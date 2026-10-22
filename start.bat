@echo off
cd /d "%~dp0"
if not exist .venv (
  echo Installation de l'environnement...
  python -m venv .venv
  .venv\Scripts\python -m pip install --upgrade pip
  .venv\Scripts\python -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu126
  .venv\Scripts\python -m pip install -r requirements.txt
)
.venv\Scripts\python download_models.py
start "" http://localhost:8000
.venv\Scripts\python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
