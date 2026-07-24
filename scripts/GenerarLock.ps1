$ErrorActionPreference = "Stop"

$projectDirectory = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectDirectory

if (-not (Test-Path -LiteralPath ".venv\Scripts\python.exe")) {
    py -3.12 -m venv .venv
}

& ".venv\Scripts\python.exe" -m pip install --upgrade pip
& ".venv\Scripts\python.exe" -m pip install pip-tools==7.6.0
& ".venv\Scripts\python.exe" -m piptools compile --generate-hashes `
    --output-file requirements.lock requirements.in
& ".venv\Scripts\python.exe" -m piptools compile --generate-hashes `
    --output-file requirements-dev.lock requirements-dev.in

