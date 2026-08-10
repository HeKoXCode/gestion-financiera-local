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
    "ArchivarYReiniciar.exe",
    "INICIAR.bat",
    "RESTAURAR_DATOS.bat",
    "ARCHIVAR_Y_REINICIAR.bat",
    "HABILITAR_ACCESO_CELULAR.bat",
    "DESHABILITAR_ACCESO_CELULAR.bat",
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
$previousGestionPort = $env:GESTION_PORT
$succeeded = $false

try {
    $env:Path = "$env:SystemRoot\System32;$env:SystemRoot"
    $env:HTTP_PROXY = "http://127.0.0.1:9"
    $env:HTTPS_PROXY = "http://127.0.0.1:9"
    $env:NO_PROXY = "127.0.0.1,localhost"
    $env:GESTION_PORT = "0"

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

    $archiveProcess = Start-Process `
        -FilePath (Join-Path $smokeDirectory "ArchivarYReiniciar.exe") `
        -ArgumentList @("--name", "portable-smoke", "--yes") `
        -WorkingDirectory $smokeDirectory `
        -WindowStyle Hidden `
        -Wait `
        -PassThru
    if ($archiveProcess.ExitCode -ne 0) {
        throw "ArchivarYReiniciar.exe termino con codigo $($archiveProcess.ExitCode)."
    }

    $archivePath = Get-ChildItem `
        -LiteralPath (Join-Path $smokeDirectory "storage") `
        -Filter "gestion_portable-smoke_*.sqlite3.zip" `
        -File |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1 -ExpandProperty FullName
    if (-not $archivePath) {
        throw "El archivador no creo la copia historica en storage."
    }

    & $pythonExecutable -c @"
import sqlite3
from pathlib import Path
from launcher.backup import validate_application_backup, validate_application_database
validate_application_database(Path(r'$databasePath'))
validate_application_backup(
    Path(r'$recoveryPath'),
    working_directory=Path(r'$databasePath').parent,
)
validate_application_backup(
    Path(r'$archivePath'),
    working_directory=Path(r'$databasePath').parent,
)
with sqlite3.connect(r'$databasePath') as connection:
    monthly_migration = connection.execute(
        'SELECT 1 FROM django_migrations WHERE app = ? AND name = ?',
        ('core', '0004_add_monthly_frequency'),
    ).fetchone()
    business_rows = sum(
        connection.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
        for table in (
            'core_customer',
            'core_product',
            'core_sale',
            'core_installment',
            'core_payment',
            'core_collectionattempt',
        )
    )
if monthly_migration is None:
    raise RuntimeError('El portable no aplico la migracion de frecuencia mensual.')
if business_rows:
    raise RuntimeError('El archivador portable no dejo vacios los datos comerciales.')
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
    $env:GESTION_PORT = $previousGestionPort
}

if ($succeeded) {
    $safeSmokeDirectory = Assert-TemporaryChildPath -Path $smokeDirectory
    Remove-Item -LiteralPath $safeSmokeDirectory -Recurse -Force
    Write-Host "Prueba portable aprobada: ejecutables, servidor, recursos, backup, restore y archivo/reinicio."
}
else {
    Write-Warning "La copia de diagnostico quedo en: $smokeDirectory"
}
