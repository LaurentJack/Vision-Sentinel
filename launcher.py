"""Point d'entrée de l'application installée (VisionSentinel.exe).

Démarre le serveur web en arrière-plan et l'affiche dans une fenêtre native (WebView2).
Fermer la fenêtre arrête le serveur et les caméras.
Si l'application tourne déjà, une nouvelle fenêtre s'ouvre sur le serveur existant.
"""
import ctypes
import json
import logging
import os
import socket
import sys
import threading
import time
import urllib.request

FROZEN = getattr(sys, "frozen", False)
if FROZEN:
    os.environ.setdefault("HF_HUB_OFFLINE", "1")        # tous les modèles sont fournis : pas d'Internet
    os.environ.setdefault("YOLO_OFFLINE", "1")
    os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp")

APP_NAME = "Vision Sentinel"


def system_lang():
    """fr / nl / en selon la langue de Windows (pour l'écran de chargement)."""
    try:
        primary = ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3FF
        return {0x0C: "fr", 0x13: "nl"}.get(primary, "en")
    except Exception:
        return "fr"


TEXTS = {
    "fr": ("Chargement des modèles…", "Le premier démarrage peut prendre une minute.",
           "Le port {port} est déjà utilisé par un autre programme.\nFermez-le ou changez « server_port » dans :\n{file}",
           "Le serveur s'est arrêté pendant le démarrage. Détails dans :\n{file}"),
    "nl": ("Modellen worden geladen…", "De eerste start kan een minuut duren.",
           "Poort {port} wordt al door een ander programma gebruikt.\nSluit het of wijzig « server_port » in:\n{file}",
           "De server is tijdens het opstarten gestopt. Details in:\n{file}"),
    "en": ("Loading models…", "The first start can take a minute.",
           "Port {port} is already used by another program.\nClose it or change « server_port » in:\n{file}",
           "The server stopped during startup. Details in:\n{file}"),
}

LOADING_HTML = """<!doctype html><html><head><meta charset="utf-8"><style>
body{{margin:0;height:100vh;display:flex;align-items:center;justify-content:center;flex-direction:column;
color:#d5f2ff;font:15px "Bahnschrift","Segoe UI",sans-serif;letter-spacing:.12em;text-transform:uppercase;
background:radial-gradient(700px 400px at 50% 45%,rgba(0,229,255,.10),transparent 70%),
linear-gradient(rgba(0,229,255,.12) 1px,transparent 1px) 0 0/44px 44px,
linear-gradient(90deg,rgba(0,229,255,.12) 1px,transparent 1px) 0 0/44px 44px,#04070c}}
.b{{color:#00e5ff;font-weight:600;font-size:24px;letter-spacing:.2em;margin-bottom:22px;text-shadow:0 0 14px rgba(0,229,255,.5)}}
.s{{width:40px;height:40px;border:2px solid #14344c;border-top-color:#00e5ff;border-radius:50%;
box-shadow:0 0 14px rgba(0,229,255,.3);animation:r 1s linear infinite;margin-bottom:18px}}@keyframes r{{to{{transform:rotate(360deg)}}}}
.m{{color:#6a8aa2;font:12px "Cascadia Mono",Consolas,monospace;letter-spacing:.04em;text-transform:none;margin-top:8px}}</style></head>
<body><div class="b">◉ Vision Sentinel</div><div class="s"></div><div>{title}</div><div class="m">{sub}</div></body></html>"""


def message_box(text):
    try:
        ctypes.windll.user32.MessageBoxW(None, text, APP_NAME, 0x10)
    except Exception:
        print(text)


def already_running(url):
    """True si notre serveur répond déjà (application déjà ouverte)."""
    try:
        with urllib.request.urlopen(url + "/api/status", timeout=1.5) as r:
            data = json.loads(r.read())
            return "device" in data or "reloading" in data
    except Exception:
        return False


def port_free(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


def setup_logging(log_dir):
    """Version installée : pas de console, tout va dans logs/vision-sentinel.log."""
    if FROZEN:
        log = open(log_dir / "vision-sentinel.log", "a", encoding="utf-8", buffering=1)
        sys.stdout = sys.stderr = log
    logging.basicConfig(level=logging.INFO, stream=sys.stderr,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    print(f"\n===== {APP_NAME} démarré le {time.strftime('%Y-%m-%d %H:%M:%S')} =====")


def open_window(url, server=None, server_thread=None, lang="fr", log_file=""):
    import webview
    webview.settings["ALLOW_DOWNLOADS"] = True  # export des extraits vidéo (MP4)
    title, sub, _, failed = TEXTS[lang]
    window = webview.create_window(APP_NAME, html=LOADING_HTML.format(title=title, sub=sub),
                                   width=1440, height=900, min_size=(900, 600))

    def wait_until_ready():
        if server is None:
            window.load_url(url)
            return
        while not server.started:
            if not server_thread.is_alive():
                message_box(failed.format(file=log_file))
                window.destroy()
                return
            time.sleep(0.3)
        window.load_url(url)

    webview.start(wait_until_ready, private_mode=False,
                  storage_path=str(LOGS_DIR.parent / "webview"))  # garde la langue choisie, etc.


def diagnostic(sources):
    """VisionSentinel.exe --diagnostic [source ...] : état du GPU et lecture vidéo, écrit dans le journal."""
    import cv2
    from cv2 import videoio_registry as vr
    print("OpenCV", cv2.__version__)
    print("backends vidéo :", [vr.getBackendName(b) for b in vr.getBackends()])
    print("backends fichiers/flux :", [vr.getBackendName(b) for b in vr.getStreamBackends()])
    for line in cv2.getBuildInformation().splitlines():
        if "FFMPEG" in line or "Video I/O" in line:
            print(" ", line.strip())
    try:
        import torch
        print("torch", torch.__version__, "| CUDA :", torch.cuda.is_available())
    except Exception as exc:
        print("torch indisponible :", exc)
    for src in sources:
        cap = cv2.VideoCapture(int(src) if src.isdigit() else src, cv2.CAP_ANY if src.isdigit() else cv2.CAP_FFMPEG)
        ok = cap.isOpened()
        print(f"source {src!r} : ouverte={ok}", f"backend={cap.getBackendName()}" if ok else "")
        cap.release()


def main():
    global LOGS_DIR
    from app.settings import DATA, LOGS, SETTINGS
    LOGS_DIR = LOGS
    setup_logging(LOGS)
    if "--diagnostic" in sys.argv:
        diagnostic(sys.argv[sys.argv.index("--diagnostic") + 1:])
        return
    lang = system_lang()
    port = int(SETTINGS.get("server_port", 8000))
    host = SETTINGS.get("server_host", "127.0.0.1")
    url = f"http://127.0.0.1:{port}"

    if already_running(url):           # deuxième lancement : simple fenêtre en plus
        open_window(url, lang=lang)
        return
    if not port_free(port):
        message_box(TEXTS[lang][2].format(port=port, file=DATA / "settings.json"))
        return

    import uvicorn
    from app.main import app
    server = uvicorn.Server(uvicorn.Config(app, host=host, port=port, log_config=None, access_log=False))
    thread = threading.Thread(target=server.run, name="serveur", daemon=True)
    thread.start()
    try:
        open_window(url, server, thread, lang, LOGS / "vision-sentinel.log")
    finally:
        server.should_exit = True     # fenêtre fermée : arrêt propre (caméras, compteurs)
        thread.join(timeout=15)
        print(f"===== {APP_NAME} arrêté =====")
        os._exit(0)                   # coupe les lectures de caméras encore bloquées


LOGS_DIR = None

if __name__ == "__main__":
    main()
