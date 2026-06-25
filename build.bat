@echo off
setlocal
cd /d "%~dp0"
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m PyInstaller --noconfirm --clean --windowed --name Banjofy --collect-all PySide6 src\banjofy\__main__.py
if errorlevel 1 pause
