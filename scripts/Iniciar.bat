@echo off
setlocal
cd /d "%~dp0.."

if not exist ".venv\Scripts\pythonw.exe" (
    echo Preparando el sistema por primera vez...
    powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\InstalarDesarrollo.ps1"
    if errorlevel 1 (
        echo.
        echo No se pudo preparar el sistema.
        pause
        exit /b 1
    )
)

start "" ".venv\Scripts\pythonw.exe" "launcher\launcher.py"
endlocal

