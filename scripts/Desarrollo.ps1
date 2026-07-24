$ErrorActionPreference = "Stop"

$projectDirectory = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectDirectory

if (-not (Test-Path -LiteralPath ".venv\Scripts\python.exe")) {
    throw "Falta .venv. Ejecuta scripts\InstalarDesarrollo.ps1 primero."
}

& ".venv\Scripts\python.exe" app\manage.py runserver 127.0.0.1:8000
