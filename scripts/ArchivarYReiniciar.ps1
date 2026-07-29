[CmdletBinding()]
param(
    [string]$Nombre = "",
    [switch]$SinConfirmacion
)

$ErrorActionPreference = "Stop"

$projectDirectory = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$pythonExecutable = Join-Path $projectDirectory ".venv\Scripts\python.exe"
$archiveTool = Join-Path $projectDirectory "launcher\archive_reset.py"

if (-not (Test-Path -LiteralPath $pythonExecutable -PathType Leaf)) {
    throw "No existe el entorno local. Ejecuta primero scripts\Iniciar.bat."
}
if (-not (Test-Path -LiteralPath $archiveTool -PathType Leaf)) {
    throw "No se encontró la herramienta de archivado."
}

$toolArguments = @($archiveTool)
if ($Nombre.Trim()) {
    $toolArguments += @("--name", $Nombre.Trim())
}
if ($SinConfirmacion) {
    $toolArguments += "--yes"
}

Push-Location $projectDirectory
try {
    & $pythonExecutable @toolArguments
    if ($LASTEXITCODE -ne 0) {
        throw "La base no fue archivada ni reiniciada."
    }
}
finally {
    Pop-Location
}
