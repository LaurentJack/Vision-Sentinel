"""Analyse d'une image : personnes (+ couleurs de vêtements), armes, visages, ou comptage de foule."""
import threading
import time
import unicodedata
from collections import deque

import cv2
import numpy as np

from .colors import clothing_colors
from .faces import FaceEngine
from .i18n import to_key, tv, msg
from .settings import MODELS, SETTINGS

# Objets du jeu COCO considérés comme armes par le modèle général
COCO_WEAPONS = {"knife": "knife", "scissors": "scissors", "baseball bat": "baseball_bat"}


def _device():
    dev = SETTINGS["device"]
    if dev == "cpu":
        return dev
    if dev != "auto":  # GPU demandé : on vérifie qu'il est bien là
        try:
            import torch
            if torch.cuda.is_available():
                return dev
        except ImportError:
            pass
        print("[moteur] GPU demandé mais indisponible : calcul sur CPU.")
        return "cpu"
    try:
        import torch
        return "cuda:0" if torch.cuda.is_available() else "cpu"
    except ImportError:
        return "cpu"


def gpu_info():
    try:
        import torch
        if torch.cuda.is_available():
            return {"gpu_available": True, "gpu_name": torch.cuda.get_device_name(0),
                    # Mémoire GPU réservée par l'application (0 en mode CPU une fois libérée)
                    "gpu_mem_mb": round(torch.cuda.memory_reserved() / 1e6)}
    except ImportError:
        pass
    return {"gpu_available": False, "gpu_name": None}


class Engine:
    """Ressources partagées par toutes les caméras."""

    def __init__(self):
        from ultralytics import YOLO
        # Ultralytics désactive le multi-thread d'OpenCV à l'import : on le rétablit (visages 2x plus rapides)
        import os
        cv2.setNumThreads(os.cpu_count() or 4)
        self._YOLO = YOLO
        self.device = _device()
        self.half = self.device.startswith("cuda")
        self.person_path = MODELS / SETTINGS["person_model"]
        if not self.person_path.exists():  # modèle de segmentation absent : cadres seulement
            self.person_path = MODELS / "yolo11n.pt"
        self.contours = SETTINGS.get("draw_style", "contour") == "contour"
        # MobileSAM détoure les objets du modèle d'armes (qui ne donne que des cadres)
        self.sam = None
        self.sam_lock = threading.Lock()
        sam_path = MODELS / SETTINGS.get("sam_model", "mobile_sam.pt")
        if self.contours and sam_path.exists():
            from ultralytics import SAM
            self.sam = SAM(str(sam_path))
        self.faces = FaceEngine()
        # CLIP : type de vêtements, type d'arme et vérification des alertes (chargé si l'un est actif)
        self.clip = None
        if any(SETTINGS.get(k, True) for k in ("clothing", "weapon_types", "weapon_verify")):
            try:
                from .clip import ClipClassifier
                self.clip = ClipClassifier(self.device)
            except Exception as exc:
                print(f"[CLIP] désactivé : {exc}")
        self.weapon_model = None
        self.weapon_lock = threading.Lock()
        self.weapon_names = {}
        wpath = MODELS / SETTINGS["weapon_model"]
        if wpath.exists():
            self.weapon_model = YOLO(str(wpath))
            # Noms affichés : renommage possible via "weapon_labels" dans data/settings.json
            labels = SETTINGS.get("weapon_labels", {})
            # to_key : « arme à feu » (ancien réglage) devient la clé neutre « firearm »
            self.weapon_names = {i: to_key(labels.get(n, n)) for i, n in self.weapon_model.names.items()}
            print(f"[armes] Modèle spécialisé chargé : {wpath.name} -> {list(self.weapon_names.values())}")
        else:
            print("[armes] Pas de models/weapons.pt : seules les armes blanches COCO "
                  "(couteau, ciseaux, batte) sont détectées. Voir README.")
        # Comptage de foule : chargé à la première caméra en mode « foule / drone »
        self.crowd_path = MODELS / SETTINGS.get("crowd_model", "crowd.pth")
        self._crowd = None
        self.crowd_lock = threading.Lock()
        print(f"[moteur] Calcul sur : {self.device}")

    def crowd_counter(self):
        """Modèle de comptage de foule partagé (None s'il n'est pas installé)."""
        if self._crowd is None and self.crowd_path.exists():
            with self.crowd_lock:
                if self._crowd is None:
                    from .crowd import CrowdCounter
                    self._crowd = CrowdCounter(self.crowd_path, device=self.device)
                    print(f"[foule] Modèle chargé : {self.crowd_path.name}")
        return self._crowd

    def new_analyzer(self):
        return Analyzer(self)

    def status(self):
        return {
            "device": self.device,
            **gpu_info(),
            "faces_available": self.faces.available,
            "weapon_model": self.weapon_model is not None,
            "crowd_model": self.crowd_path.exists(),
            "weapon_classes": list(self.weapon_names.values()),
            "draw_style": "contour" if self.contours else "box",
            "clothing_upper": self.clip.upper_names if self.clip and SETTINGS.get("clothing", True) else [],
            "clothing_lower": self.clip.lower_names if self.clip and SETTINGS.get("clothing", True) else [],
        }


