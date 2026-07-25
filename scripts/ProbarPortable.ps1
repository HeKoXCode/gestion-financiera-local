[CmdletBinding()]
param(
    [string]$Paquete
)

$ErrorActionPreference = "Stop"

$projectDirectory = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$temporaryParent = Join-Path $projectDirectory "tmp"
$pythonExecutable = Join-Path $projectDirectory ".venv\Scripts\python.exe"
if ([string]::IsNullOrWhiteSpace($Paquete)) {
    $Paquete = Join-Path $projectDirectory "portable\GestionFinanciera"
}
$packageDirectory = [IO.Path]::GetFullPath($Paquete)
$smokeDirectory = Join-Path $temporaryParent (
    "portable-smoke-" + [Guid]::NewGuid().ToString("N")
)

function Assert-TemporaryChildPath {
    param([Parameter(Mandatory = $true)][string]$Path)

    $resolved = [IO.Path]::GetFullPath($Path)
    $prefix = [IO.Path]::GetFullPath($temporaryParent).TrimEnd(
        [IO.Path]::DirectorySeparatorChar,
        [IO.Path]::AltDirectorySeparatorChar
    ) + [IO.Path]::DirectorySeparatorChar
    if (-not $resolved.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw "La carpeta temporal quedo fuera del area permitida: $resolved"
    }
    return $resolved
}

if (-not (Test-Path -LiteralPath $packageDirectory -PathType Container)) {
    throw "No existe el paquete portable: $packageDirectory"
}
foreach ($requiredFile in @(
    "GestionFinanciera.exe",
    "Restaurador.exe",
    "INICIAR.bat",
    "RESTAURAR_DATOS.bat",
    "LEEME_PRIMERO.txt"
)) {
    if (-not (Test-Path -LiteralPath (Join-Path $packageDirectory $requiredFile) -PathType Leaf)) {
        throw "Falta un archivo del paquete portable: $requiredFile"
    }
}
if (Get-ChildItem -LiteralPath $packageDirectory -Recurse -Filter "python.exe" -File) {
    throw "El paquete no debe depender de un ejecutable Python externo."
}

New-Item -ItemType Directory -Path $temporaryParent -Force | Out-Null
New-Item -ItemType Directory -Path $smokeDirectory | Out-Null
Copy-Item `
    -Path (Join-Path $packageDirectory "*") `
    -Destination $smokeDirectory `
    -Recurse `
    -Force

$previousPath = $env:Path
$previousHttpProxy = $env:HTTP_PROXY
$previousHttpsProxy = $env:HTTPS_PROXY
$previousNoProxy = $env:NO_PROXY
$succeeded = $false

try {
    $env:Path = "$env:SystemRoot\System32;$env:SystemRoot"
    $env:HTTP_PROXY = "http://127.0.0.1:9"
    $env:HTTPS_PROXY = "http://127.0.0.1:9"
    $env:NO_PROXY = "127.0.0.1,localhost"

    $applicationProcess = Start-Process `
        -FilePath (Join-Path $smokeDirectory "GestionFinanciera.exe") `
        -ArgumentList "--smoke-test" `
        -WorkingDirectory $smokeDirectory `
        -WindowStyle Hidden `
        -Wait `
        -PassThru
    if ($applicationProcess.ExitCode -ne 0) {
        $failureLog = Join-Path $smokeDirectory "smoke-test-error.txt"
        $detail = if (Test-Path -LiteralPath $failureLog -PathType Leaf) {
            Get-Content -LiteralPath $failureLog -Raw
        } else {
            "No se genero un registro de diagnostico."
        }
        throw (
            "GestionFinanciera.exe termino con codigo " +
            "$($applicationProcess.ExitCode).`n$detail"
        )
    }

    $databasePath = Join-Path $smokeDirectory "data\gestion_financiera.sqlite3"
    $recoveryPath = Join-Path $smokeDirectory "backups\gestion_recovery.sqlite3.zip"
    if (-not (Test-Path -LiteralPath $databasePath -PathType Leaf)) {
        throw "El ejecutable no creo la base fuera de _internal."
    }
    if (-not (Test-Path -LiteralPath $recoveryPath -PathType Leaf)) {
        throw "El ejecutable no creo la copia de recuperacion."
    }
    if (-not (Get-ChildItem `
        -LiteralPath (Join-Path $smokeDirectory "backups") `
        -Filter "gestion_close_*.sqlite3.zip" `
        -File
    )) {
        throw "La prueba de cierre no creo su backup final."
    }

    $restorerProcess = Start-Process `
        -FilePath (Join-Path $smokeDirectory "Restaurador.exe") `
        -ArgumentList "--smoke-test" `
        -WorkingDirectory $smokeDirectory `
        -WindowStyle Hidden `
        -Wait `
        -PassThru
    if ($restorerProcess.ExitCode -ne 0) {
        $failureLog = Join-Path $smokeDirectory "smoke-test-restorer-error.txt"
        $detail = if (Test-Path -LiteralPath $failureLog -PathType Leaf) {
            Get-Content -LiteralPath $failureLog -Raw
        } else {
            "No se genero un registro de diagnostico."
        }
        throw "Restaurador.exe termino con codigo $($restorerProcess.ExitCode).`n$detail"
    }

    if (-not (Get-ChildItem `
        -LiteralPath (Join-Path $smokeDirectory "backups") `
        -Filter "gestion_pre_restore_*.sqlite3.zip" `
        -File
    )) {
        throw "El restaurador no creo el backup preventivo."
    }

    & $pythonExecutable -c @"
from pathlib import Path
from launcher.backup import validate_application_backup, validate_application_database
validate_application_database(Path(r'$databasePath'))
validate_application_backup(
    Path(r'$recoveryPath'),
    working_directory=Path(r'$databasePath').parent,
)
print('Base portable: integridad y estructura correctas')
"@
    if ($LASTEXITCODE -ne 0) {
        throw "La base generada por el paquete no supero la validacion externa."
    }

    $succeeded = $true
}
finally {
    $env:Path = $previousPath
    $env:HTTP_PROXY = $previousHttpProxy
    $env:HTTPS_PROXY = $previousHttpsProxy
    $env:NO_PROXY = $previousNoProxy
}

if ($succeeded) {
    $safeSmokeDirectory = Assert-TemporaryChildPath -Path $smokeDirectory
    Remove-Item -LiteralPath $safeSmokeDirectory -Recurse -Force
    Write-Host "Prueba portable aprobada: ejecutables, servidor, recursos, backup y restore."
}
else {
    Write-Warning "La copia de diagnostico quedo en: $smokeDirectory"
}
