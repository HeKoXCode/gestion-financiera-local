@echo off
setlocal
cd /d "%~dp0.."

if not exist ".venv\Scripts\python.exe" (
    echo El sistema todavia no fue preparado en este equipo.
    echo Ejecuta primero scripts\Iniciar.bat.
    pause
    exit /b 1
)

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0ArchivarYReiniciar.ps1"
if errorlevel 1 (
    echo.
    echo La operacion no se completo.
    pause
    exit /b 1
)

echo.
pause
endlocal
