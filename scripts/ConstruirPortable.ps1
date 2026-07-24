[CmdletBinding()]
param(
    [switch]$OmitirPruebas,
    [switch]$OmitirZip
)

$ErrorActionPreference = "Stop"

$projectDirectory = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$pythonExecutable = Join-Path $projectDirectory ".venv\Scripts\python.exe"
$buildDirectory = Join-Path $projectDirectory "build"
$portableDirectory = Join-Path $projectDirectory "portable"
$packageDirectory = Join-Path $portableDirectory "GestionFinanciera"
$archivePath = Join-Path $portableDirectory "GestionFinanciera-portable.zip"
$specPath = Join-Path $projectDirectory "GestionFinanciera.spec"

function Assert-ProjectChildPath {
    param([Parameter(Mandatory = $true)][string]$Path)

    $resolved = [IO.Path]::GetFullPath($Path)
    $prefix = $projectDirectory.TrimEnd(
        [IO.Path]::DirectorySeparatorChar,
        [IO.Path]::AltDirectorySeparatorChar
    ) + [IO.Path]::DirectorySeparatorChar
    if (-not $resolved.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw "La ruta de construccion quedo fuera del proyecto: $resolved"
    }
    return $resolved
}

function Remove-GeneratedDirectory {
    param([Parameter(Mandatory = $true)][string]$Path)

    $safePath = Assert-ProjectChildPath -Path $Path
    if (Test-Path -LiteralPath $safePath) {
        Remove-Item -LiteralPath $safePath -Recurse -Force
    }
}

if (-not (Test-Path -LiteralPath $pythonExecutable -PathType Leaf)) {
    throw "Falta el entorno de desarrollo. Ejecuta scripts\InstalarDesarrollo.ps1."
}
if (-not (Test-Path -LiteralPath $specPath -PathType Leaf)) {
    throw "Falta GestionFinanciera.spec."
}

& $pythonExecutable -c "import PyInstaller"
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller no esta instalado. Ejecuta scripts\InstalarDesarrollo.ps1."
}

if (-not $OmitirPruebas) {
    & (Join-Path $PSScriptRoot "Probar.ps1")
    if ($LASTEXITCODE -ne 0) {
        throw "Las pruebas fallaron; el paquete no sera construido."
    }
}

Remove-GeneratedDirectory -Path $buildDirectory
Remove-GeneratedDirectory -Path $packageDirectory
if (Test-Path -LiteralPath $archivePath -PathType Leaf) {
    Remove-Item -LiteralPath (Assert-ProjectChildPath -Path $archivePath) -Force
}
New-Item -ItemType Directory -Path $portableDirectory -Force | Out-Null

& $pythonExecutable -m PyInstaller `
    --noconfirm `
    --clean `
    --distpath $portableDirectory `
    --workpath $buildDirectory `
    $specPath
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller no pudo construir el paquete."
}

foreach ($directoryName in @("data", "backups", "exports", "media")) {
    New-Item `
        -ItemType Directory `
        -Path (Join-Path $packageDirectory $directoryName) `
        -Force | Out-Null
}

Copy-Item `
    -Path (Join-Path $projectDirectory "portable_assets\*") `
    -Destination $packageDirectory `
    -Force
Copy-Item `
    -LiteralPath (Join-Path $projectDirectory "docs\MANUAL_USO_PORTABLE.txt") `
    -Destination (Join-Path $packageDirectory "LEEME_PRIMERO.txt") `
    -Force

& (Join-Path $PSScriptRoot "ProbarPortable.ps1") -Paquete $packageDirectory
if ($LASTEXITCODE -ne 0) {
    throw "El paquete se construyo, pero no supero la prueba portable."
}

$manifestPath = Join-Path $packageDirectory "MANIFEST_SHA256.txt"
$manifestLines = Get-ChildItem -LiteralPath $packageDirectory -Recurse -File |
    Where-Object { $_.FullName -ne $manifestPath } |
    Sort-Object FullName |
    ForEach-Object {
        $relative = $_.FullName.Substring($packageDirectory.Length).TrimStart([char[]]"\/")
        $hash = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash
        "$hash  $relative"
    }
[IO.File]::WriteAllLines($manifestPath, $manifestLines, [Text.UTF8Encoding]::new($false))

if (-not $OmitirZip) {
    Compress-Archive `
        -LiteralPath $packageDirectory `
        -DestinationPath $archivePath `
        -CompressionLevel Optimal

    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $archive = [IO.Compression.ZipFile]::OpenRead($archivePath)
    try {
        $archiveNames = @(
            $archive.Entries | ForEach-Object { $_.FullName.Replace("\", "/") }
        )
        foreach ($requiredEntry in @(
            "GestionFinanciera/GestionFinanciera.exe",
            "GestionFinanciera/Restaurador.exe",
            "GestionFinanciera/LEEME_PRIMERO.txt",
            "GestionFinanciera/MANIFEST_SHA256.txt"
        )) {
            if ($requiredEntry -notin $archiveNames) {
                throw "El ZIP quedo incompleto; falta $requiredEntry."
            }
        }

        $buffer = New-Object byte[] 65536
        foreach ($entry in $archive.Entries) {
            if ($entry.Length -eq 0) {
                continue
            }
            $stream = $entry.Open()
            try {
                while ($stream.Read($buffer, 0, $buffer.Length) -gt 0) {}
            }
            finally {
                $stream.Dispose()
            }
        }
    }
    finally {
        $archive.Dispose()
    }
}

$packageSize = (
    Get-ChildItem -LiteralPath $packageDirectory -Recurse -File |
        Measure-Object -Property Length -Sum
).Sum

Write-Host ""
Write-Host "Paquete portable validado:"
Write-Host "  $packageDirectory"
Write-Host ("  Tamano: {0:N1} MB" -f ($packageSize / 1MB))
if (-not $OmitirZip) {
    Write-Host "  ZIP: $archivePath"
}
