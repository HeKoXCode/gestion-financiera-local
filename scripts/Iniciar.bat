@echo off
setlocal
cd /d "%~dp0.."

if not exist ".venv\Scripts\pythonw.exe" (
    echo Preparando el programa por primera vez...
    powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\InstalarDesarrollo.ps1"
    if errorlevel 1 (
        echo.
        echo No se pudo preparar el programa.
        pause
        exit /b 1
    )
)

start "" ".venv\Scripts\pythonw.exe" "launcher\launcher.py"
endlocal

