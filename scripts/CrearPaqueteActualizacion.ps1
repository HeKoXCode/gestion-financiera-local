[CmdletBinding()]
param(
    [string]$Version = (Get-Date -Format "yyyy-MM-dd")
)

$ErrorActionPreference = "Stop"

$projectDirectory = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$portableSource = Join-Path $projectDirectory "portable\GestionFinanciera"
$stagingRoot = Join-Path $projectDirectory "portable\_actualizacion_build"
$stagingPackage = Join-Path $stagingRoot "GestionFinanciera"
$updateZip = Join-Path $projectDirectory "portable\GestionFinanciera-actualizacion-$Version.zip"
$instructions = Join-Path $projectDirectory "docs\INSTRUCCIONES_ACTUALIZACION_CLIENTE.txt"

function Assert-ProjectChildPath {
    param([Parameter(Mandatory = $true)][string]$Path)

    $resolved = [IO.Path]::GetFullPath($Path)
    $prefix = $projectDirectory.TrimEnd(
        [IO.Path]::DirectorySeparatorChar,
        [IO.Path]::AltDirectorySeparatorChar
    ) + [IO.Path]::DirectorySeparatorChar
    if (-not $resolved.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw "La ruta quedó fuera del proyecto: $resolved"
    }
    return $resolved
}

if (-not (Test-Path -LiteralPath $portableSource -PathType Container)) {
    throw "Primero construí el portable con scripts\ConstruirPortable.ps1."
}
if (-not (Test-Path -LiteralPath $instructions -PathType Leaf)) {
    throw "Faltan las instrucciones de actualización."
}

$safeStagingRoot = Assert-ProjectChildPath -Path $stagingRoot
$safeUpdateZip = Assert-ProjectChildPath -Path $updateZip
if (Test-Path -LiteralPath $safeStagingRoot) {
    Remove-Item -LiteralPath $safeStagingRoot -Recurse -Force
}
if (Test-Path -LiteralPath $safeUpdateZip) {
    Remove-Item -LiteralPath $safeUpdateZip -Force
}

New-Item -ItemType Directory -Path $stagingPackage -Force | Out-Null
$excludedDirectories = @("data", "backups", "exports", "media", "storage")
Get-ChildItem -LiteralPath $portableSource -Force |
    Where-Object { $_.Name -notin $excludedDirectories } |
    ForEach-Object {
        Copy-Item `
            -LiteralPath $_.FullName `
            -Destination $stagingPackage `
            -Recurse `
            -Force
    }

Copy-Item `
    -LiteralPath $instructions `
    -Destination (Join-Path $stagingPackage "LEEME_ACTUALIZACION.txt") `
    -Force

Compress-Archive `
    -LiteralPath $stagingPackage `
    -DestinationPath $safeUpdateZip `
    -CompressionLevel Optimal

Add-Type -AssemblyName System.IO.Compression.FileSystem
$archive = [IO.Compression.ZipFile]::OpenRead($safeUpdateZip)
try {
    $names = @($archive.Entries | ForEach-Object { $_.FullName.Replace("\", "/") })
    foreach ($forbidden in @(
        "GestionFinanciera/data/",
        "GestionFinanciera/backups/",
        "GestionFinanciera/exports/",
        "GestionFinanciera/media/",
        "GestionFinanciera/storage/"
    )) {
        $forbiddenEntries = @(
            $names | Where-Object {
                $_.StartsWith($forbidden, [StringComparison]::OrdinalIgnoreCase)
            }
        )
        if ($forbiddenEntries.Count -gt 0) {
            throw "La actualización contiene datos del usuario: $forbidden"
        }
    }
    foreach ($required in @(
        "GestionFinanciera/GestionFinanciera.exe",
        "GestionFinanciera/LEEME_ACTUALIZACION.txt"
    )) {
        if ($required -notin $names) {
            throw "El ZIP de actualización quedó incompleto; falta $required."
        }
    }
    $entryCount = $archive.Entries.Count
}
finally {
    $archive.Dispose()
}

Remove-Item -LiteralPath $safeStagingRoot -Recurse -Force

$zipInfo = Get-Item -LiteralPath $safeUpdateZip
$hash = (Get-FileHash -LiteralPath $safeUpdateZip -Algorithm SHA256).Hash
Write-Host ""
Write-Host "Paquete de actualización validado:"
Write-Host "  $($zipInfo.FullName)"
Write-Host ("  Tamaño: {0:N2} MB" -f ($zipInfo.Length / 1MB))
Write-Host "  Entradas: $entryCount"
Write-Host "  SHA256: $hash"
