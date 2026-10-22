"""Construit un dataset YOLO « armes » à partir d'Open Images (Google, licence CC BY 2.0).

Classes produites :
    0 pistolet      <- Handgun
    1 fusil         <- Rifle, Shotgun
    2 arme blanche  <- Knife, Kitchen knife, Dagger, Sword
+ des images « négatives » sans arme (téléphones, parapluies, télécommandes, marteaux, bouteilles)
  pour limiter les fausses alertes.

Usage :
    python tools/prepare_openimages.py --out datasets/armes [--max-per-class 4000] [--neg-ratio 0.2]
"""
import argparse
import csv
import io
import random
import urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import cv2
import numpy as np

BASE = "https://storage.googleapis.com/openimages"
ANNOTATIONS = {
    "train": [("train", f"{BASE}/v6/oidv6-train-annotations-bbox.csv")],
    "val": [("validation", f"{BASE}/v5/validation-annotations-bbox.csv"),
            ("test", f"{BASE}/v5/test-annotations-bbox.csv")],
}
IMAGE_URL = "https://s3.amazonaws.com/open-images-dataset/{folder}/{id}.jpg"

CLASSES = ["pistolet", "fusil", "arme blanche"]
WEAPON_MIDS = {
    "/m/0gxl3": 0,                                   # Handgun
    "/m/06c54": 1, "/m/06nrc": 1,                    # Rifle, Shotgun
    "/m/04ctx": 2, "/m/058qzx": 2, "/m/02gzp": 2, "/m/06y5r": 2,  # Knife, Kitchen knife, Dagger, Sword
}
GENERIC_WEAPON = "/m/083kb"
NEGATIVE_MIDS = {"/m/050k8", "/m/0hnnb", "/m/0qjjc", "/m/03l9g", "/m/04dr76w"}
MAX_SIDE = 960


def stream_csv(url):
    with urllib.request.urlopen(url) as resp:
        yield from csv.DictReader(io.TextIOWrapper(resp, encoding="utf-8"))


def collect(split):
    boxes = defaultdict(list)       # image -> [(cls, xmin, xmax, ymin, ymax)]
    folder = {}
    neg_candidates = set()
    has_weapon = set()
    for oi_folder, url in ANNOTATIONS[split]:
        print(f"[{split}] lecture des annotations {url.rsplit('/', 1)[-1]} ...", flush=True)
        for i, row in enumerate(stream_csv(url)):
            mid, img = row["LabelName"], row["ImageID"]
            if mid in WEAPON_MIDS:
                boxes[img].append((WEAPON_MIDS[mid], float(row["XMin"]), float(row["XMax"]),
                                   float(row["YMin"]), float(row["YMax"])))
                folder[img] = oi_folder
                has_weapon.add(img)
            elif mid == GENERIC_WEAPON:
                has_weapon.add(img)
            elif mid in NEGATIVE_MIDS:
                neg_candidates.add(img)
                folder.setdefault(img, oi_folder)
            if i % 2_000_000 == 0 and i:
                print(f"  {i // 1_000_000} M lignes, {len(boxes)} images avec armes", flush=True)
    negatives = sorted(neg_candidates - has_weapon)
    return boxes, folder, negatives


def select(boxes, negatives, max_per_class, neg_ratio, rng):
    images = list(boxes)
    rng.shuffle(images)
    count = defaultdict(int)
    chosen = []
    for img in images:
        classes = {b[0] for b in boxes[img]}
        if any(count[c] < max_per_class for c in classes):
            chosen.append(img)
            for c in classes:
                count[c] += 1
    n_neg = min(len(negatives), int(len(chosen) * neg_ratio))
    return chosen, rng.sample(negatives, n_neg), dict(count)


def download(img, folder, out_img, out_lbl, boxes):
    dest = out_img / f"{img}.jpg"
    if not dest.exists():
        data = urllib.request.urlopen(IMAGE_URL.format(folder=folder, id=img), timeout=30).read()
        im = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
        if im is None:
            return False
        h, w = im.shape[:2]
        s = MAX_SIDE / max(h, w)
        if s < 1:
            im = cv2.resize(im, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA)
        cv2.imwrite(str(dest), im, [cv2.IMWRITE_JPEG_QUALITY, 90])
    lines = [f"{c} {(x1 + x2) / 2:.6f} {(y1 + y2) / 2:.6f} {x2 - x1:.6f} {y2 - y1:.6f}"
             for c, x1, x2, y1, y2 in boxes]
    (out_lbl / f"{img}.txt").write_text("\n".join(lines), encoding="utf-8")
    return True


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--out", default="datasets/armes")
    p.add_argument("--max-per-class", type=int, default=4000)
    p.add_argument("--neg-ratio", type=float, default=0.2)
    p.add_argument("--workers", type=int, default=24)
    args = p.parse_args()
    out = Path(args.out).resolve()
    rng = random.Random(0)

    for split in ("val", "train"):
        boxes, folder, negatives = collect(split)
        cap = args.max_per_class if split == "train" else max(300, args.max_per_class // 8)
        chosen, negs, count = select(boxes, negatives, cap, args.neg_ratio, rng)
        print(f"[{split}] {len(chosen)} images avec armes {({CLASSES[k]: v for k, v in sorted(count.items())})}"
              f" + {len(negs)} négatives", flush=True)
        out_img, out_lbl = out / "images" / split, out / "labels" / split
        out_img.mkdir(parents=True, exist_ok=True)
        out_lbl.mkdir(parents=True, exist_ok=True)
        jobs = [(i, boxes[i]) for i in chosen] + [(i, []) for i in negs]
        ok = 0
        with ThreadPoolExecutor(args.workers) as pool:
            futs = [pool.submit(download, i, folder[i], out_img, out_lbl, b) for i, b in jobs]
            for n, f in enumerate(as_completed(futs), 1):
                try:
                    ok += f.result()
                except Exception:
                    pass
                if n % 500 == 0:
                    print(f"  [{split}] {n}/{len(jobs)} images", flush=True)
        print(f"[{split}] terminé : {ok}/{len(jobs)} images téléchargées", flush=True)

    yaml = [f"path: {out.as_posix()}", "train: images/train", "val: images/val", "names:"]
    yaml += [f"  {i}: {n}" for i, n in enumerate(CLASSES)]
    (out / "data.yaml").write_text("\n".join(yaml) + "\n", encoding="utf-8")
    print(f"Dataset prêt : {out / 'data.yaml'}")


if __name__ == "__main__":
    main()
