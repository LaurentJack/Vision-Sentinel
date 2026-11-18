"""Enregistrement vidéo : segments MP4 (H.264) par caméra.

Modes par caméra (clé "record" de la caméra) :
- "off"        : rien n'est enregistré ;
- "alerts"     : autour des alertes (arme, visage reconnu, zone trop pleine) ;
- "people"     : dès qu'une personne est visible (+ alertes) ;
- "continuous" : en permanence.

Les dernières secondes sont gardées en mémoire (tampon « pré-alerte ») : un clip commence donc
AVANT l'alerte, et continue « recording_post_s » secondes après la dernière. Les fichiers sont des
MP4 fragmentés : lisibles même pendant l'écriture ou après une coupure de courant.
Encodage par FFmpeg (paquet imageio-ffmpeg, libx264) ; aucune fenêtre ne s'ouvre.
"""
import collections
import os
import sqlite3
import subprocess
import threading
import time
from datetime import datetime

import cv2
import numpy as np

from .settings import DATA, SETTINGS

REC_DIR = DATA / "recordings"
REC_DIR.mkdir(parents=True, exist_ok=True)
MODES = ("off", "alerts", "people", "continuous")
SEGMENT_MAX_S = 600          # un fichier toutes les 10 minutes au plus
PROGRESS_EVERY_S = 5         # mise à jour de la fin du segment dans la base
STALE_FRAME_S = 5            # caméra muette depuis 5 s : on arrête d'écrire
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def ffmpeg_exe():
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


