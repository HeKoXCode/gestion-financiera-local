$ErrorActionPreference = "Stop"

$projectDirectory = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectDirectory

if (-not (Test-Path -LiteralPath ".venv\Scripts\python.exe")) {
    py -3.12 -m venv .venv
}

& ".venv\Scripts\python.exe" -m pip install --upgrade pip

$requirementsFile = if (Test-Path -LiteralPath "requirements-dev.lock") {
    "requirements-dev.lock"
} else {
    "requirements-dev.in"
}

& ".venv\Scripts\python.exe" -m pip install -r $requirementsFile
& ".venv\Scripts\python.exe" app\manage.py migrate

Write-Host ""
Write-Host "Entorno de desarrollo preparado."
Write-Host "Podés iniciar con scripts\Iniciar.bat"

