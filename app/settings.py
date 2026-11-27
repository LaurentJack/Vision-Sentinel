"""Réglages de l'application (fichier settings.json dans le dossier de données, créé au premier lancement).

Emplacements :
- développement (start.bat) : modèles dans ./models, données dans ./data ;
- application installée (.exe) : modèles à côté du programme (lecture seule),
  données dans %LOCALAPPDATA%\\VisionSentinel (modifiables, conservées lors des mises à jour).
La variable d'environnement VS_DATA_DIR permet de choisir un autre dossier de données.
"""
import json
import os
import sys
from pathlib import Path

from .i18n import LANGS, UserError

FROZEN = getattr(sys, "frozen", False)  # True dans l'exécutable PyInstaller
ROOT = Path(sys.executable).parent if FROZEN else Path(__file__).resolve().parent.parent
MODELS = ROOT / "models"
if os.environ.get("VS_DATA_DIR"):
    DATA = Path(os.environ["VS_DATA_DIR"])
elif FROZEN:
    DATA = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "VisionSentinel"
else:
    DATA = ROOT / "data"
FACES = DATA / "faces"
SNAPSHOTS = DATA / "snapshots"
LOGS = DATA / "logs"
for d in (DATA, FACES, SNAPSHOTS, LOGS):
    d.mkdir(parents=True, exist_ok=True)
if not FROZEN:
    MODELS.mkdir(exist_ok=True)

DEFAULTS = {
    # "auto" = GPU si disponible, sinon CPU. Ou "cpu", "cuda:0"...
    "device": "auto",
    # Modèle YOLO général (personnes + couteaux, ciseaux, battes du jeu COCO)
    "person_model": "yolo11n-seg.pt",
    # Affichage : "contour" (silhouette des objets) ou "box" (carrés)
    "draw_style": "contour",
    # Forme autour des visages : "oval" ou "box" (indépendant de draw_style)
    "face_shape": "oval",
    # Détourage des armes du modèle spécialisé (utilisé seulement en mode "contour")
    "sam_model": "mobile_sam.pt",
    # Modèle YOLO spécialisé armes (pistolets, fusils, couteaux...) : optionnel
    "weapon_model": "weapons.pt",
    "imgsz": 640,
    "person_conf": 0.40,
    "coco_weapon_conf": 0.45,
    "weapon_conf": 0.45,
    # Type d'arme (pistolet, fusil...) et vérification des alertes par CLIP
    "weapon_types": True,
    "weapon_type_min_conf": 0.4,      # en dessous : nom générique (« arme à feu »)
    "weapon_types_list": {},          # vide = liste par défaut (app/clip.py)
    "weapon_verify": True,            # écarte téléphones, bouteilles... pris pour une arme
    "weapon_verify_threshold": 0.6,   # probabilité « objet anodin » au-delà de laquelle l'alerte est écartée
    # Renommage des classes du modèle d'armes, ex. {"0": "arme à feu"}
    "weapon_labels": {"0": "firearm"},  # le modèle d'armes fourni n'a qu'une classe, nommée « 0 »
    # Seuil de similarité cosinus SFace (0.363 = valeur conseillée par OpenCV)
    "face_match_threshold": 0.40,
    # Largeur d'image pour la détection de visages (plus grand = visages lointains, mais plus lent)
    "face_det_width": 640,
    "face_every_n_frames": 2,
    # Type de vêtements (CLIP). Listes modifiables : {"nom affiché": "description anglaise"}
    "clothing": True,
    "clothing_upper": {},          # vide = liste par défaut (app/clothing.py)
    "clothing_lower": {},
    "clothing_min_conf": 0.35,     # en dessous : « ? »
    "clothing_refresh_s": 8,       # recalcul par personne suivie
    "clothing_min_height": 90,     # taille minimale de la personne (pixels)
    "clothing_per_frame": 2,
    # Comptage de foule (caméras en mode « foule / drone ») : un point par tête, modèle entraîné par
    # train_crowd.py. Agrandir l'image (crowd_scale > 1) aide quand les têtes font moins de ~8 pixels.
    "crowd_model": "crowd.pth",
    "crowd_threshold": 0.5,        # confiance minimale d'un point ; plus bas = compte plus de monde
    "crowd_scale": 1.0,
    "crowd_heatmap": True,         # carte de densité incrustée dans la vidéo
    "max_fps": 15,
    "weapon_cooldown_s": 10,
    "face_cooldown_s": 30,
    "zone_cooldown_s": 60,         # délai entre deux alertes « zone trop pleine »
    "log_unknown_faces": False,
    # --- Vie privée / RGPD ---
    "face_recognition": True,      # identification des personnes enregistrées (donnée biométrique)
    "blur_unknown_faces": False,   # floute les visages non reconnus (direct et captures)
    "retention_days": 30,          # suppression auto du journal et des captures (0 = jamais)
    "privacy_ack": None,           # date de prise de connaissance de l'avertissement RGPD
    "overlay_lang": "fr",          # langue des textes incrustés dans la vidéo (fr, nl, en)
    # --- Enregistrement vidéo (mode par caméra : off, alerts, people, continuous) ---
    "recording_pre_s": 10,         # secondes gardées en mémoire avant une alerte
    "recording_post_s": 30,        # secondes enregistrées après la dernière alerte
    "recording_fps": 10,           # images par seconde des vidéos
    "recording_width": 1280,       # largeur maximale des vidéos (pixels)
    "recording_crf": 26,           # qualité H.264 (plus bas = meilleure qualité, fichiers plus gros)
    "recording_max_gb": 50,        # espace disque maximal (0 = sans limite) ; les plus anciennes partent
    "recording_overlay": True,     # date, heure et nom de caméra incrustés dans la vidéo
    # Application installée (.exe) : adresse du serveur. "127.0.0.1" = ce PC seulement ;
    # "0.0.0.0" = accessible depuis le réseau (attention : aucune protection par mot de passe).
    "server_host": "127.0.0.1",
    "server_port": 8000,
}

