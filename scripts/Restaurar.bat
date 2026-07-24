@echo off
setlocal
cd /d "%~dp0.."

if not exist ".venv\Scripts\pythonw.exe" (
    echo El programa todavia no fue preparado en este equipo.
    echo Ejecuta primero scripts\Iniciar.bat.
    pause
    exit /b 1
)

start "" ".venv\Scripts\pythonw.exe" "launcher\restorer.py"
endlocal