class Analyzer:
    """Un analyseur par caméra (le suivi des personnes est propre à chaque flux)."""

    def __init__(self, engine: Engine):
        self.engine = engine
        self.model = engine._YOLO(str(engine.person_path))
        names = self.model.names
        self.person_cls = [i for i, n in names.items() if n == "person"]
        self.weapon_cls = {i: COCO_WEAPONS[n] for i, n in names.items() if n in COCO_WEAPONS}
        if "knife" in engine.weapon_names.values():
            # Le modèle spécialisé gère déjà les couteaux : évite une double alerte
            self.weapon_cls = {i: lbl for i, lbl in self.weapon_cls.items() if lbl != "knife"}
        self._n = 0
        self._last_faces = []
        self._clothes = {}  # track_id -> dernier type de vêtements connu
        self._crowd_hist = deque(maxlen=5)  # derniers comptages de foule (chiffre affiché lissé)

    def _count_crowd(self, frame):
        """Mode foule : un point par tête. Le nombre affiché est la médiane des derniers comptages."""
        cc = self.engine.crowd_counter()
        if cc is None:
            return {"kind": "crowd", "label": "crowd", "conf": 1.0, "box": (0, 0, 0, 0),
                    "points": np.zeros((0, 2), np.float32), "count": None}
        with self.engine.crowd_lock:  # un seul passage à la fois sur la carte graphique
            pts = cc.points(frame, SETTINGS.get("crowd_scale", 1.0), SETTINGS.get("crowd_threshold", 0.5))
        self._crowd_hist.append(len(pts))
        return {"kind": "crowd", "label": "crowd", "conf": 1.0, "box": (0, 0, 0, 0), "points": pts,
                "count": int(np.median(self._crowd_hist))}

    def _check_weapons(self, frame, found):
        """CLIP sur chaque arme détectée : écarte les objets anodins, puis précise le type."""
        try:
            checks = self.engine.clip.classify_weapons(frame, [d["box"] for d in found])
        except Exception as exc:
            print(f"[armes] vérification impossible : {exc}")
            return found
        kept = []
        for d, c in zip(found, checks):
            if c is None:
                kept.append(d)
                continue
            if SETTINGS.get("weapon_verify", True) and c["not_weapon"] >= SETTINGS.get("weapon_verify_threshold", 0.6):
                continue  # téléphone, bouteille... : pas d'alerte
            d["group"] = d["label"]  # « arme à feu » : sert au délai entre alertes (le type peut varier)
            if SETTINGS.get("weapon_types", True) and c["type_conf"] >= SETTINGS.get("weapon_type_min_conf", 0.4):
                d["label"] = c["type"]
                d["type_conf"] = c["type_conf"]
            kept.append(d)
        return kept

    def _update_clothing(self, frame, persons):
        """Type de vêtements par personne suivie : calculé rarement, puis mémorisé."""
        clf = self.engine.clip
        now = time.time()
        refresh = SETTINGS.get("clothing_refresh_s", 8)
        min_h = SETTINGS.get("clothing_min_height", 90)
        todo = [d for d in persons
                if d.get("track_id") is not None and d["box"][3] - d["box"][1] >= min_h
                and now - self._clothes.get(d["track_id"], {}).get("t", 0) > refresh]
        # Priorité aux nouvelles personnes, puis aux plus grandes ; 2 au plus par image
        todo.sort(key=lambda d: (d["track_id"] in self._clothes, -(d["box"][3] - d["box"][1])))
        todo = todo[:SETTINGS.get("clothing_per_frame", 2)]
        if todo:
            for d, r in zip(todo, clf.classify_clothing(frame, [d["box"] for d in todo])):
                if r:
                    self._clothes[d["track_id"]] = {"t": now, **r}
        for d in persons:
            c = self._clothes.get(d.get("track_id"))
            if c:
                d.update({k: v for k, v in c.items() if k != "t"})
        for tid in [k for k, v in self._clothes.items() if now - v["t"] > 120]:
            del self._clothes[tid]

    def analyze(self, frame, opts: dict):
        e = self.engine
        dets = []
        # Mode foule / drone : les têtes sont comptées par points ; la détection individuelle des
        # personnes, des vêtements et des visages est coupée (inutile vue d'en haut, et coûteuse).
        crowd = bool(opts.get("crowd"))
        if crowd:
            dets.append(self._count_crowd(frame))
        # Personnes suivies si l'une des fonctions en a besoin (vêtements, armes, zones de comptage)
        want_people = not crowd and (opts.get("colors", True) or opts.get("weapons", True) or bool(opts.get("areas")))
        classes = list(self.person_cls)
        if opts.get("weapons", True):
            classes += list(self.weapon_cls)

        if want_people and classes:
            res = self.model.track(
                frame, persist=True, classes=classes, conf=min(SETTINGS["person_conf"], SETTINGS["coco_weapon_conf"]),
                imgsz=SETTINGS["imgsz"], device=e.device, verbose=False, tracker="bytetrack.yaml",
            )[0]
            boxes = res.boxes
            ids = boxes.id.int().tolist() if boxes.id is not None else [None] * len(boxes)
            polys = _polygons(res, len(boxes))
            for xyxy, cls, conf, tid, poly in zip(boxes.xyxy.int().tolist(), boxes.cls.int().tolist(),
                                                  boxes.conf.tolist(), ids, polys):
                if cls in self.weapon_cls:
                    if conf >= SETTINGS["coco_weapon_conf"]:
                        dets.append({"kind": "weapon", "label": self.weapon_cls[cls], "conf": conf,
                                     "box": tuple(xyxy), "contour": poly})
                elif conf >= SETTINGS["person_conf"]:
                    d = {"kind": "person", "label": "person", "conf": conf, "box": tuple(xyxy),
                         "track_id": tid, "contour": poly}
                    if opts.get("colors", True):
                        c = clothing_colors(frame, xyxy, poly)
                        if c:
                            d.update(c)
                    dets.append(d)
            if opts.get("colors", True) and e.clip is not None and SETTINGS.get("clothing", True):
                try:
                    self._update_clothing(frame, [d for d in dets if d["kind"] == "person"])
                except Exception as exc:
                    print(f"[vêtements] erreur : {exc}")

        if opts.get("weapons", True) and e.weapon_model is not None:
            with e.weapon_lock:
                res = e.weapon_model.predict(frame, conf=SETTINGS["weapon_conf"], imgsz=SETTINGS["imgsz"],
                                             device=e.device, verbose=False)[0]
            names = e.weapon_names
            found = [{"kind": "weapon", "label": names[cls], "conf": conf, "box": tuple(xyxy), "contour": None}
                     for xyxy, cls, conf in zip(res.boxes.xyxy.int().tolist(), res.boxes.cls.int().tolist(),
                                                res.boxes.conf.tolist())]
            if found and e.clip is not None and (SETTINGS.get("weapon_types", True) or SETTINGS.get("weapon_verify", True)):
                found = self._check_weapons(frame, found)
            if found and e.sam is not None:
                # Détourage uniquement quand une arme est vue (MobileSAM coûte quelques dizaines de ms)
                try:
                    with e.sam_lock:
                        r = e.sam(frame, bboxes=[list(d["box"]) for d in found], device=e.device, verbose=False)[0]
                    for d, poly in zip(found, _polygons(r, len(found))):
                        d["contour"] = poly
                except Exception as exc:
                    print(f"[armes] détourage impossible : {exc}")
            dets += found

        # Visages : pour la reconnaissance (option de la caméra) ou pour le floutage (vie privée)
        recognize = opts.get("faces", True) and not crowd
        if not crowd and (recognize or SETTINGS.get("blur_unknown_faces")):
            # Les visages coûtent plus cher (CPU) : analysés 1 image sur N, réutilisés entre-temps
            if self._n % max(1, SETTINGS["face_every_n_frames"]) == 0:
                self._last_faces = e.faces.analyze(frame, recognize=recognize)
            dets += self._last_faces
        self._n += 1
        return dets


