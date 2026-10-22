# Vision Sentinel

Application locale de vidéosurveillance pour Windows : plusieurs caméras (IP RTSP/HTTP, USB, fichiers)
avec analyse en temps réel sur GPU NVIDIA (ou CPU). Tout reste sur votre PC : aucun service en ligne.

- **Détection d'armes** : armes à feu (avec leur type : pistolet, revolver, fusils…) et armes blanches,
  alerte sonore, capture et journal, filtre anti-fausses alertes (téléphones, bouteilles…).
- **Vêtements** : type (jean, pull, veste…) et couleur du haut et du bas de chaque personne suivie,
  avec recherche dans le journal.
- **Reconnaissance faciale** à partir d'une galerie de photos, ou **floutage** des visages inconnus.
- **Comptage** : personnes présentes dans une zone dessinée, passages d'une ligne dans chaque sens.
- Interface en **français, néerlandais et anglais** ; rappels RGPD / loi caméras belge intégrés.

> ⚠️ Usage responsable : la vidéosurveillance et surtout la reconnaissance faciale sont strictement
> encadrées (voir [Cadre légal](#cadre-légal-belgique--ue)). Aucune détection n'est fiable à 100 % :
> gardez toujours une personne pour valider les alertes.

## Démarrage (depuis le code source)

Prérequis : Windows 10/11, Python 3.11, de préférence une carte NVIDIA.

Double-cliquez sur `start.bat` (la première fois, il installe tout et télécharge les modèles, environ 4 Go),
puis ouvrez <http://localhost:8000>.

Ou manuellement :

```bash
python -m venv .venv
.venv\Scripts\python -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu126
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python download_models.py
.venv\Scripts\python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Comptage : zones et lignes

Bouton **Zones** sous chaque caméra : l'image actuelle s'ouvre et on y dessine à la souris.

- **Zone** (« + Zone », cliquer les coins, cliquer le premier point ou Entrée pour fermer) : nombre de
  personnes présentes à l'intérieur et maximum atteint. Option « Alerte au-delà de N personnes » :
  alerte « Zone trop pleine » avec capture dans le journal (au plus une par minute, `zone_cooldown_s`).
- **Ligne** (« + Ligne », deux clics) : passages comptés dans chaque sens. La flèche indique le sens
  compté comme « entrée » ; « Inverser le sens » la retourne.
- Une personne est repérée par **ses pieds** (bas de son cadre) : tracez zones et lignes au sol, et
  faites aller les lignes jusqu'aux bords du passage.
- Les compteurs s'affichent sous la caméra et sur la vidéo ; « Remettre à zéro » dans l'éditeur.
  Ils sont sauvegardés toutes les 30 s dans `data/counters.json` et survivent à un redémarrage.
- Le comptage fonctionne même si vêtements et armes sont désactivés sur la caméra. Comme il s'appuie
  sur le suivi des personnes, une foule dense ou une personne longtemps cachée peut fausser un passage.

## Langues

L'interface existe en **français, néerlandais et anglais** : sélecteur « Langue » en haut à droite,
mémorisé par navigateur (deux personnes peuvent utiliser deux langues différentes). Au premier
lancement, la langue du navigateur est utilisée.

- Les textes incrustés dans la vidéo et dans les captures du journal ont leur propre réglage
  (Paramètres > « Langue des textes sur la vidéo »), commun à tous.
- Le journal enregistre les couleurs, vêtements et armes sous une forme neutre (`blue`, `jeans`,
  `handgun`) traduite à l'affichage : la recherche fonctionne dans les trois langues (« pistool »,
  « pistolet » et « handgun » trouvent les mêmes alertes).
- Traductions : `app/static/i18n.js` (interface) et `app/i18n.py` (valeurs, vidéo, messages d'erreur).
  Les textes néerlandais et anglais de l'avertissement RGPD méritent une relecture par un locuteur natif.

## Version installable (Windows)

**Téléchargement** : page [Releases](https://github.com/LaurentJack/Vision-Sentinel/releases). L'installateur
(environ 3,3 Go) est découpé en morceaux de moins de 2 Go : téléchargez **les trois fichiers**
(`VisionSentinel-Setup-1.0.0.exe`, `-1.bin`, `-2.bin`) **dans le même dossier**, puis lancez le `.exe`.
`SHA256SUMS.txt` permet de vérifier les téléchargements. L'installateur n'est pas signé : Windows
SmartScreen affiche « éditeur inconnu » (« Informations complémentaires » > « Exécuter quand même »).

Il installe l'application pour l'utilisateur courant (pas de droits administrateur), dans
`%LOCALAPPDATA%\Programs\VisionSentinel`, avec raccourcis Bureau / menu Démarrer.

- **Pré-requis du PC** : Windows 10/11 64 bits, composant WebView2 (présent sur Windows 11 et la plupart des
  Windows 10 ; l'installateur vérifie), pilote NVIDIA récent pour le GPU. Sans carte NVIDIA, le calcul passe
  sur le CPU (plus lent). Ni Python ni CUDA ne sont nécessaires.
- **Fenêtre native** : l'application s'ouvre dans sa propre fenêtre ; la fermer arrête les caméras.
  Relancer l'application quand elle tourne déjà ouvre simplement une deuxième fenêtre.
- **Données** : `%LOCALAPPDATA%\VisionSentinel` (caméras, journal, captures, visages, réglages, compteurs,
  journal technique `logs\vision-sentinel.log`). Conservées lors d'une mise à jour ; la désinstallation
  propose de les supprimer.
- **Accès réseau** : par défaut, seulement depuis ce PC. Pour y accéder depuis un autre poste, mettre
  `"server_host": "0.0.0.0"` dans `settings.json` (attention : aucune protection par mot de passe).
- **Diagnostic** : `VisionSentinel.exe --diagnostic [source]` écrit l'état du GPU et de la lecture vidéo
  dans le journal technique.

Reconstruire : `packaging\build.bat` (PyInstaller, copie des modèles, puis Inno Setup 6).

## Sources de caméra

| Type | Exemple |
|---|---|
| Webcam USB / intégrée | `0`, `1`… |
| Caméra IP RTSP | `rtsp://utilisateur:motdepasse@192.168.1.20:554/stream1` |
| Flux HTTP / MJPEG | `http://192.168.1.21/video.mjpg` |
| Fichier vidéo (lu en boucle) | `C:\videos\test.mp4` |

L'URL RTSP exacte dépend de la marque (Hikvision : `/Streaming/Channels/101`, Dahua : `/cam/realmonitor?channel=1&subtype=0`, Reolink : `/h264Preview_01_main`…).
Préférez le sous-flux (résolution plus basse) si vous avez beaucoup de caméras.

## Détection d'armes

- **Armes blanches** (couteaux, ciseaux, battes) : modèle général YOLO11 (jeu COCO).
- **Armes à feu** : `models/weapons.pt`, téléchargé par `download_models.py` depuis
  [Zcket/gun_dtct](https://huggingface.co/Zcket/gun_dtct) (YOLOv8, licence MIT). Un fichier `.pt` pouvant
  contenir du code, le script n'accepte que la version analysée (empreinte SHA-256 vérifiée).
  Mesuré sur 940 images de validation Open Images (seuil 0,5) : alerte sur 90 % des images contenant une
  arme à feu, fausses alertes sur 11 % des images sans arme, surtout des téléphones, ramenées à 0 sur
  cet échantillon par la vérification ci-dessous.

Pour utiliser votre propre modèle : remplacez `models/weapons.pt` par un modèle YOLOv8/YOLO11. Pour en
entraîner un : `tools/prepare_openimages.py` construit un jeu de données (pistolets, fusils, armes
blanches + images sans arme) depuis Open Images, puis `train_weapons.py chemin\vers\data.yaml`.

### Type d'arme et vérification des alertes

Chaque arme à feu détectée est ensuite examinée par CLIP (le même modèle que pour les vêtements) :

- **Type** : pistolet, revolver, fusil d'assaut, fusil de chasse, fusil de précision. Mesuré sur 865 armes
  d'Open Images : 76 % des pistolets et 94 % des fusils classés dans la bonne famille (arme de poing / arme
  d'épaule). La distinction fine (pistolet ou revolver, fusil d'assaut ou de précision) n'a pas été mesurée.
  Si CLIP hésite, l'alerte garde le nom générique « arme à feu ».
- **Vérification** : si la zone ressemble plutôt à un téléphone, une bouteille, un outil ou un parapluie,
  l'alerte est écartée. Mesuré : 15 fausses alertes sur 15 écartées, 2 % des vraies armes perdues.
- Une alerte liste tous les types vus dans l'image (ex. « fusil d'assaut, pistolet ») ; la recherche par
  nom les retrouve.

Ces deux options se règlent dans l'onglet **Paramètres** (Détection). La liste des types se modifie dans
`data/settings.json` (`weapon_types_list`, ex. `{"pistolet": "a handgun pistol", ...}`).

> Aucune détection d'armes n'est fiable à 100 % (faux positifs sur téléphones, outils, ombres). Gardez un humain dans la boucle.

## Reconnaissance faciale

Onglet **Visages** : ajoutez un nom + une photo nette de face (plusieurs photos par personne = meilleurs résultats).
Les photos sont stockées dans `data/faces/<nom>/`. Le seuil se règle dans `data/settings.json` (`face_match_threshold`, plus haut = plus strict).

## Réglages

La plupart des réglages se changent dans l'onglet **Paramètres** de l'interface (CPU/GPU, vie privée,
seuils, affichage). Passer du CPU au GPU, changer l'affichage ou activer les vêtements recharge les modèles
(une vingtaine de secondes) sans redémarrer l'application.

Tous les réglages sont dans `data/settings.json` :

| Clé | Rôle |
|---|---|
| `device` | `auto`, `cpu` ou `cuda:0` |
| `max_fps` | images analysées par seconde et par caméra |
| `person_conf`, `weapon_conf`, `coco_weapon_conf` | seuils de confiance |
| `face_recognition` | identification des personnes enregistrées (donnée biométrique) |
| `blur_unknown_faces` | floute les visages non reconnus, dans le direct et les captures |
| `retention_days` | suppression automatique du journal et des captures après N jours (0 = jamais) |
| `privacy_ack` | date à laquelle l'avertissement RGPD a été validé (`null` = il s'affiche au démarrage) |
| `draw_style` | `"contour"` (silhouette des objets) ou `"box"` (carrés) |
| `face_shape` | `"oval"` (par défaut) ou `"box"` autour des visages |
| `clothing` | `true` / `false` : reconnaissance du type de vêtements (CLIP) |
| `clothing_upper`, `clothing_lower` | types reconnus, ex. `{"polo": "a polo shirt"}` (vide = liste par défaut) |
| `clothing_min_conf` | confiance minimale, sinon le type affiché est « ? » |
| `weapon_labels` | renomme les classes du modèle d'armes, ex. `{"0": "arme à feu"}` |
| `weapon_cooldown_s`, `face_cooldown_s` | délai minimum entre deux alertes identiques |
| `log_unknown_faces` | enregistrer aussi les visages inconnus |

