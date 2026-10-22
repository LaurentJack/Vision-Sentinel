"""Zones (personnes présentes dans un périmètre) et lignes (passages dans chaque sens).

Les zones et lignes sont dessinées dans l'interface, enregistrées dans la configuration de la
caméra avec des coordonnées relatives (0 à 1), donc indépendantes de la résolution du flux.

Une personne est repérée par le point à ses pieds (bas-centre de son cadre) :
- zone : elle est comptée si ce point est à l'intérieur du polygone ;
- ligne : un passage est compté quand ce point traverse le segment entre deux images.
  « Entrée » = traversée dans le sens de la flèche affichée sur la vidéo, « sortie » = l'inverse.
"""
import json
import threading
import time
import uuid

import cv2
import numpy as np

from .i18n import UserError, msg
from .settings import DATA, SETTINGS

COUNTERS_FILE = DATA / "counters.json"
_file_lock = threading.Lock()

ZONE_COLOR = (230, 180, 40)    # bleu clair (BGR)
LINE_COLOR = (0, 200, 255)     # jaune orangé
CROSS_DEBOUNCE_S = 1.0         # une même personne ne compte pas deux fois la même ligne en 1 s
TRACK_FORGET_S = 10


def _new_counts():
    return {"inside": 0, "max": 0, "in": 0, "out": 0, "since": time.time()}


# --- validation des zones envoyées par l'interface --------------------------------
def validate_areas(raw) -> list:
    if not isinstance(raw, list) or len(raw) > 50:
        raise UserError("invalid_areas")
    out = []
    for a in raw:
        if not isinstance(a, dict):
            raise UserError("invalid_areas")
        kind, pts = a.get("kind"), a.get("points")
        if kind not in ("zone", "line") or not isinstance(pts, list):
            raise UserError("invalid_areas")
        if (kind == "zone" and not 3 <= len(pts) <= 40) or (kind == "line" and len(pts) != 2):
            raise UserError("invalid_areas")
        points = []
        for p in pts:
            if not isinstance(p, (list, tuple)) or len(p) != 2:
                raise UserError("invalid_areas")
            try:
                x, y = float(p[0]), float(p[1])
            except (TypeError, ValueError):
                raise UserError("invalid_areas")
            points.append([round(min(1.0, max(0.0, x)), 4), round(min(1.0, max(0.0, y)), 4)])
        item = {"id": str(a.get("id") or uuid.uuid4().hex[:8])[:16], "kind": kind,
                "name": str(a.get("name") or "").strip()[:40] or kind, "points": points}
        if kind == "zone" and a.get("max_people") not in (None, ""):
            try:
                mp = int(a["max_people"])
            except (TypeError, ValueError):
                raise UserError("invalid_areas")
            if not 1 <= mp <= 1000:
                raise UserError("invalid_areas")
            item["max_people"] = mp
        out.append(item)
    return out


# --- géométrie -------------------------------------------------------------------
def _side(p, a, b):
    """> 0 si p est du côté de la flèche (normale) du segment a->b, < 0 de l'autre côté."""
    return (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])


def _segments_cross(p1, p2, a, b):
    d1, d2 = _side(p1, a, b), _side(p2, a, b)
    d3, d4 = _side(a, p1, p2), _side(b, p1, p2)
    return d1 * d2 < 0 and d3 * d4 < 0


def _pixels(points, w, h):
    return [(x * w, y * h) for x, y in points]


