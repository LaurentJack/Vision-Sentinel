"""Classification par comparaison image / texte avec CLIP (aucun entraînement).

Sert à deux choses :
- le type de vêtements (jean, chemise, pull...) d'une personne ;
- le type d'arme détectée (pistolet, fusil...) et l'écartement des fausses alertes
  (téléphone, bouteille... pris pour une arme par le détecteur).

Les descriptions sont en anglais (CLIP les comprend mieux) et affichées en français.
Les listes se modifient dans data/settings.json.
"""
import threading

import cv2
import numpy as np

from .settings import MODELS, SETTINGS

# Clés neutres (traduites à l'affichage, voir app/i18n.py) -> description anglaise pour CLIP
DEFAULT_UPPER = {
    "tshirt": "a t-shirt",
    "shirt": "a button-up shirt",
    "sweater": "a knitted sweater",
    "hoodie": "a hoodie",
    "jacket": "a jacket",
    "coat": "a long coat",
    "suit": "a suit jacket",
    "tank_top": "a tank top",
    "dress": "a dress",
}
DEFAULT_LOWER = {
    "jeans": "denim jeans",
    "trousers": "trousers",
    "sweatpants": "sweatpants",
    "shorts": "shorts",
    "skirt": "a skirt",
    "dress": "a dress",
}
# Testé sur 865 armes d'Open Images : 76 % des pistolets et 94 % des fusils classés dans la bonne
# famille (arme de poing / arme d'épaule). « pistolet-mitrailleur » a été retiré : il captait les pistolets.
DEFAULT_WEAPONS = {
    "handgun": "a handgun pistol",
    "revolver": "a revolver",
    "assault_rifle": "an assault rifle",
    "hunting_rifle": "a hunting rifle or a shotgun",
    "sniper_rifle": "a sniper rifle",
}
# Objets souvent pris pour une arme : s'ils l'emportent, l'alerte est écartée
NOT_WEAPONS = {
    "_phone": "a mobile phone",
    "_bottle": "a bottle or a can",
    "_tool": "a tool",
    "_umbrella": "an umbrella",
    "_object": "an everyday object",
}
CLOTHING_TEMPLATES = [
    "a photo of a person wearing {}.",
    "a cropped photo of {} worn by a person.",
    "a surveillance camera image of someone wearing {}.",
]
OBJECT_TEMPLATES = [
    "a photo of {}.",
    "a cropped photo of {}.",
    "a surveillance camera image of {}.",
]


