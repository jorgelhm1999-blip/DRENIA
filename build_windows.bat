@echo off
setlocal
cd /d "%~dp0"
if not exist "bin\whitebox_tools.exe" (
  echo Falta bin\whitebox_tools.exe. Usa el flujo de GitHub Actions o descárgalo desde WhiteboxTools.
  exit /b 1
)
py -3.12 -m pip install -r requirements.txt pyinstaller
if errorlevel 1 exit /b 1
py -3.12 -m PyInstaller --noconfirm --clean --onedir --windowed --name DRENIA --icon "assets\drenia_kyogre.ico" --add-data "assets\drenia_kyogre.ico;assets" --add-binary "bin\whitebox_tools.exe;bin" --collect-all rasterio --collect-all fiona --collect-all shapely app.py
if errorlevel 1 exit /b 1
echo Ejecutable: dist\DRENIA\DRENIA.exe
