"""Couleur dominante d'une zone de vêtement et nom de couleur (clé neutre, traduite à l'affichage)."""
import cv2
import numpy as np

COLOR_NAMES = ["black", "gray", "white", "red", "orange", "yellow", "beige",
               "brown", "green", "cyan", "blue", "purple", "pink"]

_KMEANS_CRITERIA = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0)


def dominant_bgr(region: np.ndarray):
    """Couleur majoritaire (k-means, 3 groupes) d'une zone BGR."""
    if region is None or region.size == 0 or min(region.shape[:2]) < 4:
        return None
    small = cv2.resize(region, (24, 24), interpolation=cv2.INTER_AREA)
    return _kmeans_major(small.reshape(-1, 3))


def _kmeans_major(pixels: np.ndarray):
    """Couleur majoritaire d'une liste de pixels BGR (N x 3)."""
    if len(pixels) > 600:  # sous-échantillonnage régulier : assez précis, beaucoup plus rapide
        pixels = pixels[np.linspace(0, len(pixels) - 1, 600).astype(int)]
    data = pixels.astype(np.float32)
    _, labels, centers = cv2.kmeans(data, 3, None, _KMEANS_CRITERIA, 2, cv2.KMEANS_PP_CENTERS)
    counts = np.bincount(labels.flatten(), minlength=3)
    return tuple(int(x) for x in centers[counts.argmax()])


def color_name(bgr) -> str:
    hsv = cv2.cvtColor(np.uint8([[bgr]]), cv2.COLOR_BGR2HSV)[0, 0]
    h, s, v = int(hsv[0]) * 2, hsv[1] / 255.0, hsv[2] / 255.0
    # Sombre : noir sauf si la teinte reste nette (ex. jean bleu foncé)
    if v < 0.12 or (v < 0.30 and s < 0.40):
        return "black"
    if s < 0.20:
        return "white" if v > 0.78 else "gray"
    if 20 <= h <= 50 and s < 0.40 and v > 0.60:
        return "beige"
    if 10 <= h < 45 and v < 0.60:
        return "brown"
    if h < 15 or h >= 340:
        return "red"
    if h < 40:
        return "orange"
    if h < 70:
        return "yellow"
    if h < 165:
        return "green"
    if h < 195:
        return "cyan"
    if h < 260:
        return "blue"
    if h < 290:
        return "purple"
    return "pink"


MIN_MASK_PIXELS = 40


def clothing_colors(frame: np.ndarray, box, contour=None):
    """Renvoie (haut, bas) pour une personne : noms + couleurs BGR.

    Avec le contour de la silhouette, seuls les pixels de la personne comptent (pas le décor).
    Sans contour, on prend le centre du cadre.
    """
    x1, y1, x2, y2 = box
    x1, y1 = max(0, x1), max(0, y1)
    w, h = x2 - x1, y2 - y1
    if w < 12 or h < 30:
        return None
    bands = {"upper": (0.20, 0.50), "lower": (0.55, 0.88)}
    mask = None
    if contour is not None and len(contour) >= 3:
        mask = np.zeros((h, w), np.uint8)
        cv2.fillPoly(mask, [(contour - [x1, y1]).astype(np.int32)], 255)
    out = {}
    for key, (a, b) in bands.items():
        ya, yb = y1 + int(h * a), y1 + int(h * b)
        color = None
        if mask is not None:
            region = frame[ya:yb, x1:x2]
            m = mask[ya - y1: ya - y1 + region.shape[0], :region.shape[1]]
            pix = region[m > 0]
            if len(pix) >= MIN_MASK_PIXELS:
                color = _kmeans_major(pix)
        if color is None:  # pas de masque exploitable : centre du cadre
            color = dominant_bgr(frame[ya:yb, x1 + int(w * 0.25): x2 - int(w * 0.25)])
        out[key] = color
    ub, lb = out["upper"], out["lower"]
    if ub is None or lb is None:
        return None
    return {"upper": color_name(ub), "lower": color_name(lb), "upper_bgr": ub, "lower_bgr": lb}
