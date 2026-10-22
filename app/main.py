"""Serveur web Vision Sentinel."""
import os

os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp")

import asyncio
import gc
import json
import threading
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .analyzer import Engine
from .areas import save_all as save_counters, validate_areas
from .camera import CameraWorker
from .colors import COLOR_NAMES
from .events import EventStore
from .settings import DATA, EDITABLE, FACES, RELOAD_KEYS, SETTINGS, SNAPSHOTS, save, validate
from .faces import safe_name
from .i18n import LANGS, VALUES, UserError, msg, pick_lang

CAMERAS_FILE = DATA / "cameras.json"
STATIC = Path(__file__).parent / "static"

engine: Engine = None
events: EventStore = None
workers: dict[str, CameraWorker] = {}
reloading = False
reload_lock = threading.Lock()


def save_cameras():
    CAMERAS_FILE.write_text(json.dumps([w.cfg for w in workers.values()], indent=2, ensure_ascii=False),
                            encoding="utf-8")


def start_camera(cfg: dict):
    w = CameraWorker(cfg, engine, events)
    workers[cfg["id"]] = w
    w.start()
    return w


def reload_engine():
    """Recharge les modèles (ex. passage CPU <-> GPU) puis relance les caméras."""
    global engine, reloading
    with reload_lock:
        reloading = True
        try:
            cfgs = [w.cfg for w in workers.values()]
            save_counters({cid: w.areas for cid, w in workers.items()})  # repris par les nouvelles caméras
            old = list(workers.values())
            for w in old:
                w.stop()
            for w in old:
                w.join()
                w.release()  # coupe les liens vers les modèles, même si un flux vidéo garde la caméra
            workers.clear()
            del old
            engine = None
            free_gpu_memory()
            engine = Engine()
            for cfg in cfgs:
                start_camera(cfg)
        finally:
            reloading = False
    # Les derniers flux vidéo de l'ancienne page se ferment après coup : second nettoyage
    threading.Timer(10, free_gpu_memory).start()


def free_gpu_memory():
    gc.collect()
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except ImportError:
        pass


def purge_loop():
    """Durée de conservation : efface chaque heure le journal et les captures trop anciens."""
    while True:
        days = SETTINGS.get("retention_days", 30)
        if days and events is not None:
            for name in events.purge_before(time.time() - days * 86400):
                (SNAPSHOTS / name).unlink(missing_ok=True)
        time.sleep(3600)


def counters_loop():
    """Sauvegarde les compteurs des zones et lignes toutes les 30 s (ils survivent à un redémarrage)."""
    while True:
        time.sleep(30)
        try:
            save_counters({cid: w.areas for cid, w in list(workers.items())})
        except Exception as exc:
            print(f"[compteurs] sauvegarde impossible : {exc}")


@asynccontextmanager
async def lifespan(app):
    global engine, events
    engine = Engine()
    events = EventStore()
    if CAMERAS_FILE.exists():
        for cfg in json.loads(CAMERAS_FILE.read_text(encoding="utf-8")):
            start_camera(cfg)
    threading.Thread(target=purge_loop, daemon=True, name="purge").start()
    threading.Thread(target=counters_loop, daemon=True, name="compteurs").start()
    yield
    for w in workers.values():
        w.stop()
    save_counters({cid: w.areas for cid, w in workers.items()})


app = FastAPI(title="Vision Sentinel", lifespan=lifespan)


@app.exception_handler(UserError)
async def user_error(request: Request, exc: UserError):
    """Message d'erreur dans la langue de l'interface (en-tête X-Lang)."""
    lang = pick_lang(request.headers.get("x-lang"))
    return JSONResponse({"detail": msg(exc.code, lang, **exc.params)}, status_code=exc.status)


@app.get("/api/i18n")
def i18n_values():
    """Noms affichés des valeurs neutres (couleurs, vêtements, armes) dans chaque langue."""
    return {key: dict(zip(LANGS, names)) for key, names in VALUES.items()}


@app.middleware("http")
async def no_stale_ui(request, call_next):
    """L'interface est revalidée à chaque chargement : une mise à jour s'affiche sans vider le cache."""
    response = await call_next(request)
    if not request.url.path.startswith(("/api/", "/snapshots/", "/faces/")):
        response.headers["Cache-Control"] = "no-cache"
    return response


class CameraIn(BaseModel):
    name: str
    source: str
    colors: bool = True
    faces: bool = True
    weapons: bool = True
    analyze: bool = True
    max_fps: int | None = None


class CameraPatch(BaseModel):
    name: str | None = None
    colors: bool | None = None
    faces: bool | None = None
    weapons: bool | None = None
    analyze: bool | None = None
    max_fps: int | None = None


def get_worker(cam_id: str) -> CameraWorker:
    w = workers.get(cam_id)
    if not w:
        raise UserError("unknown_camera", status=404)
    return w


# --- caméras -------------------------------------------------------------------
@app.get("/api/status")
def status():
    if reloading or engine is None:
        return {"reloading": True}
    return {**engine.status(), "colors": COLOR_NAMES, "cameras": len(workers), "reloading": False,
            "privacy_ack": SETTINGS.get("privacy_ack"), "face_recognition": SETTINGS.get("face_recognition", True)}


# --- réglages --------------------------------------------------------------------
@app.get("/api/settings")
def get_settings():
    return {"values": {k: SETTINGS.get(k) for k in EDITABLE}, "reload_keys": sorted(RELOAD_KEYS)}