# --- dessin -------------------------------------------------------------------
COLORS = {"person": (80, 200, 80), "weapon": (0, 0, 255), "face_known": (0, 215, 255), "face": (200, 200, 200)}


def _ascii(s: str) -> str:
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()


def _label(img, text, x, y, color, placed=None):
    text = _ascii(text)
    (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
    y = max(th + 6, y)
    x = max(0, min(x, img.shape[1] - tw - 6))  # reste dans l'image
    if placed is not None:
        # Évite le chevauchement avec les étiquettes déjà posées : on remonte (ou descend en haut d'image)
        def hits(yy):
            return any(x < bx2 and x + tw + 6 > bx1 and yy - th - 6 < by2 and yy > by1
                       for bx1, by1, bx2, by2 in placed)
        step, tries = th + 8, 0
        while hits(y) and tries < 8:
            y = y - step if y - step >= th + 6 else y + step * (tries + 1)
            tries += 1
        placed.append((x, y - th - 6, x + tw + 6, y))
    cv2.rectangle(img, (x, y - th - 6), (x + tw + 6, y), color, -1)
    cv2.putText(img, text, (x + 3, y - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1, cv2.LINE_AA)


def _polygons(result, n):
    """Contours (tableaux de points entiers) d'un résultat Ultralytics, ou None par objet."""
    if result.masks is None:
        return [None] * n
    out = [xy.astype(np.int32) if len(xy) >= 3 else None for xy in result.masks.xy]
    return (out + [None] * n)[:n]


def _contour_mode():
    return SETTINGS.get("draw_style", "contour") == "contour"


def _shape(img, overlay, d, col, thick):
    """Dessine le contour (avec remplissage léger) ou, à défaut, le cadre."""
    x1, y1, x2, y2 = d["box"]
    # Visages : forme réglée à part ("face_shape"), indépendante de "draw_style"
    if d["kind"] == "face" and SETTINGS.get("face_shape", "oval") == "oval":
        center = ((x1 + x2) // 2, (y1 + y2) // 2)
        axes = (max(1, (x2 - x1) // 2), max(1, int((y2 - y1) * 0.6)))
        cv2.ellipse(img, center, axes, 0, 0, 360, col, thick, cv2.LINE_AA)
        return
    if _contour_mode() and d.get("contour") is not None:
        cv2.fillPoly(overlay, [d["contour"]], col)
        cv2.polylines(img, [d["contour"]], True, col, thick, cv2.LINE_AA)
        return
    cv2.rectangle(img, (x1, y1), (x2, y2), col, thick)


def _lang():
    return SETTINGS.get("overlay_lang", "fr")


def _describe(kind, color):
    """« pull bleu », « bleu » (type inconnu) ou « ? », dans la langue des incrustations."""
    parts = [tv(p, _lang()) for p in (kind if kind and kind != "?" else None, color) if p]
    return " ".join(parts) or "?"


def _anchor(d):
    """Point où placer l'étiquette : haut du contour, sinon coin du cadre."""
    c = d.get("contour")
    if c is not None and _contour_mode():
        top = c[c[:, 1].argmin()]
        return int(max(0, top[0] - 20)), int(top[1]) - 4
    return d["box"][0], d["box"][1]


def _blur_faces(img, dets):
    """Pixellise les visages non reconnus ; renvoie les détections restant à dessiner."""
    if not SETTINGS.get("blur_unknown_faces"):
        return dets
    H, W = img.shape[:2]
    keep = []
    for d in dets:
        if d["kind"] == "face" and not d.get("known"):
            x1, y1, x2, y2 = d["box"]
            mx, my = int((x2 - x1) * 0.2), int((y2 - y1) * 0.2)
            x1, y1, x2, y2 = max(0, x1 - mx), max(0, y1 - my), min(W, x2 + mx), min(H, y2 + my)
            roi = img[y1:y2, x1:x2]
            if roi.size:
                small = cv2.resize(roi, (max(1, roi.shape[1] // 12), max(1, roi.shape[0] // 12)),
                                   interpolation=cv2.INTER_LINEAR)
                img[y1:y2, x1:x2] = cv2.resize(small, (roi.shape[1], roi.shape[0]),
                                               interpolation=cv2.INTER_NEAREST)
        else:
            keep.append(d)
    return keep


def _draw_crowd(img, d):
    """Carte de densité, un point par tête et le total en bas à gauche."""
    from .crowd import density_overlay
    pts = d["points"]
    if SETTINGS.get("crowd_heatmap", True) and len(pts):
        img[:] = density_overlay(img, pts)
    r = max(2, img.shape[1] // 640)
    for x, y in pts.astype(int):
        cv2.circle(img, (int(x), int(y)), r, (255, 255, 255), -1, cv2.LINE_AA)
    lang = _lang()
    text = (f"{d['count']} {msg('people_count', lang)}" if d["count"] is not None
            else msg("crowd_model_missing", lang))
    text = _ascii(text)
    scale = max(0.7, img.shape[1] / 1280)
    (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, scale, 2)
    pad = int(10 * scale)
    # En bas à gauche : le haut de l'image porte déjà l'étiquette LIVE / REC de l'interface
    y0 = img.shape[0] - th - 2 * pad
    cv2.rectangle(img, (0, y0), (tw + 2 * pad + 6, img.shape[0]), (12, 7, 4), -1)
    cv2.rectangle(img, (0, y0), (6, img.shape[0]), (255, 229, 0), -1)
    cv2.putText(img, text, (6 + pad, y0 + th + pad), cv2.FONT_HERSHEY_SIMPLEX, scale, (255, 229, 0), 2, cv2.LINE_AA)


def draw(img, dets):
    for d in dets:
        if d["kind"] == "crowd":
            _draw_crowd(img, d)
    dets = _blur_faces(img, dets)  # en premier : le floutage vaut aussi pour les captures du journal
    overlay = img.copy()
    labels = []
    for d in dets:
        x1, y1, x2, y2 = d["box"]
        if d["kind"] == "person":
            col = COLORS["person"]
            text = f"#{d['track_id']}" if d.get("track_id") is not None else tv("person", _lang())
            if "upper" in d or "upper_type" in d:
                text += f" {msg('top', _lang())}:" + _describe(d.get("upper_type"), d.get("upper"))
                text += f" {msg('bottom', _lang())}:" + _describe(d.get("lower_type"), d.get("lower"))
            _shape(img, overlay, d, col, 2)
            labels.append((text, *_anchor(d), col))
        elif d["kind"] == "weapon":
            col = COLORS["weapon"]
            _shape(img, overlay, d, col, 3)
            labels.append((f"{msg('weapon', _lang())}: {tv(d['label'], _lang())} {d['conf']:.0%}", *_anchor(d), col))
        elif d["kind"] == "face":
            col = COLORS["face_known"] if d.get("known") else COLORS["face"]
            _shape(img, overlay, d, col, 2)
            text = f"{d['label']} {d['conf']:.2f}" if d.get("known") else tv(d["label"], _lang())
            labels.append((text, x1, y2 + 18, col))
    if _contour_mode() and any(d.get("contour") is not None for d in dets):
        cv2.addWeighted(overlay, 0.25, img, 0.75, 0, dst=img)  # remplissage translucide
    placed = []
    for text, x, y, col in labels:  # étiquettes dessinées en dernier, bien lisibles
        _label(img, text, x, y, col, placed)
    return img