## Structure

```
app/main.py         API web + flux MJPEG
app/camera.py       lecture des caméras, reconnexion, événements
app/analyzer.py     YOLO (personnes, armes) + dessin
app/clip.py         CLIP : type de vêtements, type d'arme, filtre anti-fausses alertes
app/colors.py       couleur dominante des vêtements
app/faces.py        YuNet + SFace (OpenCV)
app/areas.py        zones et lignes de comptage
app/events.py       journal SQLite
app/i18n.py         traductions côté serveur
app/static/         interface web (FR/NL/EN)
launcher.py         version installée : serveur + fenêtre native
packaging/          PyInstaller + Inno Setup
tools/              préparation d'un jeu de données d'armes
data/               (non publié) réglages, caméras, journal, captures, galerie de visages
models/             (non publié) poids des modèles : download_models.py
```

## Cadre légal (Belgique / UE)

La reconnaissance faciale traite des **données biométriques** (art. 9 RGPD) : interdite par principe sauf exception
(consentement explicite, etc.). Les caméras sont aussi encadrées par la loi caméras du 21 mars 2007
(déclaration sur declarationcamera.be, pictogramme, durée de conservation limitée). Renseignez-vous avant
de filmer ou d'identifier des personnes en dehors d'un usage strictement privé.

## Licence et crédits

Code sous licence **GNU AGPL-3.0** (voir `LICENSE`), compatible avec Ultralytics YOLO, lui-même sous AGPL-3.0.

| Composant | Rôle | Licence |
|---|---|---|
| [Ultralytics YOLO11 / MobileSAM](https://github.com/ultralytics/ultralytics) | personnes, couteaux, suivi, détourage | AGPL-3.0 (MobileSAM : Apache-2.0) |
| [Zcket/gun_dtct](https://huggingface.co/Zcket/gun_dtct) | armes à feu | MIT |
| [OpenCV Zoo YuNet / SFace](https://github.com/opencv/opencv_zoo) | détection / reconnaissance faciale | MIT / Apache-2.0 |
| [OpenCLIP ViT-B-32 (LAION-2B)](https://github.com/mlfoundations/open_clip) | vêtements, types d'armes | MIT |
| [Open Images](https://storage.googleapis.com/openimages/web/index.html) | évaluation et entraînement (optionnel) | CC BY 4.0 / CC BY 2.0 |

Les modèles ne sont pas inclus dans ce dépôt : `download_models.py` les télécharge depuis leurs sources.
