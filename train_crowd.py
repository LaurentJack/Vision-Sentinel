"""Entraîne le modèle de comptage de foule (P2PNet) sur des images de drone et l'enregistre dans models/crowd.pth.

Données : DroneCrowd / VisDrone2020-CC (têtes annotées par des points), décompressé dans
    datasets/dronecrowd/VisDrone2020-CC/{sequences,annotations,trainlist.txt}

Usage :
    python train_crowd.py [--epochs 60] [--batch 8] [--crop 256] [--init models/crowd_init_shtech.pth]
    python train_crowd.py --resume          # reprend là où l'entraînement s'est arrêté
    python train_crowd.py --epochs 1 --limit 40   # essai rapide

Le modèle de départ conseillé est P2PNet entraîné sur ShanghaiTech A (foules denses) : il connaît déjà
les foules serrées, l'entraînement lui apprend la vue de drone. Sans --init, le réseau part de zéro
(beaucoup plus long). Les poids obtenus héritent des licences des données et du modèle de départ
(usage de recherche / non commercial) : ils ne sont pas publiés avec l'application.
"""
import argparse
import csv
import math
import random
import time
from pathlib import Path

import cv2
import numpy as np
import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader, Dataset

from app.crowd import P2PNet, to_tensor

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "datasets" / "dronecrowd" / "VisDrone2020-CC"
RUNS = ROOT / "runs" / "crowd"

# Coûts et poids de P2PNet (article d'origine)
COST_CLASS, COST_POINT = 1.0, 0.05
LOSS_POINT, EOS_WEIGHT = 2e-4, 0.5


# --- données --------------------------------------------------------------------------------------
def load_frames(seqs):
    items = []
    for s in seqs:
        ann = DATA / "annotations" / f"{s}.txt"
        if not ann.exists():
            continue
        a = np.loadtxt(ann, delimiter=",", dtype=np.float32, ndmin=2)
        for fr in np.unique(a[:, 0]).astype(int):
            img = DATA / "sequences" / s / f"{fr:05d}.jpg"
            if img.exists():
                items.append((img, a[a[:, 0] == fr, 1:3].copy()))
    return items


def split_sequences(val_every=10):
    seqs = [l.strip() for l in (DATA / "trainlist.txt").read_text().split() if l.strip()]
    seqs = [s for s in seqs if (DATA / "annotations" / f"{s}.txt").exists()]
    val = seqs[::val_every]          # ~1 séquence sur 10 mise de côté pour mesurer l'erreur
    return [s for s in seqs if s not in val], val


class CropDataset(Dataset):
    """Morceaux d'images agrandis/réduits au hasard, retournés, avec variations de couleur."""

    def __init__(self, items, crop=256, scale=(0.6, 1.8), crops_per_image=2):
        self.items, self.crop, self.scale, self.k = items, crop, scale, crops_per_image

    def __len__(self):
        return len(self.items) * self.k

    def __getitem__(self, i):
        path, pts = self.items[i % len(self.items)]
        img = cv2.imread(str(path))[:, :, ::-1].astype(np.float32) / 255
        s = math.exp(random.uniform(*map(math.log, self.scale)))
        img = cv2.resize(img, None, fx=s, fy=s, interpolation=cv2.INTER_LINEAR)
        p = pts * s
        h, w = img.shape[:2]
        c = self.crop
        if h < c or w < c:       # image plus petite que le morceau : on complète en noir
            img = cv2.copyMakeBorder(img, 0, max(0, c - h), 0, max(0, c - w), cv2.BORDER_CONSTANT)
            h, w = img.shape[:2]
        # on vise plus souvent un endroit où il y a du monde
        if len(p) and random.random() < 0.7:
            cx, cy = p[random.randrange(len(p))]
            x0 = int(np.clip(cx - random.uniform(0, c), 0, w - c))
            y0 = int(np.clip(cy - random.uniform(0, c), 0, h - c))
        else:
            x0, y0 = random.randint(0, w - c), random.randint(0, h - c)
        img = img[y0:y0 + c, x0:x0 + c]
        p = p - [x0, y0]
        p = p[(p[:, 0] >= 0) & (p[:, 0] < c) & (p[:, 1] >= 0) & (p[:, 1] < c)] if len(p) else p
        if random.random() < 0.5:
            img = img[:, ::-1]
            if len(p):
                p = np.stack([c - 1 - p[:, 0], p[:, 1]], 1)
        if random.random() < 0.8:     # lumière, contraste, saturation (neige, ombres, contre-jour)
            img = img * random.uniform(0.7, 1.3) + random.uniform(-0.1, 0.1)
            g = img.mean(2, keepdims=True)
            img = g + (img - g) * random.uniform(0.6, 1.4)
            img = np.clip(img, 0, 1)
        if random.random() < 0.3:     # flou : images de drone compressées / basse résolution
            k = random.choice([3, 5])
            img = cv2.GaussianBlur(np.ascontiguousarray(img), (k, k), 0)
        return to_tensor(np.ascontiguousarray(img, dtype=np.float32)), torch.from_numpy(np.asarray(p, np.float32).reshape(-1, 2))


