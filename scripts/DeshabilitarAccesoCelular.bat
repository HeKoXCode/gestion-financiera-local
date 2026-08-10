@echo off
setlocal
set "RULE_NAME=Gestion Financiera - Acceso celular"

fltmc >nul 2>&1
if errorlevel 1 (
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

netsh advfirewall firewall show rule name="%RULE_NAME%" >nul 2>&1
if errorlevel 1 goto success

netsh advfirewall firewall delete rule name="%RULE_NAME%" >nul 2>&1

if errorlevel 1 (
    echo.
    echo No se pudo quitar la regla del Firewall de Windows.
    echo.
    pause
    exit /b 1
)

:success
echo.
echo Acceso desde celular deshabilitado en esta computadora.
timeout /t 4 >nul
exit /b 0
