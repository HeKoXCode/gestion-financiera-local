[CmdletBinding()]
param(
    [string]$PythonPath = ""
)

$ErrorActionPreference = "Stop"

$projectDirectory = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectDirectory

if ([string]::IsNullOrWhiteSpace($PythonPath)) {
    $localPython = Join-Path $projectDirectory ".venv\Scripts\python.exe"
    if (Test-Path -LiteralPath $localPython -PathType Leaf) {
        $PythonPath = $localPython
    }
    else {
        $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
        if (-not $pythonCommand) {
            throw "No se encontro Python. Instala el entorno o indica -PythonPath."
        }
        $PythonPath = $pythonCommand.Source
    }
}
if (-not (Test-Path -LiteralPath $PythonPath -PathType Leaf)) {
    throw "No existe el ejecutable Python indicado: $PythonPath"
}

$pythonExecutable = [IO.Path]::GetFullPath($PythonPath)

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
