"""Entraîne un modèle YOLO spécialisé armes et le copie dans models/weapons.pt.

Usage :
    python train_weapons.py chemin/vers/data.yaml [--epochs 80] [--batch 8]

Le data.yaml est au format YOLO (export « YOLOv8/YOLO11 » de Roboflow Universe, ou
tools/prepare_openimages.py), avec des classes comme : pistolet, fusil, arme blanche...
Les noms de classes du dataset sont affichés tels quels dans l'application.
"""
import argparse
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main():
    from ultralytics import YOLO

    p = argparse.ArgumentParser()
    p.add_argument("data")
    p.add_argument("--epochs", type=int, default=50)
    p.add_argument("--batch", type=int, default=6)   # 6 tient dans un GPU de 4 Go (pleine précision)
    p.add_argument("--imgsz", type=int, default=640)
    p.add_argument("--base", default="yolo11s.pt")
    args = p.parse_args()

    model = YOLO(args.base)
    model.train(data=args.data, epochs=args.epochs, batch=args.batch, imgsz=args.imgsz,
                patience=15,   # arrêt anticipé si plus de progrès pendant 15 passes
                # Le mode déterministe force des algorithmes GPU très gourmands en mémoire :
                # sur une carte de 4 Go, il déborde en RAM et l'entraînement devient ~10x plus lent.
                deterministic=False,
                workers=4, project=str(ROOT / "runs"), name="weapons", exist_ok=True)
    best = ROOT / "runs" / "weapons" / "weights" / "best.pt"
    shutil.copy(best, ROOT / "models" / "weapons.pt")
    print("Modèle copié dans models/weapons.pt — redémarrez l'application.")


# Indispensable sous Windows : les processus de chargement réimportent ce fichier
if __name__ == "__main__":
    main()