# --- base des segments --------------------------------------------------------------
class RecordingStore:
    def __init__(self):
        self.db = sqlite3.connect(str(DATA / "recordings.db"), check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.lock = threading.Lock()
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS recordings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                camera_id TEXT NOT NULL, camera_name TEXT,
                start REAL NOT NULL, end REAL NOT NULL,
                path TEXT NOT NULL, size INTEGER DEFAULT 0,
                kind TEXT, open INTEGER DEFAULT 1
            )""")
        self.db.execute("CREATE INDEX IF NOT EXISTS idx_rec_cam ON recordings(camera_id, start)")
        # Segments restés « ouverts » (arrêt brutal) : clos avec la dernière fin connue et leur vraie
        # taille ; ceux qui sont vides ou disparus sont supprimés
        for rid, path in self.db.execute("SELECT id, path FROM recordings WHERE open=1").fetchall():
            size = os.path.getsize(path) if os.path.exists(path) else 0
            if size < 1024:
                if os.path.exists(path):
                    os.remove(path)
                self.db.execute("DELETE FROM recordings WHERE id=?", (rid,))
            else:
                self.db.execute("UPDATE recordings SET open=0, size=? WHERE id=?", (size, rid))
        self.db.execute("DELETE FROM recordings WHERE size<1024 AND open=0")
        self.db.commit()

    def add(self, **row) -> int:
        with self.lock:
            cur = self.db.execute(
                "INSERT INTO recordings (camera_id, camera_name, start, end, path, kind, open) VALUES (?,?,?,?,?,?,1)",
                (row["camera_id"], row["camera_name"], row["start"], row["start"], row["path"], row["kind"]))
            self.db.commit()
            return cur.lastrowid

    def progress(self, rec_id, end, size, done=False):
        with self.lock:
            self.db.execute("UPDATE recordings SET end=?, size=?, open=? WHERE id=?", (end, size, 0 if done else 1, rec_id))
            self.db.commit()

    def get(self, rec_id):
        with self.lock:
            r = self.db.execute("SELECT * FROM recordings WHERE id=?", (rec_id,)).fetchone()
        return dict(r) if r else None

    def between(self, camera_id, t0, t1):
        with self.lock:
            rows = self.db.execute(
                "SELECT * FROM recordings WHERE camera_id=? AND end>=? AND start<=? ORDER BY start",
                (camera_id, t0, t1)).fetchall()
        return [dict(r) for r in rows]

    def locate(self, camera_id, ts):
        """Segment qui contient ts, sinon le prochain qui commence dans les 5 minutes."""
        with self.lock:
            r = self.db.execute("SELECT * FROM recordings WHERE camera_id=? AND start<=? AND end>=? ORDER BY start DESC LIMIT 1",
                                (camera_id, ts + 1, ts - 1)).fetchone()
            if not r:
                r = self.db.execute("SELECT * FROM recordings WHERE camera_id=? AND start>=? AND start<=? ORDER BY start LIMIT 1",
                                    (camera_id, ts, ts + 300)).fetchone()
        return dict(r) if r else None

    def usage(self):
        with self.lock:
            n, total = self.db.execute("SELECT COUNT(*), COALESCE(SUM(size), 0) FROM recordings").fetchone()
        return n, total

    def delete(self, rec_id):
        r = self.get(rec_id)
        if not r:
            return False
        try:
            os.remove(r["path"])
        except FileNotFoundError:
            pass
        with self.lock:
            self.db.execute("DELETE FROM recordings WHERE id=?", (rec_id,))
            self.db.commit()
        return True

    def cleanup(self):
        """Durée de conservation + quota disque : supprime les segments les plus anciens."""
        days = SETTINGS.get("retention_days", 30)
        removed = 0
        if days:
            with self.lock:
                old = [r[0] for r in self.db.execute("SELECT id FROM recordings WHERE end<? AND open=0",
                                                    (time.time() - days * 86400,))]
            for rid in old:
                removed += self.delete(rid)
        quota = SETTINGS.get("recording_max_gb", 50) * 1e9
        try:
            free = __import__("shutil").disk_usage(REC_DIR).free
        except OSError:
            free = None
        while True:
            _, total = self.usage()
            low_disk = free is not None and free < 2e9
            if not ((quota and total > quota) or low_disk):
                break
            with self.lock:
                r = self.db.execute("SELECT id FROM recordings WHERE open=0 ORDER BY start LIMIT 1").fetchone()
            if not r:
                break
            removed += self.delete(r[0])
            if low_disk:
                free = __import__("shutil").disk_usage(REC_DIR).free
        return removed


# --- enregistreur d'une caméra ---------------------------------------------------------
class Recorder:
    def __init__(self, worker, store: RecordingStore):
        self.w = worker
        self.store = store
        self.buffer = collections.deque()   # (horodatage, image JPEG) : tampon pré-alerte
        self.proc = None
        self.rec_id = None
        self.path = None
        self.seg_start = 0.0
        self.size_wh = None
        self.fps = 10
        self.until = 0.0                     # enregistrer au moins jusqu'à cet instant
        self.last_progress = 0.0
        self.recording = False
        self.thread = None

    # appelé par la caméra
    def trigger(self):
        self.until = max(self.until, time.time() + SETTINGS.get("recording_post_s", 30))

    def start(self):
        self.thread = threading.Thread(target=self._loop, daemon=True, name=f"rec-{self.w.id}")
        self.thread.start()

    def join(self, timeout=5.0):
        if self.thread:
            self.thread.join(timeout)

    # --- préparation d'une image : taille fixe, floutage éventuel, date et heure incrustées ---
    def _prepare(self, frame, now):
        img = frame.copy()
        if SETTINGS.get("blur_unknown_faces"):
            from .analyzer import _blur_faces
            _blur_faces(img, [d for d in self.w.last_dets if d.get("kind") == "face"])
        width = int(SETTINGS.get("recording_width", 1280))
        h, w = img.shape[:2]
        if w > width:
            img = cv2.resize(img, (width, int(round(h * width / w / 2)) * 2), interpolation=cv2.INTER_AREA)
        h, w = img.shape[:2]
        if w % 2 or h % 2:  # H.264 (yuv420p) exige des dimensions paires
            img = img[: h - h % 2, : w - w % 2]
        if SETTINGS.get("recording_overlay", True):
            text = f"{self.w.cfg['name']}  {datetime.fromtimestamp(now).strftime('%Y-%m-%d %H:%M:%S')}"
            text = text.encode("ascii", "ignore").decode()
            scale = max(0.45, img.shape[1] / 1800)
            (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, scale, 1)
            y = img.shape[0] - 10
            cv2.rectangle(img, (6, y - th - 8), (14 + tw, y + 4), (0, 0, 0), -1)
            cv2.putText(img, text, (10, y - 2), cv2.FONT_HERSHEY_SIMPLEX, scale, (255, 255, 255), 1, cv2.LINE_AA)
        return img

    # --- fichier en cours -----------------------------------------------------------------
    def _open(self, shape, kind):
        h, w = shape[:2]
        start = self.buffer[0][0] if self.buffer else time.time()
        day = datetime.fromtimestamp(start)
        folder = REC_DIR / self.w.id / day.strftime("%Y-%m-%d")
        folder.mkdir(parents=True, exist_ok=True)
        self.path = folder / f"{day.strftime('%H%M%S')}_{kind}.mp4"
        args = [ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y",
                "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{w}x{h}", "-r", str(self.fps), "-i", "-",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", str(SETTINGS.get("recording_crf", 26)),
                "-pix_fmt", "yuv420p", "-g", str(self.fps * 2),
                # MP4 fragmenté écrit sur le disque à chaque fragment (toutes les 2 s) : lisible pendant
                # l'écriture et récupérable après une coupure de courant
                "-movflags", "frag_keyframe+empty_moov+default_base_moof", "-flush_packets", "1", str(self.path)]
        self.proc = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL, creationflags=NO_WINDOW)
        self.size_wh = (w, h)
        self.seg_start = start
        self.rec_id = self.store.add(camera_id=self.w.id, camera_name=self.w.cfg["name"], start=start,
                                     path=str(self.path), kind=kind)
        self.recording = True
        # le tampon pré-alerte part en premier dans le fichier
        while self.buffer:
            _, jpg = self.buffer.popleft()
            img = cv2.imdecode(np.frombuffer(jpg, np.uint8), cv2.IMREAD_COLOR)
            if img is not None and img.shape[:2] == (h, w):
                self._write(img)

    def _write(self, img):
        try:
            self.proc.stdin.write(img.tobytes())
        except (BrokenPipeError, OSError, ValueError):
            print(f"[enregistrement] {self.w.cfg['name']} : FFmpeg s'est arrêté, segment clos.")
            self._close()

    def _close(self):
        if not self.proc:
            return
        proc, self.proc = self.proc, None
        try:
            proc.stdin.close()
            proc.wait(timeout=20)
        except Exception:
            proc.kill()
        size = self.path.stat().st_size if self.path and self.path.exists() else 0
        self.store.progress(self.rec_id, time.time(), size, done=True)
        self.recording = False
        self.rec_id = None

    # --- boucle -------------------------------------------------------------------------
    def _loop(self):
        next_t = time.time()
        while self.w.running:
            mode = self.w.cfg.get("record", "alerts")
            now = time.time()
            with self.w.frame_lock:
                frame = self.w.frame
                fresh = now - getattr(self.w, "frame_time", 0) < STALE_FRAME_S
            if mode not in MODES or mode == "off" or frame is None or not fresh:
                self._close()
                self.buffer.clear()
                time.sleep(0.5)
                next_t = time.time()
                continue
            if not self.proc:
                self.fps = int(SETTINGS.get("recording_fps", 10))  # fixé pour toute la durée du segment
            img = self._prepare(frame, now)
            want = mode == "continuous" or now < self.until
            if want:
                if self.proc and (img.shape[1], img.shape[0]) != self.size_wh:
                    self._close()  # la résolution de la caméra a changé
                if not self.proc:
                    self._open(img.shape, "continuous" if mode == "continuous" else "event")
                if self.proc:
                    self._write(img)
                if self.proc and now - self.last_progress > PROGRESS_EVERY_S:
                    self.last_progress = now
                    self.store.progress(self.rec_id, now, self.path.stat().st_size if self.path.exists() else 0)
                if self.proc and now - self.seg_start > SEGMENT_MAX_S:
                    self._close()  # nouveau fichier au tour suivant
            else:
                self._close()
                pre = SETTINGS.get("recording_pre_s", 10)
                if pre > 0:
                    ok, jpg = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 85])
                    if ok:
                        self.buffer.append((now, jpg.tobytes()))
                    while self.buffer and now - self.buffer[0][0] > pre:
                        self.buffer.popleft()
            # cadence fixe : la durée de la vidéo correspond au temps réel
            next_t += 1.0 / self.fps
            delay = next_t - time.time()
            if delay > 0:
                time.sleep(delay)
            else:
                next_t = time.time()  # en retard : on ne rattrape pas (sinon accélération)
        self._close()


# --- export d'un extrait (un ou plusieurs segments) -----------------------------------------
def export_clip(segments, t0, t1, out_path):
    """Assemble [t0, t1] à partir des segments (copie sans réencodage, coupe aux images clés)."""
    parts = []
    for s in segments:
        a, b = max(t0, s["start"]), min(t1, s["end"])
        if b - a > 0.5 and os.path.exists(s["path"]):
            parts.append((s["path"], a - s["start"], b - s["start"]))
    if not parts:
        return False
    exe = ffmpeg_exe()
    if len(parts) == 1:
        path, a, b = parts[0]
        args = [exe, "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{a:.2f}", "-i", path,
                "-t", f"{b - a:.2f}", "-c", "copy", "-movflags", "+faststart", str(out_path)]
    else:
        lst = str(out_path) + ".txt"
        with open(lst, "w", encoding="utf-8") as f:
            for path, a, b in parts:
                f.write(f"file '{path.replace(chr(92), '/')}'\ninpoint {a:.2f}\noutpoint {b:.2f}\n")
        args = [exe, "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst,
                "-c", "copy", "-movflags", "+faststart", str(out_path)]
    r = subprocess.run(args, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, creationflags=NO_WINDOW, timeout=600)
    if len(parts) > 1:
        try:
            os.remove(str(out_path) + ".txt")
        except OSError:
            pass
    return r.returncode == 0 and os.path.exists(out_path) and os.path.getsize(out_path) > 0
