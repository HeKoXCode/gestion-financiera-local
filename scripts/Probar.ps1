$ErrorActionPreference = "Stop"

$projectDirectory = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectDirectory

if (-not (Test-Path -LiteralPath ".venv\Scripts\python.exe")) {
    throw "Falta .venv. Ejecuta scripts\InstalarDesarrollo.ps1 primero."
}

& ".venv\Scripts\python.exe" -m ruff check .
& ".venv\Scripts\python.exe" -m coverage erase
& ".venv\Scripts\python.exe" -m coverage run -m pytest
& ".venv\Scripts\python.exe" -m coverage report