def collate(batch):
    return torch.stack([b[0] for b in batch]), [b[1] for b in batch]


# --- appariement points prédits / têtes annotées (algorithme hongrois) ---------------------------
def hungarian(cost):
    """Affectation de coût minimal pour une matrice m x n avec m <= n. Renvoie (lignes, colonnes)."""
    m, n = cost.shape
    u, v = np.zeros(m + 1), np.zeros(n + 1)
    p, way = np.zeros(n + 1, int), np.zeros(n + 1, int)
    for i in range(1, m + 1):
        p[0], j0 = i, 0
        minv, used = np.full(n + 1, np.inf), np.zeros(n + 1, bool)
        while True:
            used[j0] = True
            i0 = p[j0]
            free = ~used[1:]
            cur = cost[i0 - 1] - u[i0] - v[1:]
            upd = free & (cur < minv[1:])
            minv[1:][upd] = cur[upd]
            way[1:][upd] = j0
            mv = np.where(free, minv[1:], np.inf)
            j1 = int(mv.argmin()) + 1
            delta = mv[j1 - 1]
            u[p[used]] += delta
            v[used] -= delta
            minv[1:][free] -= delta
            j0 = j1
            if p[j0] == 0:
                break
        while j0:
            j1 = way[j0]
            p[j0] = p[j1]
            j0 = j1
    cols = np.nonzero(p[1:])[0]
    return p[1:][cols] - 1, cols


@torch.no_grad()
def match(pred_pts, prob, gt, candidates=24):
    """Associe chaque tête annotée à un point prédit. Ne considère que les candidats proches (rapide)."""
    if len(gt) == 0:
        return np.zeros(0, int), np.zeros(0, int)
    d = torch.cdist(gt, pred_pts)                               # [m, K]
    k = min(candidates, d.shape[1])
    near = d.topk(k, largest=False).indices.unique()            # candidats utiles
    cost = (COST_POINT * d[:, near] - COST_CLASS * prob[near][None]).cpu().numpy().astype(np.float64)
    if cost.shape[0] > cost.shape[1]:                           # (très rare) plus de têtes que de candidats
        r, c = hungarian(cost.T)
        r, c = c, r
    else:
        r, c = hungarian(cost)
    return r, near.cpu().numpy()[c]


def loss_fn(pts, logits, targets):
    ce_w = torch.tensor([EOS_WEIGHT, 1.0], device=logits.device)
    loss_ce, loss_pt, n_gt = 0.0, 0.0, 0
    for b, gt in enumerate(targets):
        gt = gt.to(pts.device)
        prob = logits[b].float().softmax(-1)[:, 1]
        r, c = match(pts[b].float(), prob, gt)
        tgt = torch.zeros(logits.shape[1], dtype=torch.long, device=logits.device)
        tgt[torch.as_tensor(c, device=logits.device)] = 1
        loss_ce = loss_ce + F.cross_entropy(logits[b].float(), tgt, weight=ce_w)
        if len(r):
            loss_pt = loss_pt + F.mse_loss(pts[b][c].float(), gt[r], reduction="sum")
            n_gt += len(r)
    loss_ce = loss_ce / len(targets)
    loss_pt = loss_pt / max(1, n_gt)
    return loss_ce + LOSS_POINT * loss_pt, float(loss_ce.detach()), float(loss_pt.detach() if torch.is_tensor(loss_pt) else loss_pt)


def train_mode(net):
    """Mode entraînement, mais BatchNorm figées : avec de petits lots de morceaux d'image, leurs
    statistiques dérivent et le modèle ne détecte plus rien en mode évaluation."""
    net.train()
    for m in net.modules():
        if isinstance(m, torch.nn.BatchNorm2d):
            m.eval()
            for prm in m.parameters():
                prm.requires_grad_(False)


# --- évaluation -----------------------------------------------------------------------------------
@torch.no_grad()
def evaluate(net, items, device, every=5, threshold=0.5):
    net.eval()
    errs = []
    for path, gt in items[::every]:
        img = cv2.imread(str(path))
        h, w = img.shape[:2]
        W, H = round(w / 128) * 128, round(h / 128) * 128
        x = to_tensor(cv2.resize(img, (W, H))[:, :, ::-1].astype(np.float32) / 255)[None].to(device)
        _, logits = net(x)
        n = int((logits[0].float().softmax(-1)[:, 1] > threshold).sum())
        errs.append(n - len(gt))
    train_mode(net)
    e = np.array(errs, np.float64)
    return float(np.abs(e).mean()), float(np.sqrt((e ** 2).mean())), float(e.mean())