# --- compteurs d'une caméra --------------------------------------------------------
class AreaCounter:
    def __init__(self, cam_id: str):
        self.cam_id = cam_id
        self.lock = threading.Lock()
        self.counts = _load(cam_id)
        self._prev = {}       # track_id -> (x, y, t) : dernière position des pieds
        self._crossed = {}    # (area_id, track_id) -> t du dernier passage compté

    def sync(self, areas):
        """Garde les compteurs des zones existantes, en crée pour les nouvelles."""
        with self.lock:
            ids = {a["id"] for a in areas}
            self.counts = {k: v for k, v in self.counts.items() if k in ids}
            for a in areas:
                self.counts.setdefault(a["id"], _new_counts())

    def reset(self, area_id):
        with self.lock:
            if area_id in self.counts:
                self.counts[area_id] = _new_counts()

    def snapshot(self):
        with self.lock:
            return {k: dict(v) for k, v in self.counts.items()}

    def update(self, areas, persons, shape):
        """Met à jour les compteurs ; renvoie les zones qui dépassent leur seuil [(zone, présents)]."""
        if not areas:
            return []
        h, w = shape[:2]
        now = time.time()
        feet = {d["track_id"]: ((d["box"][0] + d["box"][2]) / 2, d["box"][3])
                for d in persons if d.get("track_id") is not None}
        over = []
        with self.lock:
            for a in areas:
                c = self.counts.setdefault(a["id"], _new_counts())
                pts = _pixels(a["points"], w, h)
                if a["kind"] == "zone":
                    poly = np.array(pts, np.float32)
                    inside = sum(cv2.pointPolygonTest(poly, p, False) >= 0 for p in feet.values())
                    c["inside"] = int(inside)
                    c["max"] = max(c["max"], int(inside))
                    if a.get("max_people") and inside > a["max_people"]:
                        over.append((a, int(inside)))
                else:
                    p1, p2 = pts
                    for tid, cur in feet.items():
                        prev = self._prev.get(tid)
                        if not prev or not _segments_cross(prev[:2], cur, p1, p2):
                            continue
                        key = (a["id"], tid)
                        if now - self._crossed.get(key, 0) < CROSS_DEBOUNCE_S:
                            continue
                        self._crossed[key] = now
                        if _side(prev[:2], p1, p2) < 0:   # vers le côté de la flèche
                            c["in"] += 1
                        else:
                            c["out"] += 1
        for tid, (x, y) in feet.items():
            self._prev[tid] = (x, y, now)
        for tid in [k for k, v in self._prev.items() if now - v[2] > TRACK_FORGET_S]:
            del self._prev[tid]
        for key in [k for k, t in self._crossed.items() if now - t > 60]:
            del self._crossed[key]
        return over


# --- dessin sur la vidéo -------------------------------------------------------------
def draw_areas(img, areas, counts, label_fn):
    """Zones (polygone translucide + nombre de présents) et lignes (flèche d'entrée + compteurs)."""
    if not areas:
        return img
    lang = SETTINGS.get("overlay_lang", "fr")
    h, w = img.shape[:2]
    overlay = img.copy()
    labels = []
    for a in areas:
        c = counts.get(a["id"], _new_counts())
        pts = np.array(_pixels(a["points"], w, h), np.int32)
        if a["kind"] == "zone":
            cv2.fillPoly(overlay, [pts], ZONE_COLOR)
            cv2.polylines(img, [pts], True, ZONE_COLOR, 2, cv2.LINE_AA)
            text = f"{a['name']}: {c['inside']}" + (f"/{a['max_people']}" if a.get("max_people") else "")
            top = pts[pts[:, 1].argmin()]
            labels.append((text, int(top[0]), int(top[1]) - 4, ZONE_COLOR))
        else:
            (x1, y1), (x2, y2) = pts
            cv2.line(img, (x1, y1), (x2, y2), LINE_COLOR, 3, cv2.LINE_AA)
            # Flèche perpendiculaire au milieu : sens compté comme « entrée »
            mx, my = (x1 + x2) / 2, (y1 + y2) / 2
            nx, ny = -(y2 - y1), (x2 - x1)
            norm = max(1.0, (nx * nx + ny * ny) ** 0.5)
            length = max(20, min(50, int(0.06 * max(w, h))))
            tip = (int(mx + nx / norm * length), int(my + ny / norm * length))
            cv2.arrowedLine(img, (int(mx), int(my)), tip, LINE_COLOR, 2, cv2.LINE_AA, tipLength=0.35)
            text = f"{a['name']}  {msg('in', lang)}:{c['in']}  {msg('out', lang)}:{c['out']}"
            # Au milieu de la ligne, à côté de la flèche (le haut de l'image est souvent encombré)
            labels.append((text, int(mx) + 8, int(my) - 8, LINE_COLOR))
    cv2.addWeighted(overlay, 0.18, img, 0.82, 0, dst=img)
    placed = []  # les étiquettes se décalent au lieu de se recouvrir
    for text, x, y, col in labels:
        label_fn(img, text, x, y, col, placed)
    return img


# --- sauvegarde des compteurs (survivent à un redémarrage) ----------------------------
def _load(cam_id):
    try:
        with _file_lock:
            data = json.loads(COUNTERS_FILE.read_text(encoding="utf-8"))
        return {k: {**_new_counts(), **v, "inside": 0} for k, v in data.get(cam_id, {}).items()}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_all(counters: dict):
    """counters : {cam_id: AreaCounter}"""
    data = {cam_id: c.snapshot() for cam_id, c in counters.items()}
    with _file_lock:
        tmp = COUNTERS_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=1), encoding="utf-8")
        tmp.replace(COUNTERS_FILE)