class ClipClassifier:
    def __init__(self, device: str):
        import open_clip
        import torch
        self.torch = torch
        self.device = device
        self.lock = threading.Lock()
        name = SETTINGS.get("clip_model", "ViT-B-32")
        # Version installée : fichier de poids local (aucun accès Internet). Sinon : cache Hugging Face.
        local = MODELS / "clip_vit_b32.safetensors"
        pretrained = str(local) if local.exists() and name == "ViT-B-32" else SETTINGS.get("clip_pretrained", "laion2b_s34b_b79k")
        self.model, _, _ = open_clip.create_model_and_transforms(
            name, pretrained=pretrained, cache_dir=str(MODELS / "clip"), device=device)
        self.model.eval()
        tok = open_clip.get_tokenizer(name)
        self.upper_names, self.upper_text = self._encode(SETTINGS.get("clothing_upper") or DEFAULT_UPPER,
                                                         CLOTHING_TEMPLATES, tok)
        self.lower_names, self.lower_text = self._encode(SETTINGS.get("clothing_lower") or DEFAULT_LOWER,
                                                         CLOTHING_TEMPLATES, tok)
        weapons = SETTINGS.get("weapon_types_list") or DEFAULT_WEAPONS
        self.n_weapon_types = len(weapons)
        self.weapon_names, self.weapon_text = self._encode({**weapons, **NOT_WEAPONS}, OBJECT_TEMPLATES, tok)
        # Normalisation CLIP faite sur GPU (plus rapide que la transformation PIL)
        self.mean = torch.tensor([0.48145466, 0.4578275, 0.40821073], device=device).view(1, 3, 1, 1)
        self.std = torch.tensor([0.26862954, 0.26130258, 0.27577711], device=device).view(1, 3, 1, 1)
        print(f"[CLIP] prêt : vêtements {self.upper_names} / {self.lower_names} ; "
              f"armes {self.weapon_names[:self.n_weapon_types]}")

    def _encode(self, mapping: dict, templates, tokenizer):
        names = list(mapping)
        with self.torch.no_grad():
            feats = []
            for fr in names:
                f = self.model.encode_text(tokenizer([t.format(mapping[fr]) for t in templates]).to(self.device))
                f = (f / f.norm(dim=-1, keepdim=True)).mean(0)
                feats.append(f / f.norm())
        return names, self.torch.stack(feats)

    def _embed(self, crops):
        batch = [cv2.cvtColor(cv2.resize(c, (224, 224), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2RGB)
                 for c in crops]
        t = self.torch.from_numpy(np.stack(batch)).to(self.device).permute(0, 3, 1, 2).float() / 255.0
        with self.lock, self.torch.no_grad():
            f = self.model.encode_image((t - self.mean) / self.std)
            return f / f.norm(dim=-1, keepdim=True)

    def _probs(self, img_feats, text):
        return (100.0 * img_feats @ text.T).softmax(-1).cpu().numpy()

    # --- vêtements ---------------------------------------------------------------
    def classify_clothing(self, frame, boxes):
        """Pour chaque cadre de personne : {upper_type, upper_type_conf, lower_type, lower_type_conf}."""
        crops, idx = [], []
        H, W = frame.shape[:2]
        for i, (x1, y1, x2, y2) in enumerate(boxes):
            h = y2 - y1
            pad = int((x2 - x1) * 0.08)
            xa, xb = max(0, x1 - pad), min(W, x2 + pad)
            up = frame[max(0, y1 + int(h * 0.12)): min(H, y1 + int(h * 0.58)), xa:xb]
            lo = frame[max(0, y1 + int(h * 0.48)): min(H, y1 + int(h * 0.98)), xa:xb]
            if up.size and lo.size:
                crops += [up, lo]
                idx.append(i)
        out = [None] * len(boxes)
        if not crops:
            return out
        min_conf = SETTINGS.get("clothing_min_conf", 0.35)
        f = self._embed(crops)
        pu, pl = self._probs(f[0::2], self.upper_text), self._probs(f[1::2], self.lower_text)
        for k, i in enumerate(idx):
            ju, jl = int(pu[k].argmax()), int(pl[k].argmax())
            out[i] = {
                "upper_type": self.upper_names[ju] if pu[k][ju] >= min_conf else "?",
                "upper_type_conf": float(pu[k][ju]),
                "lower_type": self.lower_names[jl] if pl[k][jl] >= min_conf else "?",
                "lower_type_conf": float(pl[k][jl]),
            }
        return out

    # --- armes ---------------------------------------------------------------------
    def classify_weapons(self, frame, boxes):
        """Pour chaque cadre d'arme : {type, type_conf, not_weapon} (not_weapon = probabilité d'un objet anodin)."""
        H, W = frame.shape[:2]
        crops, idx = [], []
        for i, (x1, y1, x2, y2) in enumerate(boxes):
            px, py = int((x2 - x1) * 0.1), int((y2 - y1) * 0.1)
            c = frame[max(0, y1 - py):min(H, y2 + py), max(0, x1 - px):min(W, x2 + px)]
            if c.size and min(c.shape[:2]) >= 8:
                crops.append(c)
                idx.append(i)
        out = [None] * len(boxes)
        if not crops:
            return out
        p = self._probs(self._embed(crops), self.weapon_text)
        n = self.n_weapon_types
        for k, i in enumerate(idx):
            types = p[k][:n] / max(1e-6, p[k][:n].sum())  # répartition entre types d'armes seulement
            j = int(types.argmax())
            out[i] = {"type": self.weapon_names[j], "type_conf": float(types[j]),
                      "not_weapon": float(p[k][n:].sum())}
        return out
