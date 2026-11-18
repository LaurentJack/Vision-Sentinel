"""Lecture d'un flux caméra + analyse en continu (2 threads par caméra)."""
import os
import threading
import time
from collections import Counter
from pathlib import Path

import cv2
import numpy as np

from .analyzer import _label, draw
from .areas import AreaCounter, draw_areas
from .i18n import msg
from .settings import SETTINGS, SNAPSHOTS

PERSON_LOG_AFTER = 5     # images de suivi avant d'enregistrer une personne
TRACK_FORGET_S = 60


def placeholder(text: str, w=640, h=360) -> bytes:
    img = np.full((h, w, 3), 25, np.uint8)
    (tw, _), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.8, 2)
    cv2.putText(img, text, ((w - tw) // 2, h // 2), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (180, 180, 180), 2, cv2.LINE_AA)
    return cv2.imencode(".jpg", img)[1].tobytes()


def open_source(src: str):
    src = src.strip()
    if src.isdigit():  # webcam USB / intégrée
        backend = cv2.CAP_DSHOW if os.name == "nt" else cv2.CAP_ANY
        cap = cv2.VideoCapture(int(src), backend)
    else:              # rtsp://, http(s)://, fichier vidéo
        cap = cv2.VideoCapture(src, cv2.CAP_FFMPEG)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    return cap


class CameraWorker:
    def __init__(self, cfg: dict, engine, events, recordings=None):
        self.cfg = cfg
        self.engine = engine
        self.events = events
        self.analyzer = engine.new_analyzer()
        self.running = False
        self.status = "starting"
        self.fps = 0.0
        self.frame = None
        self.frame_seq = 0
        self.frame_lock = threading.Lock()
        self.jpeg = placeholder(msg("connecting", SETTINGS.get("overlay_lang", "fr")))
        self.jpeg_seq = 0
        self.last_dets = []
        self._cooldown = {}
        self._tracks = {}
        self._threads = []
        self.frame_time = 0.0
        # Enregistrement vidéo (segments MP4) : None si le module n'est pas disponible
        self.recorder = None
        if recordings is not None:
            from .recorder import Recorder
            self.recorder = Recorder(self, recordings)
        self.areas = AreaCounter(cfg["id"])  # zones et lignes de comptage
        self.areas.sync(cfg.get("areas") or [])

    @property
    def id(self):
        return self.cfg["id"]

    def start(self):
        self.running = True
        for fn in (self._grab_loop, self._process_loop):
            t = threading.Thread(target=fn, daemon=True, name=f"{fn.__name__}-{self.id}")
            t.start()
            self._threads.append(t)
        if self.recorder:
            self.recorder.start()

    def stop(self):
        self.running = False

    def join(self, timeout=5.0):
        """Attend l'arrêt des threads (libère la caméra avant de la rouvrir)."""
        for t in self._threads:
            t.join(timeout)
        if self.recorder:
            self.recorder.join(timeout + 20)  # laisse FFmpeg finir le fichier

    def release(self):
        """Libère les modèles et images (mémoire GPU) d'une caméra arrêtée."""
        self.analyzer = None
        self.engine = None
        self.frame = None
        self.last_dets = []

    def info(self):
        return {**self.cfg, "status": self.status, "fps": round(self.fps, 1),
                "detections": len(self.last_dets), "counts": self.areas.snapshot(),
                "recording": bool(self.recorder and self.recorder.recording)}

    def current_frame(self) -> bytes:
        """Dernière image brute (sans dessins), pour dessiner les zones dans l'interface."""
        with self.frame_lock:
            frame = None if self.frame is None else self.frame.copy()
        if frame is None:
            return self.jpeg
        return cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])[1].tobytes()

    def _set_jpeg(self, data: bytes):
        self.jpeg = data
        self.jpeg_seq += 1

    # --- lecture ---------------------------------------------------------
    def _grab_loop(self):
        src = self.cfg["source"]
        is_file = Path(src.strip()).is_file()
        cap = None
        while self.running:
            if cap is None or not cap.isOpened():
                self.status = "connecting"
                cap = open_source(src)
                if not cap.isOpened():
                    self.status = "offline"
                    self._set_jpeg(placeholder(msg("offline_retry", SETTINGS.get("overlay_lang", "fr"))))
                    cap = None
                    time.sleep(3)
                    continue
                file_delay = 1.0 / (cap.get(cv2.CAP_PROP_FPS) or 25) if is_file else 0
            ok, frame = cap.read()
            if not ok:
                if is_file:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    continue
                self.status = "reconnecting"
                cap.release()
                cap = None
                time.sleep(2)
                continue
            self.status = "online"
            with self.frame_lock:
                self.frame = frame
                self.frame_seq += 1
                self.frame_time = time.time()
            if is_file:
                time.sleep(file_delay)
        if cap is not None:
            cap.release()

    # --- analyse ---------------------------------------------------------
    def _process_loop(self):
        last_seq, t_prev = -1, time.time()
        while self.running:
            with self.frame_lock:
                frame, seq = self.frame, self.frame_seq
            min_dt = 1.0 / max(1, self.cfg.get("max_fps") or SETTINGS["max_fps"])
            if frame is None or seq == last_seq or time.time() - t_prev < min_dt:
                time.sleep(0.005)
                continue
            last_seq = seq
            try:
                dets = self.analyzer.analyze(frame, self.cfg) if self.cfg.get("analyze", True) else []
            except Exception as exc:  # une erreur d'analyse ne doit pas couper le flux
                print(f"[{self.cfg['name']}] erreur d'analyse : {exc}")
                dets = []
            self.last_dets = dets
            areas = self.cfg.get("areas") or []
            persons = [d for d in dets if d["kind"] == "person"]
            over = self.areas.update(areas, persons, frame.shape)
            if self.recorder and persons and self.cfg.get("record", "alerts") == "people":
                self.recorder.trigger()  # mode « personnes » : on enregistre tant que quelqu'un est visible
            annotated = draw(frame.copy(), dets)
            draw_areas(annotated, areas, self.areas.snapshot(), _label)
            self._handle_events(annotated, dets)
            for zone, inside in over:  # trop de monde dans une zone
                if self._ready(("zone", zone["id"]), SETTINGS.get("zone_cooldown_s", 60)):
                    self._log(annotated, type="zone", label=zone["name"], value=inside)
            h, w = annotated.shape[:2]
            if w > 1280:
                annotated = cv2.resize(annotated, (1280, int(h * 1280 / w)))
            self._set_jpeg(cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 75])[1].tobytes())
            now = time.time()
            self.fps = 0.9 * self.fps + 0.1 * (1.0 / max(1e-3, now - t_prev))
            t_prev = now

    def _ready(self, key, delay):
        now = time.time()
        if now - self._cooldown.get(key, 0) < delay:
            return False
        self._cooldown[key] = now
        return True

    def _log(self, img, **ev):
        if self.recorder and ev.get("type") in ("weapon", "face", "zone"):
            self.recorder.trigger()  # clip vidéo autour de l'alerte
        ev_id = self.events.add(camera_id=self.id, camera_name=self.cfg["name"], **ev)
        name = f"{ev_id}.jpg"
        small = img
        if img.shape[1] > 960:
            small = cv2.resize(img, (960, int(img.shape[0] * 960 / img.shape[1])))
        cv2.imwrite(str(SNAPSHOTS / name), small, [cv2.IMWRITE_JPEG_QUALITY, 80])
        self.events.set_snapshot(ev_id, name)

    def _handle_events(self, img, dets):
        now = time.time()
        # Armes : une alerte par famille (« arme à feu », « couteau »...) qui liste tous les types vus
        # dans l'image (ex. « fusil d'assaut, pistolet »). Le délai porte sur la famille, car le type
        # précis peut varier d'une image à l'autre.
        groups = {}
        for d in dets:
            if d["kind"] == "weapon":
                groups.setdefault(d.get("group", d["label"]), []).append(d)
        for group, items in groups.items():
            if self._ready(("weapon", group), SETTINGS["weapon_cooldown_s"]):
                items.sort(key=lambda d: -d["conf"])
                types = list(dict.fromkeys(d["label"] for d in items))
                self._log(img, type="weapon", label=", ".join(types), confidence=items[0]["conf"])
        for d in dets:
            if d["kind"] == "face":
                if d.get("known") or SETTINGS["log_unknown_faces"]:
                    if self._ready(("face", d["label"]), SETTINGS["face_cooldown_s"]):
                        self._log(img, type="face", label=d["label"], confidence=d["conf"])
            elif d["kind"] == "person" and d.get("track_id") is not None and "upper" in d:
                t = self._tracks.setdefault(d["track_id"], {"up": Counter(), "low": Counter(), "upt": Counter(),
                                                            "lowt": Counter(), "n": 0, "logged": False})
                t["up"][d["upper"]] += 1
                t["low"][d["lower"]] += 1
                for key, field in (("upt", "upper_type"), ("lowt", "lower_type")):
                    if d.get(field) and d[field] != "?":
                        t[key][d[field]] += 1
                t["n"] += 1
                t["seen"] = now
                if not t["logged"] and t["n"] >= PERSON_LOG_AFTER:
                    t["logged"] = True
                    top = lambda c: c.most_common(1)[0][0] if c else None
                    self._log(img, type="person", label="person", confidence=d["conf"],
                              upper=top(t["up"]), lower=top(t["low"]),
                              upper_type=top(t["upt"]), lower_type=top(t["lowt"]),
                              track_id=d["track_id"])
        for tid in [k for k, t in self._tracks.items() if now - t.get("seen", now) > TRACK_FORGET_S]:
            del self._tracks[tid]
