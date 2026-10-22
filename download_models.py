"""Télécharge les modèles nécessaires dans le dossier models/.

- yolo11n / yolo11n-seg : personnes (+ couteaux, ciseaux, battes) — Ultralytics, AGPL-3.0
- mobile_sam : détourage des armes en mode « contours » — Ultralytics (MobileSAM, Apache-2.0)
- YuNet / SFace : détection et reconnaissance faciale — OpenCV Zoo (MIT / Apache-2.0)
- weapons.pt : armes à feu — Zcket/gun_dtct sur Hugging Face (MIT), vérifié par empreinte SHA-256
Le modèle CLIP (vêtements, types d'armes) est téléchargé automatiquement au premier lancement.
"""
import hashlib
import sys
import urllib.request
from pathlib import Path

MODELS = Path(__file__).resolve().parent / "models"
MODELS.mkdir(exist_ok=True)

# nom local -> (adresse, empreinte SHA-256 attendue ou None)
FILES = {
    "yolo11n.pt": ("https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11n.pt", None),
    # Version segmentation : contour des personnes au lieu d'un carré
    "yolo11n-seg.pt": ("https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11n-seg.pt", None),
    # Détourage des armes détectées par models/weapons.pt
    "mobile_sam.pt": ("https://github.com/ultralytics/assets/releases/download/v8.3.0/mobile_sam.pt", None),
    "face_detection_yunet_2023mar.onnx": (
        "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx", None),
    "face_recognition_sface_2021dec.onnx": (
        "https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx", None),
    # Modèle communautaire : un fichier .pt peut contenir du code, on n'accepte que la version analysée
    # (aucun appel dangereux, vérifié avec picklescan).
    "weapons.pt": ("https://huggingface.co/Zcket/gun_dtct/resolve/main/yolov8_background1k_best.pt",
                   "f1b151a061cbc960b7dc3aee4aa5306d7250be05daa4960cc0bf65627e917ef8"),
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


for name, (url, expected) in FILES.items():
    dest = MODELS / name
    if dest.exists() and dest.stat().st_size > 100_000 and (expected is None or sha256(dest) == expected):
        print(f"déjà présent : {name}")
        continue
    print(f"téléchargement : {name} ...")
    tmp = dest.with_suffix(dest.suffix + ".part")
    urllib.request.urlretrieve(url, tmp)
    if expected and sha256(tmp) != expected:
        tmp.unlink()
        sys.exit(f"ERREUR : {name} ne correspond pas à la version vérifiée (empreinte différente). "
                 f"Fichier supprimé par sécurité.")
    tmp.replace(dest)
    print(f"  -> {dest.stat().st_size / 1e6:.1f} Mo")

print("OK.")
