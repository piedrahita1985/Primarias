@echo off
REM Empaqueta la app en un unico ejecutable (.exe) con PyInstaller.
REM Requiere: pip install pyinstaller  (una sola vez, no va en requirements.txt
REM porque es una herramienta de build, no una dependencia en tiempo de ejecucion)
REM
REM El .exe resultante queda en dist\Kardex Primarias.exe y ya es autocontenido: al
REM primer arranque crea config.json, data\kardex.db, errores.log y firmas\
REM junto a si mismo (ver app_paths.py: writable_base_path()).
REM
REM Se envia con el inventario ya migrado: despues de compilar, este script
REM copia data\kardex.db, config.json y firmas\ junto al .exe (mismo criterio
REM que usa la app en tiempo de ejecucion via writable_base_path()).
REM
REM --collect-submodules UI: UI/menu.py abre cada pantalla con
REM importlib.import_module("UI.entradas") a partir de un string armado en
REM tiempo de ejecucion. El analizador estatico de PyInstaller NO sigue esos
REM imports dinamicos, asi que sin esta bandera el build queda "incompleto"
REM (arranca, pero cualquier pantalla que no sea login/menu falla con
REM "No module named UI.xxx" al abrirla). Con esta bandera se fuerza a incluir
REM TODOS los .py de UI/ (y por lo tanto lo que cada uno importe de logica/).
py -3 -m PyInstaller --onefile --windowed --noconfirm --name "Kardex Primarias" --icon "imagenes\icono.ico" --add-data "imagenes;imagenes" --collect-submodules UI --collect-submodules logica main.py

echo Copiando datos junto al ejecutable...
if not exist "dist\data" mkdir "dist\data"
copy /Y data\kardex.db "dist\data\kardex.db" >nul
copy /Y config.json "dist\config.json" >nul
if exist firmas (
    xcopy /Y /I /E firmas "dist\firmas" >nul
)

echo.
echo Listo. Ejecutable en dist\Kardex Primarias.exe (con inventario, config y firmas incluidos)
