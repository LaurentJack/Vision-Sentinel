@echo off
rem Construit dist\VisionSentinel\ (programme) puis dist\installer\VisionSentinel-Setup-x.y.z.exe
cd /d "%~dp0.."
echo [1/3] Executable (PyInstaller)...
.venv\Scripts\pyinstaller --noconfirm --clean --distpath dist --workpath build packaging\VisionSentinel.spec || exit /b 1
echo [2/3] Modeles...
.venv\Scripts\python packaging\copy_models.py || exit /b 1
echo [3/3] Installateur (Inno Setup)...
set ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe
if not exist "%ISCC%" set ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe
"%ISCC%" packaging\installer.iss || exit /b 1
echo Termine : dist\installer
