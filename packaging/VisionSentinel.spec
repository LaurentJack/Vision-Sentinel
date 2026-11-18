# Recette PyInstaller : construit dist/VisionSentinel/VisionSentinel.exe (dossier, pas un fichier unique).
# Lancement : packaging\build.bat (ou .venv\Scripts\pyinstaller packaging\VisionSentinel.spec)
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules

ROOT = Path(SPECPATH).parent

datas, binaries, hiddenimports = [], [], []
# Paquets qui chargent des fichiers ou des modules à la volée (configs YOLO, tokenizer CLIP, WebView2...)
# imageio_ffmpeg : contient FFmpeg (encodage H.264 des enregistrements vidéo)
for pkg in ("ultralytics", "open_clip", "webview", "imageio_ffmpeg"):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h
hiddenimports += collect_submodules("uvicorn") + collect_submodules("app") + ["lap"]

# torchvision charge ses opérateurs compilés (nms...) à la volée depuis _C_stable.pyd :
# PyInstaller ne les voit pas, sans eux CLIP et le tri des détections échouent.
import torchvision
_tv = Path(torchvision.__file__).parent
binaries += [(str(f), "torchvision") for f in list(_tv.glob("*.pyd")) + list(_tv.glob("*.dll"))]
datas += [(str(ROOT / "app" / "static"), "app/static")]

a = Analysis(
    [str(ROOT / "launcher.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "IPython", "jupyter_client", "notebook", "pytest", "tensorboard"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="VisionSentinel",
    console=False,            # pas de fenêtre noire : journal dans %LOCALAPPDATA%\VisionSentinel\logs
    icon=str(ROOT / "packaging" / "icon.ico"),
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="VisionSentinel", upx=False)
