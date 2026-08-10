@echo off
setlocal
set "RULE_NAME=Gestion Financiera - Acceso celular"

fltmc >nul 2>&1
if errorlevel 1 (
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

netsh advfirewall firewall delete rule name="%RULE_NAME%" >nul 2>&1
netsh advfirewall firewall add rule ^
    name="%RULE_NAME%" ^
    dir=in ^
    action=allow ^
    protocol=TCP ^
    localport=8765 ^
    remoteip=LocalSubnet ^
    profile=any ^
    enable=yes >nul

if errorlevel 1 (
    echo.
    echo No se pudo configurar el Firewall de Windows.
    echo Verifica que el servicio Firewall de Microsoft Defender este activo.
    echo.
    pause
    exit /b 1
)

echo.
echo Acceso desde celular habilitado para esta computadora.
echo Solo se aceptan conexiones desde la red local al puerto 8765.
timeout /t 4 >nul
exit /b 0