@app.post("/api/settings")
def set_settings(changes: dict):
    clean = validate(changes)  # UserError (traduite) si un réglage est invalide
    need_reload = any(k in RELOAD_KEYS and SETTINGS.get(k) != v for k, v in clean.items())
    SETTINGS.update(clean)
    save()
    if need_reload and not reloading:
        threading.Thread(target=reload_engine, daemon=True, name="reload").start()
    return {"ok": True, "reloading": need_reload}


@app.get("/api/cameras")
def list_cameras():
    return [w.info() for w in workers.values()]


@app.post("/api/cameras")
def add_camera(cam: CameraIn):
    ready_engine()
    cfg = {"id": uuid.uuid4().hex[:8], **cam.model_dump()}
    start_camera(cfg)
    save_cameras()
    return cfg


@app.patch("/api/cameras/{cam_id}")
def update_camera(cam_id: str, patch: CameraPatch):
    w = get_worker(cam_id)
    w.cfg.update({k: v for k, v in patch.model_dump().items() if v is not None})
    save_cameras()
    return w.info()


@app.delete("/api/cameras/{cam_id}")
def delete_camera(cam_id: str):
    w = get_worker(cam_id)
    w.stop()
    del workers[cam_id]
    threading.Thread(target=lambda: (w.join(), w.release()), daemon=True).start()
    save_cameras()
    return {"ok": True}


@app.get("/api/cameras/{cam_id}/stream")
async def stream(cam_id: str):
    w = get_worker(cam_id)

    async def gen():
        last = -1
        while w.running:
            if w.jpeg_seq != last:
                last, jpg = w.jpeg_seq, w.jpeg
                yield (b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: "
                       + str(len(jpg)).encode() + b"\r\n\r\n" + jpg + b"\r\n")
            await asyncio.sleep(0.02)

    return StreamingResponse(gen(), media_type="multipart/x-mixed-replace; boundary=frame")


@app.put("/api/cameras/{cam_id}/areas")
def set_areas(cam_id: str, body: dict):
    """Zones et lignes de comptage dessinées dans l'interface."""
    w = get_worker(cam_id)
    areas = validate_areas(body.get("areas"))
    w.cfg["areas"] = areas
    w.areas.sync(areas)
    save_cameras()
    return w.info()


@app.post("/api/cameras/{cam_id}/areas/{area_id}/reset")
def reset_area(cam_id: str, area_id: str):
    w = get_worker(cam_id)
    w.areas.reset(area_id)
    return w.info()


@app.get("/api/cameras/{cam_id}/frame")
def raw_frame(cam_id: str):
    """Image brute actuelle (sans dessins) pour l'éditeur de zones."""
    return Response(get_worker(cam_id).current_frame(), media_type="image/jpeg",
                    headers={"Cache-Control": "no-store"})


@app.get("/api/cameras/{cam_id}/snapshot")
def snapshot(cam_id: str):
    return Response(get_worker(cam_id).jpeg, media_type="image/jpeg")


# --- événements ------------------------------------------------------------------
@app.get("/api/events")
def get_events(type: str | None = None, camera_id: str | None = None, upper: str | None = None,
               lower: str | None = None, label: str | None = None, after_id: int | None = None,
               since: float | None = None, limit: int = 200, upper_type: str | None = None,
               lower_type: str | None = None):
    return events.query(type=type, camera_id=camera_id, upper=upper, lower=lower, label=label,
                        after_id=after_id, since=since, limit=limit,
                        upper_type=upper_type, lower_type=lower_type)


@app.delete("/api/events")
def clear_events():
    events.clear()
    for f in SNAPSHOTS.glob("*.jpg"):
        f.unlink(missing_ok=True)
    return {"ok": True}


# --- visages ---------------------------------------------------------------------
def ready_engine() -> Engine:
    if reloading or engine is None:
        raise UserError("reloading", status=503)
    return engine


@app.get("/api/faces")
def list_faces():
    return ready_engine().faces.list()


@app.post("/api/faces")
async def enroll_face(name: str = Form(...), photo: UploadFile = File(...)):
    saved = ready_engine().faces.enroll(name, await photo.read())
    return {"ok": True, "name": saved}


@app.delete("/api/faces/{name}")
def delete_face(name: str):
    ready_engine().faces.remove(name)
    return {"ok": True}


@app.get("/faces/{name}/{photo}")
def face_photo(name: str, photo: str):
    path = FACES / safe_name(name) / Path(photo).name
    if not path.is_file():
        raise HTTPException(404)
    return FileResponse(path)


@app.get("/", include_in_schema=False)
@app.get("/index.html", include_in_schema=False)
def index():
    """Page d'accueil : app.js et style.css sont demandés avec un numéro de version
    (date de modification), pour qu'un navigateur ne garde jamais une ancienne copie."""
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    for name in ("i18n.js", "app.js", "areas.js", "style.css"):
        version = int((STATIC / name).stat().st_mtime)
        html = html.replace(f'"{name}"', f'"{name}?v={version}"')
    return Response(html, media_type="text/html; charset=utf-8", headers={"Cache-Control": "no-cache"})


app.mount("/snapshots", StaticFiles(directory=SNAPSHOTS), name="snapshots")
app.mount("/", StaticFiles(directory=STATIC, html=True), name="static")
