@echo off
REM Builds dist\PaperHeart.exe using an isolated virtual environment,
REM so the exe only bundles PaperHeart's own dependencies.

setlocal
cd /d "%~dp0"

if not exist .buildvenv (
    echo Creating build virtual environment...
    python -m venv .buildvenv
)

echo Installing build dependencies...
.buildvenv\Scripts\python.exe -m pip install --upgrade pip -q
.buildvenv\Scripts\python.exe -m pip install -r requirements.txt pyinstaller -q

echo Building PaperHeart.exe...
.buildvenv\Scripts\python.exe -m PyInstaller --noconfirm --onefile --windowed ^
    --name PaperHeart ^
    --icon assets\paperheart.ico ^
    --add-data "assets\paperheart.ico;assets" ^
    main.py

echo.
echo Done. The executable is at dist\PaperHeart.exe
endlocal
