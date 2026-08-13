$ErrorActionPreference = "Stop"

$projectDirectory = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectDirectory

if (-not (Test-Path -LiteralPath ".venv\Scripts\python.exe")) {
    throw "Falta .venv. Ejecuta scripts\InstalarDesarrollo.ps1 primero."
}

$pythonExecutable = ".venv\Scripts\python.exe"

function Invoke-RequiredStep {
    param(
        [Parameter(Mandatory = $true)][string]$Title,
        [Parameter(Mandatory = $true)][scriptblock]$Action
    )

    Write-Host ""
    Write-Host "== $Title ==" -ForegroundColor Cyan
    & $Action
    if ($LASTEXITCODE -ne 0) {
        throw "Fallo el paso obligatorio: $Title"
    }
}

Invoke-RequiredStep "Analisis estatico" {
    & $pythonExecutable -m ruff check .
}
Invoke-RequiredStep "Validacion de Django" {
    & $pythonExecutable app\manage.py check
}
Invoke-RequiredStep "Control de migraciones" {
    & $pythonExecutable app\manage.py makemigrations --check --dry-run
}
Invoke-RequiredStep "Pruebas" {
    & $pythonExecutable -m coverage erase
    & $pythonExecutable -m coverage run -m pytest
}
Invoke-RequiredStep "Cobertura minima" {
    & $pythonExecutable -m coverage report --fail-under=85
}
