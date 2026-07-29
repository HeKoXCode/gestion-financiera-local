param(
    [string]$PaquetePortable = "",
    [switch]$OmitirPortable
)

$ErrorActionPreference = "Stop"

$projectDirectory = Split-Path -Parent $PSScriptRoot
$pythonExecutable = Join-Path $projectDirectory ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $pythonExecutable -PathType Leaf)) {
    throw "No existe el entorno de desarrollo. Ejecuta scripts\InstalarDesarrollo.ps1."
}

if (-not $PaquetePortable) {
    $PaquetePortable = Join-Path $projectDirectory "portable\GestionFinanciera"
}

function Invoke-QAStep {
    param(
        [string]$Title,
        [scriptblock]$Action
    )

    Write-Host ""
    Write-Host "== $Title ==" -ForegroundColor Cyan
    & $Action
    if ($LASTEXITCODE -ne 0) {
        throw "Fallo el paso: $Title"
    }
}

Push-Location $projectDirectory
try {
    Invoke-QAStep "Analisis estatico del codigo" {
        & $pythonExecutable -m ruff check app launcher tests
    }

    Invoke-QAStep "Validacion interna de Django" {
        & $pythonExecutable app\manage.py check
    }

    Invoke-QAStep "Control de migraciones pendientes" {
        & $pythonExecutable app\manage.py makemigrations --check --dry-run
    }

    Invoke-QAStep "Pruebas unitarias, integrales y casos extremos" {
        & $pythonExecutable -m coverage erase
        & $pythonExecutable -m coverage run -m pytest
    }

    Invoke-QAStep "Cobertura de pruebas" {
        & $pythonExecutable -m coverage report --fail-under=85
    }

    if (-not $OmitirPortable) {
        if (-not (Test-Path -LiteralPath $PaquetePortable -PathType Container)) {
            throw "No existe el paquete portable: $PaquetePortable"
        }
        Invoke-QAStep "Prueba aislada del portable y del restaurador" {
            & (Join-Path $PSScriptRoot "ProbarPortable.ps1") -Paquete $PaquetePortable
        }
    }

    Write-Host ""
    Write-Host "FASEFINAL3 APROBADA" -ForegroundColor Green
    Write-Host "Codigo, reglas financieras, pantallas, datos y portable superaron QA."
}
finally {
    Pop-Location
}
