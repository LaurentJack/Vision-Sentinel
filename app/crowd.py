"""Comptage de foule par points (architecture P2PNet, Song et al., ICCV 2021), réécrite pour Vision Sentinel.

Le réseau place un point sur chaque tête : il reste fiable là où les silhouettes se chevauchent
(foules denses, vues de drone), contrairement à la détection par boîtes.
Poids : models/crowd.pth, produits par train_crowd.py.
"""
from pathlib import Path

import cv2
import numpy as np
import torch
from torch import nn

VGG16 = [64, 64, 'M', 128, 128, 'M', 256, 256, 256, 'M', 512, 512, 512, 'M', 512, 512, 512, 'M']
MEAN = np.array([0.485, 0.456, 0.406], np.float32)
STD = np.array([0.229, 0.224, 0.225], np.float32)
STRIDE = 8          # un groupe de points candidats tous les 8 pixels
ANCHORS = 2         # 2 x 2 points candidats par case


def _vgg16_bn_layers():
    layers, c = [], 3
    for v in VGG16:
        if v == 'M':
            layers.append(nn.MaxPool2d(2, 2))
        else:
            layers += [nn.Conv2d(c, v, 3, padding=1), nn.BatchNorm2d(v), nn.ReLU(inplace=True)]
            c = v
    return layers


class _Backbone(nn.Module):
    def __init__(self):
        super().__init__()
        f = _vgg16_bn_layers()
        self.body1, self.body2 = nn.Sequential(*f[:13]), nn.Sequential(*f[13:23])
        self.body3, self.body4 = nn.Sequential(*f[23:33]), nn.Sequential(*f[33:43])

    def forward(self, x):
        out = []
        for b in (self.body1, self.body2, self.body3, self.body4):
            x = b(x)
            out.append(x)
        return out


class _Head(nn.Module):
    def __init__(self, out_ch):
        super().__init__()
        self.conv1 = nn.Conv2d(256, 256, 3, padding=1)
        self.conv2 = nn.Conv2d(256, 256, 3, padding=1)
        self.conv3 = nn.Conv2d(256, 256, 3, padding=1)   # gardées pour la compatibilité des poids d'origine
        self.conv4 = nn.Conv2d(256, 256, 3, padding=1)
        self.output = nn.Conv2d(256, out_ch, 3, padding=1)

    def forward(self, x):
        x = torch.relu(self.conv2(torch.relu(self.conv1(x))))
        return self.output(x).permute(0, 2, 3, 1)


class _Decoder(nn.Module):
    def __init__(self):
        super().__init__()
        self.P5_1, self.P5_2 = nn.Conv2d(512, 256, 1), nn.Conv2d(256, 256, 3, padding=1)
        self.P4_1, self.P4_2 = nn.Conv2d(512, 256, 1), nn.Conv2d(256, 256, 3, padding=1)
        self.P3_1, self.P3_2 = nn.Conv2d(256, 256, 1), nn.Conv2d(256, 256, 3, padding=1)
        self.up = nn.Upsample(scale_factor=2, mode='nearest')

    def forward(self, c4, c5):
        return self.P4_2(self.P4_1(c4) + self.up(self.P5_1(c5)))


def anchor_points(h, w, device):
    """Positions (x, y) des points candidats pour une carte de h x w cases."""
    off = (np.arange(1, ANCHORS + 1) - 0.5) * (STRIDE / ANCHORS) - STRIDE / 2
    ax, ay = np.meshgrid(off, off)
    sx, sy = np.meshgrid((np.arange(w) + 0.5) * STRIDE, (np.arange(h) + 0.5) * STRIDE)
    pts = np.stack([ax.ravel(), ay.ravel()], 1)[None] + np.stack([sx.ravel(), sy.ravel()], 1)[:, None]
    return torch.from_numpy(pts.reshape(-1, 2).astype(np.float32)).to(device)


class P2PNet(nn.Module):
    def __init__(self):
        super().__init__()
        self.backbone = _Backbone()
        self.fpn = _Decoder()
        n = ANCHORS * ANCHORS
        self.regression = _Head(n * 2)
        self.classification = _Head(n * 2)

    def forward(self, x):
        """Renvoie (points [N, K, 2] en pixels, logits [N, K, 2] fond / tête)."""
        f = self.backbone(x)
        p = self.fpn(f[2], f[3])
        n = x.shape[0]
        reg = self.regression(p).reshape(n, -1, 2) * 100
        logits = self.classification(p).reshape(n, -1, 2)
        return reg + anchor_points(p.shape[2], p.shape[3], x.device), logits


def to_tensor(rgb_float01):
    return torch.from_numpy(((rgb_float01 - MEAN) / STD).transpose(2, 0, 1).copy())


class CrowdCounter:
    """Compte les personnes d'une image BGR. scale > 1 agrandit l'image (petites têtes, drone en altitude)."""

    def __init__(self, weights, device=None):
        self.device = device or ('cuda' if torch.cuda.is_available() else 'cpu')
        sd = torch.load(weights, map_location='cpu', weights_only=True)
        sd = sd.get('model', sd)
        self.net = P2PNet()
        self.net.load_state_dict(sd, strict=True)
        self.net.eval().to(self.device)

    @torch.inference_mode()
    def points(self, bgr, scale=1.0, threshold=0.5, roi=None):
        """Points (x, y) des têtes, en coordonnées de l'image d'origine.

        roi : polygone [[x, y], ...] en pixels ; seuls les points à l'intérieur sont gardés.
        """
        h, w = bgr.shape[:2]
        W = max(128, round(w * scale / 128) * 128)
        H = max(128, round(h * scale / 128) * 128)
        img = cv2.resize(bgr, (W, H), interpolation=cv2.INTER_CUBIC if scale > 1 else cv2.INTER_AREA)
        t = to_tensor(img[:, :, ::-1].astype(np.float32) / 255)[None].to(self.device)
        pts, logits = self.net(t)   # pleine précision : en fp16, ce réseau déborde (valeurs infinies)
        keep = logits[0].float().softmax(-1)[:, 1] > threshold
        p = pts[0][keep].float().cpu().numpy() * [w / W, h / H]
        if roi is not None and len(p):
            poly = np.asarray(roi, np.float32)
            p = p[[cv2.pointPolygonTest(poly, (float(x), float(y)), False) >= 0 for x, y in p]]
        return p


def density_overlay(bgr, pts, sigma=None, alpha=0.45):
    """Carte de chaleur de densité dessinée sur l'image (copie)."""
    h, w = bgr.shape[:2]
    if not len(pts):
        return bgr.copy()
    sigma = sigma or max(4.0, w / 140)
    dens = np.zeros((h, w), np.float32)
    ij = np.clip(np.round(pts).astype(int), 0, [w - 1, h - 1])
    np.add.at(dens, (ij[:, 1], ij[:, 0]), 1)
    dens = cv2.GaussianBlur(dens, (0, 0), sigma)
    norm = (np.clip(dens / max(dens.max(), 1e-6), 0, 1) * 255).astype(np.uint8)
    heat = cv2.applyColorMap(norm, cv2.COLORMAP_TURBO)
    mask = (norm > 25)[..., None]
    return np.where(mask, cv2.addWeighted(bgr, 1 - alpha, heat, alpha, 0), bgr)


def default_weights(models_dir: Path):
    p = Path(models_dir) / 'crowd.pth'
    return p if p.exists() else None