# --- boucle principale ----------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=60)
    ap.add_argument("--batch", type=int, default=8)
    ap.add_argument("--crop", type=int, default=256)
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--init", default=str(ROOT / "models" / "crowd_init_shtech.pth"))
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--limit", type=int, default=0, help="nombre d'images max (essai rapide)")
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    RUNS.mkdir(parents=True, exist_ok=True)
    train_seqs, val_seqs = split_sequences()
    train_items, val_items = load_frames(train_seqs), load_frames(val_seqs)
    if args.limit:
        random.seed(0)
        train_items = random.sample(train_items, min(args.limit, len(train_items)))
        val_items = val_items[:: max(1, len(val_items) // max(4, args.limit // 4))]
    print(f"entraînement : {len(train_items)} images ({len(train_seqs)} séquences), "
          f"validation : {len(val_items)} images ({len(val_seqs)} séquences), appareil : {device}")

    net = P2PNet().to(device)
    start, best = 0, float("inf")
    last = RUNS / "last.pth"
    if args.resume and last.exists():
        ck = torch.load(last, map_location="cpu", weights_only=True)
        net.load_state_dict(ck["model"])
        start, best = int(ck["epoch"]) + 1, float(ck["best"])
        print(f"reprise à la passe {start + 1}, meilleure erreur {best:.1f}")
    elif args.init and Path(args.init).exists():
        sd = torch.load(args.init, map_location="cpu", weights_only=True)
        net.load_state_dict(sd.get("model", sd))
        print("départ :", Path(args.init).name)
    else:
        print("départ : poids aléatoires (aucun modèle initial trouvé)")

    train_mode(net)
    backbone = [p for n, p in net.named_parameters() if n.startswith("backbone") and p.requires_grad]
    heads = [p for n, p in net.named_parameters() if not n.startswith("backbone") and p.requires_grad]
    opt = torch.optim.AdamW([{"params": heads, "lr": args.lr}, {"params": backbone, "lr": args.lr / 10}],
                            weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=args.epochs, eta_min=args.lr / 50)
    if args.resume and last.exists():
        opt.load_state_dict(ck["opt"])
        sched.load_state_dict(ck["sched"])

    dl = DataLoader(CropDataset(train_items, args.crop), batch_size=args.batch, shuffle=True,
                    num_workers=args.workers, collate_fn=collate, drop_last=True,
                    persistent_workers=args.workers > 0)
    log = RUNS / "log.csv"
    if not log.exists():
        log.write_text("passe,perte,perte_classe,perte_points,MAE,RMSE,biais,duree_s\n")

    for ep in range(start, args.epochs):
        t0, tot, tce, tpt, nb = time.time(), 0.0, 0.0, 0.0, 0
        for i, (x, targets) in enumerate(dl):
            x = x.to(device, non_blocking=True)
            pts, logits = net(x)      # pleine précision : en fp16 ce réseau déborde (perte « nan »)
            loss, lce, lpt = loss_fn(pts, logits, targets)
            opt.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(net.parameters(), 0.1)
            opt.step()
            tot, tce, tpt, nb = tot + float(loss), tce + lce, tpt + lpt, nb + 1
            if i % 50 == 0:
                print(f"  passe {ep + 1}/{args.epochs}  lot {i}/{len(dl)}  perte {tot / nb:.4f}", flush=True)
        sched.step()
        mae, rmse, bias = evaluate(net, val_items, device)
        dt = time.time() - t0
        print(f"passe {ep + 1}/{args.epochs} : perte {tot / nb:.4f}  erreur moyenne {mae:.1f} pers./image "
              f"(RMSE {rmse:.1f}, biais {bias:+.1f})  {dt / 60:.1f} min", flush=True)
        with log.open("a", newline="") as f:
            csv.writer(f).writerow([ep + 1, f"{tot / nb:.5f}", f"{tce / nb:.5f}", f"{tpt / nb:.3f}",
                                    f"{mae:.2f}", f"{rmse:.2f}", f"{bias:.2f}", f"{dt:.0f}"])
        if mae < best:
            best = mae
            torch.save(net.state_dict(), RUNS / "best.pth")
            torch.save(net.state_dict(), ROOT / "models" / "crowd.pth")
            print(f"  -> meilleur modèle enregistré dans models/crowd.pth (erreur {mae:.1f})")
        torch.save({"model": net.state_dict(), "opt": opt.state_dict(), "sched": sched.state_dict(),
                    "epoch": ep, "best": best}, last)
    print("Terminé. Meilleure erreur moyenne :", f"{best:.1f}", "personnes par image.")


# Indispensable sous Windows : les processus de chargement réimportent ce fichier
if __name__ == "__main__":
    main()
