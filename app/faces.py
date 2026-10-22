"""Détection (YuNet) et reconnaissance faciale (SFace) avec OpenCV."""
import re
import shutil
import threading
import uuid

import cv2
import numpy as np

from .i18n import UserError
from .settings import FACES, MODELS, SETTINGS

DET_MODEL = MODELS / "face_detection_yunet_2023mar.onnx"
REC_MODEL = MODELS / "face_recognition_sface_2021dec.onnx"
DET_W = SETTINGS.get("face_det_width", 640)  # largeur utilisée pour la détection


def safe_name(name: str) -> str:
    name = re.sub(r"[^\w \-]", "", name, flags=re.UNICODE).strip()
    return name[:60]


class FaceEngine:
    def __init__(self):
        self.lock = threading.Lock()
        self.available = DET_MODEL.exists() and REC_MODEL.exists()
        self.gallery: dict[str, list[np.ndarray]] = {}
        if not self.available:
            print("[visages] Modèles absents : lancez `python download_models.py`.")
            return
        self.detector = cv2.FaceDetectorYN.create(str(DET_MODEL), "", (320, 320), 0.8, 0.3, 5000)
        self.recognizer = cv2.FaceRecognizerSF.create(str(REC_MODEL), "")
        self.reload()

    # --- bas niveau -------------------------------------------------------
    def _detect(self, img):
        """Détecte sur une copie réduite ; renvoie les coordonnées dans l'image d'origine."""
        h, w = img.shape[:2]
        scale = min(1.0, DET_W / w)
        small = cv2.resize(img, (int(w * scale), int(h * scale))) if scale < 1 else img
        self.detector.setInputSize((small.shape[1], small.shape[0]))
        _, faces = self.detector.detect(small)
        if faces is None:
            return []
        faces[:, :14] /= scale
        return faces

    def _embed(self, img, face):
        aligned = self.recognizer.alignCrop(img, face)
        return self.recognizer.feature(aligned).copy()

    def _identify(self, feat):
        best_name, best_score = None, 0.0
        for name, feats in self.gallery.items():
            for g in feats:
                score = self.recognizer.match(feat, g, cv2.FaceRecognizerSF_FR_COSINE)
                if score > best_score:
                    best_name, best_score = name, score
        if best_score >= SETTINGS["face_match_threshold"]:
            return best_name, float(best_score)
        return None, float(best_score)

    # --- analyse d'une image du flux --------------------------------------
    def analyze(self, frame, recognize=True):
        """Détecte les visages ; identifie seulement si `recognize` (reconnaissance faciale activée)."""
        if not self.available:
            return []
        recognize = recognize and SETTINGS.get("face_recognition", True) and bool(self.gallery)
        out = []
        with self.lock:
            for f in self._detect(frame):
                name, score = self._identify(self._embed(frame, f)) if recognize else (None, 0.0)
                x, y, w, h = f[:4].astype(int)
                out.append({
                    "kind": "face", "label": name or "unknown", "known": name is not None,
                    "conf": score, "box": (max(0, x), max(0, y), x + w, y + h),
                })
        return out

    # --- galerie -----------------------------------------------------------
    def _largest_face_feature(self, img):
        faces = self._detect(img)
        if len(faces) == 0:
            return None
        face = max(faces, key=lambda f: f[2] * f[3])
        return self._embed(img, face)

    def reload(self):
        gallery = {}
        with self.lock:
            for person_dir in sorted(p for p in FACES.iterdir() if p.is_dir()):
                feats = []
                for img_path in person_dir.iterdir():
                    img = cv2.imdecode(np.fromfile(str(img_path), np.uint8), cv2.IMREAD_COLOR)
                    if img is None:
                        continue
                    feat = self._largest_face_feature(img)
                    if feat is not None:
                        feats.append(feat)
                if feats:
                    gallery[person_dir.name] = feats
            self.gallery = gallery
        print(f"[visages] {len(gallery)} personne(s) enregistrée(s).")

    def enroll(self, name: str, data: bytes) -> str:
        if not self.available:
            raise UserError("face_models_missing")
        name = safe_name(name)
        if not name:
            raise UserError("invalid_name")
        img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            raise UserError("unreadable_image")
        with self.lock:
            feat = self._largest_face_feature(img)
            if feat is None:
                raise UserError("no_face")
            folder = FACES / name
            folder.mkdir(exist_ok=True)
            ok, buf = cv2.imencode(".jpg", img)
            buf.tofile(str(folder / f"{uuid.uuid4().hex[:10]}.jpg"))
            self.gallery.setdefault(name, []).append(feat)
        return name

    def list(self):
        out = []
        for d in sorted(p for p in FACES.iterdir() if p.is_dir()):
            photos = sorted(f.name for f in d.iterdir() if f.is_file())
            out.append({"name": d.name, "photos": photos, "count": len(photos)})
        return out

    def remove(self, name: str):
        name = safe_name(name)
        folder = FACES / name
        if folder.is_dir():
            shutil.rmtree(folder)
        with self.lock:
            self.gallery.pop(name, None)
