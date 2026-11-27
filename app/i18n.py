"""Traductions côté serveur (français, néerlandais, anglais).

Les valeurs détectées (couleurs, vêtements, armes) sont enregistrées sous une clé neutre
(« blue », « jeans », « handgun ») et traduites seulement à l'affichage : le journal reste
cherchable quelle que soit la langue choisie.
"""

LANGS = ("fr", "nl", "en")
DEFAULT_LANG = "fr"

# clé neutre -> (français, néerlandais, anglais)
VALUES = {
    # couleurs
    "black": ("noir", "zwart", "black"),
    "gray": ("gris", "grijs", "grey"),
    "white": ("blanc", "wit", "white"),
    "red": ("rouge", "rood", "red"),
    "orange": ("orange", "oranje", "orange"),
    "yellow": ("jaune", "geel", "yellow"),
    "beige": ("beige", "beige", "beige"),
    "brown": ("marron", "bruin", "brown"),
    "green": ("vert", "groen", "green"),
    "cyan": ("cyan", "cyaan", "cyan"),
    "blue": ("bleu", "blauw", "blue"),
    "purple": ("violet", "paars", "purple"),
    "pink": ("rose", "roze", "pink"),
    # vêtements (haut)
    "tshirt": ("t-shirt", "T-shirt", "T-shirt"),
    "shirt": ("chemise", "hemd", "shirt"),
    "sweater": ("pull", "trui", "sweater"),
    "hoodie": ("sweat à capuche", "hoodie", "hoodie"),
    "jacket": ("veste", "jack", "jacket"),
    "coat": ("manteau", "jas", "coat"),
    "suit": ("costume", "kostuum", "suit jacket"),
    "tank_top": ("débardeur", "topje", "tank top"),
    "dress": ("robe", "jurk", "dress"),
    # vêtements (bas)
    "jeans": ("jean", "jeans", "jeans"),
    "trousers": ("pantalon", "broek", "trousers"),
    "sweatpants": ("jogging", "joggingbroek", "sweatpants"),
    "shorts": ("short", "short", "shorts"),
    "skirt": ("jupe", "rok", "skirt"),
    # armes
    "firearm": ("arme à feu", "vuurwapen", "firearm"),
    "handgun": ("pistolet", "pistool", "handgun"),
    "revolver": ("revolver", "revolver", "revolver"),
    "assault_rifle": ("fusil d'assaut", "aanvalsgeweer", "assault rifle"),
    "hunting_rifle": ("fusil de chasse", "jachtgeweer", "hunting rifle"),
    "sniper_rifle": ("fusil de précision", "precisiegeweer", "sniper rifle"),
    "knife": ("couteau", "mes", "knife"),
    "scissors": ("ciseaux", "schaar", "scissors"),
    "baseball_bat": ("batte", "knuppel", "baseball bat"),
    # divers
    "person": ("personne", "persoon", "person"),
    "unknown": ("Inconnu", "Onbekend", "Unknown"),
}

# Textes du serveur : incrustations vidéo et messages d'erreur
MESSAGES = {
    "top": ("haut", "boven", "top"),
    "bottom": ("bas", "onder", "bottom"),
    "weapon": ("ARME", "WAPEN", "WEAPON"),
    "in": ("entrées", "in", "in"),
    "people_count": ("personnes", "personen", "people"),
    "crowd_model_missing": ("Modèle de foule absent (models/crowd.pth, voir train_crowd.py)",
                            "Menigtemodel ontbreekt (models/crowd.pth, zie train_crowd.py)",
                            "Crowd model missing (models/crowd.pth, see train_crowd.py)"),
    "out": ("sorties", "uit", "out"),
    "no_recording": ("Aucun enregistrement à ce moment-là.", "Geen opname op dat moment.", "No recording at that time."),
    "recording_busy": ("Ce segment est en cours d'enregistrement.", "Dit segment wordt nog opgenomen.",
                       "This segment is still being recorded."),
    "invalid_areas": ("Zones ou lignes invalides.", "Ongeldige zones of lijnen.", "Invalid zones or lines."),
    "connecting": ("Connexion...", "Verbinden...", "Connecting..."),
    "offline_retry": ("Hors ligne - nouvel essai...", "Offline - nieuwe poging...", "Offline - retrying..."),
    "unknown_camera": ("Caméra inconnue", "Onbekende camera", "Unknown camera"),
    "reloading": ("Rechargement des modèles en cours, réessayez dans un instant.",
                  "De modellen worden opnieuw geladen, probeer het zo dadelijk opnieuw.",
                  "Models are reloading, please try again in a moment."),
    "face_models_missing": ("Modèles de visage absents (lancez download_models.py).",
                            "Gezichtsmodellen ontbreken (start download_models.py).",
                            "Face models are missing (run download_models.py)."),
    "invalid_name": ("Nom invalide.", "Ongeldige naam.", "Invalid name."),
    "unreadable_image": ("Image illisible.", "Onleesbare afbeelding.", "Unreadable image."),
    "no_face": ("Aucun visage détecté sur cette photo.", "Geen gezicht gevonden op deze foto.",
                "No face found in this photo."),
    "unknown_setting": ("Réglage inconnu : {key}", "Onbekende instelling: {key}", "Unknown setting: {key}"),
    "bool_expected": ("{key} : oui/non attendu", "{key}: ja/nee verwacht", "{key}: yes/no expected"),
    "number_expected": ("{key} : nombre attendu", "{key}: getal verwacht", "{key}: number expected"),
    "out_of_range": ("{key} : doit être entre {lo} et {hi}", "{key}: moet tussen {lo} en {hi} liggen",
                     "{key}: must be between {lo} and {hi}"),
    "invalid_value": ("{key} : valeur invalide", "{key}: ongeldige waarde", "{key}: invalid value"),
}


class UserError(Exception):
    """Erreur à montrer à l'utilisateur, traduite dans sa langue par le serveur web."""

    def __init__(self, code: str, status: int = 400, **params):
        super().__init__(code)
        self.code, self.status, self.params = code, status, params


def _idx(lang):
    return LANGS.index(lang) if lang in LANGS else 0


def tv(key, lang=DEFAULT_LANG):
    """Nom affiché d'une valeur neutre ; une valeur inconnue (liste personnalisée, nom) reste telle quelle."""
    if key is None:
        return None
    names = VALUES.get(key)
    return names[_idx(lang)] if names else key


def msg(code, lang=DEFAULT_LANG, **params):
    texts = MESSAGES.get(code)
    return (texts[_idx(lang)] if texts else code).format(**params)


def pick_lang(header: str | None):
    """Langue d'une requête (en-tête X-Lang envoyé par l'interface)."""
    lang = (header or "").lower()[:2]
    return lang if lang in LANGS else DEFAULT_LANG


# nom affiché (toutes langues, minuscules) -> clé neutre ; sert aux conversions et à la recherche
_REVERSE = {}
for _key, _names in VALUES.items():
    for _n in _names:
        _REVERSE.setdefault(_n.lower(), _key)


def to_key(name):
    """« bleu », « blauw » ou « blue » -> « blue ». Renvoie le nom tel quel s'il est inconnu."""
    if name is None:
        return None
    return _REVERSE.get(name.lower(), name)


def search_terms(text: str):
    """Termes à chercher dans le journal : le texte lui-même + les clés dont un nom le contient."""
    text = text.strip().lower()
    keys = {k for n, k in _REVERSE.items() if text in n}
    return [text] + sorted(keys)
