"""Copie les modèles nécessaires à côté de l'exécutable : dist/VisionSentinel/models."""
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "models"
DST = ROOT / "dist" / "VisionSentinel" / "models"

FILES = ["yolo11n.pt", "yolo11n-seg.pt", "weapons.pt", "mobile_sam.pt",
         "face_detection_yunet_2023mar.onnx", "face_recognition_sface_2021dec.onnx"]

DST.mkdir(parents=True, exist_ok=True)
for name in FILES:
    if not (SRC / name).exists():
        sys.exit(f"Modèle manquant : {SRC / name} (lancez download_models.py)")
    shutil.copy2(SRC / name, DST / name)
    print(f"copié : {name}")

# CLIP : un seul fichier de poids, chargé sans passer par le cache Hugging Face
clip = next((SRC / "clip").rglob("open_clip_model.safetensors"), None)
if clip is None:
    sys.exit("Poids CLIP introuvables dans models/clip (lancez l'application une fois en mode développement)")
shutil.copy2(clip, DST / "clip_vit_b32.safetensors")
print("copié : clip_vit_b32.safetensors")
size = sum(f.stat().st_size for f in DST.iterdir()) / 1e6
print(f"Modèles : {size:.0f} Mo dans {DST}")