# Réglages modifiables depuis l'interface : (type, choix possibles ou (min, max))
EDITABLE = {
    "device": (str, ["auto", "cuda:0", "cpu"]),
    "draw_style": (str, ["box", "contour"]),
    "face_shape": (str, ["oval", "box"]),
    "max_fps": (int, (1, 30)),
    "person_conf": (float, (0.1, 0.95)),
    "weapon_conf": (float, (0.1, 0.95)),
    "coco_weapon_conf": (float, (0.1, 0.95)),
    "face_match_threshold": (float, (0.2, 0.9)),
    "weapon_cooldown_s": (int, (1, 3600)),
    "face_cooldown_s": (int, (1, 3600)),
    "crowd_threshold": (float, (0.2, 0.9)),
    "crowd_scale": (float, (0.5, 4.0)),
    "crowd_heatmap": (bool, None),
    "clothing": (bool, None),
    "weapon_types": (bool, None),
    "weapon_verify": (bool, None),
    "weapon_verify_threshold": (float, (0.3, 0.95)),
    "clothing_min_conf": (float, (0.1, 0.9)),
    "face_recognition": (bool, None),
    "blur_unknown_faces": (bool, None),
    "log_unknown_faces": (bool, None),
    "retention_days": (int, (0, 3650)),
    "privacy_ack": (str, None),
    "overlay_lang": (str, list(LANGS)),
    "recording_pre_s": (int, (0, 60)),
    "recording_post_s": (int, (5, 600)),
    "recording_fps": (int, (2, 25)),
    "recording_width": (int, (480, 3840)),
    "recording_max_gb": (int, (0, 100000)),
    "recording_overlay": (bool, None),
}
# Ces réglages demandent de recharger les modèles
RELOAD_KEYS = {"device", "draw_style", "clothing", "weapon_types", "weapon_verify"}

_path = DATA / "settings.json"


def load() -> dict:
    cfg = dict(DEFAULTS)
    if _path.exists():
        try:
            cfg.update(json.loads(_path.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            pass
    else:
        _path.write_text(json.dumps(DEFAULTS, indent=2, ensure_ascii=False), encoding="utf-8")
    return cfg


SETTINGS = load()


def save():
    _path.write_text(json.dumps(SETTINGS, indent=2, ensure_ascii=False), encoding="utf-8")


def validate(changes: dict) -> dict:
    """Garde uniquement les réglages connus, au bon type et dans les bornes."""
    clean = {}
    for key, value in changes.items():
        if key not in EDITABLE:
            raise UserError("unknown_setting", key=key)
        typ, rule = EDITABLE[key]
        if value is None and key == "privacy_ack":
            clean[key] = None
            continue
        if typ is bool:
            if not isinstance(value, bool):
                raise UserError("bool_expected", key=key)
        elif typ in (int, float):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise UserError("number_expected", key=key)
            value = typ(value)
            lo, hi = rule
            if not lo <= value <= hi:
                raise UserError("out_of_range", key=key, lo=lo, hi=hi)
        elif typ is str:
            if not isinstance(value, str) or (rule and value not in rule):
                raise UserError("invalid_value", key=key)
        clean[key] = value
    return clean
