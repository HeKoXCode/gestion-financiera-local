[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$ArchivoZip,
    [string]$ChecksumPath = "",
    [string]$ReportPath = "",
    [string]$PythonPath = "",
    [switch]$OmitirDefender
)

$ErrorActionPreference = "Stop"

$projectDirectory = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$temporaryParent = Join-Path $projectDirectory "tmp"
$archivePath = [IO.Path]::GetFullPath($ArchivoZip)
$archiveName = [IO.Path]::GetFileName($archivePath)

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

function Remove-ValidatedTemporaryDirectory {
    param([Parameter(Mandatory = $true)][string]$Path)

    $safePath = Assert-TemporaryChildPath -Path $Path
    if (-not (Test-Path -LiteralPath $safePath -PathType Container)) {
        return
    }
    $reparsePoints = @(
        Get-ChildItem -LiteralPath $safePath -Force -Recurse |
            Where-Object { $_.Attributes -band [IO.FileAttributes]::ReparsePoint }
    )
    if ($reparsePoints.Count -gt 0) {
        throw "No se eliminara una carpeta temporal que contiene reparse points: $safePath"
    }
    Remove-Item -LiteralPath $safePath -Recurse -Force
}

if (-not (Test-Path -LiteralPath $archivePath -PathType Leaf)) {
    throw "No existe el ZIP de release: $archivePath"
}
if ([IO.Path]::GetExtension($archivePath) -ne ".zip") {
    throw "El artefacto de release debe ser un ZIP."
}

if ([string]::IsNullOrWhiteSpace($ChecksumPath)) {
    $ChecksumPath = Join-Path ([IO.Path]::GetDirectoryName($archivePath)) "SHA256SUMS.txt"
}
$resolvedChecksumPath = [IO.Path]::GetFullPath($ChecksumPath)
if (-not (Test-Path -LiteralPath $resolvedChecksumPath -PathType Leaf)) {
    throw "No existe el archivo de checksums: $resolvedChecksumPath"
}

$archiveHash = (Get-FileHash -LiteralPath $archivePath -Algorithm SHA256).Hash
$checksumLine = Get-Content -LiteralPath $resolvedChecksumPath |
    Where-Object { $_ -match ("\s{2}" + [Regex]::Escape($archiveName) + "$") } |
    Select-Object -First 1
if (-not $checksumLine) {
    throw "SHA256SUMS.txt no contiene una entrada para $archiveName."
}
$expectedHash = ($checksumLine -split '\s+', 2)[0].ToUpperInvariant()
if ($archiveHash -ne $expectedHash) {
    throw "El SHA-256 publicado no coincide con el ZIP."
}

Add-Type -AssemblyName System.IO.Compression.FileSystem
$archive = [IO.Compression.ZipFile]::OpenRead($archivePath)
try {
    $entryNames = @(
        $archive.Entries | ForEach-Object { $_.FullName.Replace("\", "/") }
    )
    foreach ($entryName in $entryNames) {
        if (
            $entryName.StartsWith("/") -or
            $entryName -match '(^|/)\.\.(/|$)' -or
            $entryName -match '^[A-Za-z]:'
        ) {
            throw "El ZIP contiene una ruta insegura: $entryName"
        }
    }

    foreach ($requiredEntry in @(
        "GestionFinanciera/GestionFinanciera.exe",
        "GestionFinanciera/Restaurador.exe",
        "GestionFinanciera/ArchivarYReiniciar.exe",
        "GestionFinanciera/LEEME_PRIMERO.txt",
        "GestionFinanciera/MANIFEST_SHA256.txt",
        "GestionFinanciera/VERSION.txt"
    )) {
        if ($requiredEntry -notin $entryNames) {
            throw "El ZIP de release esta incompleto; falta $requiredEntry."
        }
    }

    $sensitiveEntries = @(
        $entryNames | Where-Object {
            $_ -match '(?i)^GestionFinanciera/(data|backups|exports|media|storage)/.+' -or
            $_ -match '(?i)^GestionFinanciera/(\.env|\.secret_key)$' -or
            $_ -match '(?i)\.(sqlite|sqlite3|db|pem|key)$'
        }
    )
    if ($sensitiveEntries.Count -gt 0) {
        throw (
            "El ZIP contiene archivos que pueden ser sensibles:`n" +
            ($sensitiveEntries -join "`n")
        )
    }
}
finally {
    $archive.Dispose()
}

$auditDirectory = Join-Path $temporaryParent (
    "release-audit-" + [Guid]::NewGuid().ToString("N")
)
New-Item -ItemType Directory -Path $temporaryParent -Force | Out-Null
New-Item -ItemType Directory -Path $auditDirectory | Out-Null

$signatureResults = @()
$antivirusResult = [ordered]@{
    provider = "Microsoft Defender"
    executed = $false
    status = "omitted"
    signature_version = $null
    signature_updated_at = $null
    detections = 0
}
$completed = $false

try {
    [IO.Compression.ZipFile]::ExtractToDirectory($archivePath, $auditDirectory)
    $packageDirectory = Join-Path $auditDirectory "GestionFinanciera"
    if (-not (Test-Path -LiteralPath $packageDirectory -PathType Container)) {
        throw "El ZIP no contiene la carpeta raiz GestionFinanciera."
    }

    & (Join-Path $PSScriptRoot "ProbarPortable.ps1") `
        -Paquete $packageDirectory `
        -PythonPath $PythonPath
    if ($LASTEXITCODE -ne 0) {
        throw "La copia extraida no supero la prueba portable aislada."
    }

    foreach ($executableName in @(
        "GestionFinanciera.exe",
        "Restaurador.exe",
        "ArchivarYReiniciar.exe"
    )) {
        $signature = Get-AuthenticodeSignature `
            -LiteralPath (Join-Path $packageDirectory $executableName)
        $signatureResults += [ordered]@{
            file = $executableName
            status = $signature.Status.ToString()
            signer = if ($signature.SignerCertificate) {
                $signature.SignerCertificate.Subject
            } else {
                $null
            }
        }
    }

    if (-not $OmitirDefender) {
        if (
            -not (Get-Command Start-MpScan -ErrorAction SilentlyContinue) -or
            -not (Get-Command Get-MpComputerStatus -ErrorAction SilentlyContinue)
        ) {
            throw "Microsoft Defender no esta disponible; usa -OmitirDefender solo en CI."
        }

        $scanStartedAt = Get-Date
        Start-MpScan -ScanType CustomScan -ScanPath $archivePath
        $defenderStatus = Get-MpComputerStatus
        $recentDetections = @()
        if (Get-Command Get-MpThreatDetection -ErrorAction SilentlyContinue) {
            $recentDetections = @(
                Get-MpThreatDetection |
                    Where-Object {
                        $_.InitialDetectionTime -ge $scanStartedAt.AddSeconds(-5) -and
                        (($_.Resources -join " ") -match [Regex]::Escape($archiveName))
                    }
            )
        }
        if ($recentDetections.Count -gt 0) {
            throw "Microsoft Defender detecto una amenaza en el ZIP de release."
        }
        $antivirusResult.executed = $true
        $antivirusResult.status = "passed"
        $antivirusResult.signature_version = $defenderStatus.AntivirusSignatureVersion
        $antivirusResult.signature_updated_at = (
            $defenderStatus.AntivirusSignatureLastUpdated.ToUniversalTime().ToString("o")
        )
        $antivirusResult.detections = 0
    }

    $report = [ordered]@{
        schema_version = "1.0.0"
        project = "gestion-financiera-local"
        artifact = [ordered]@{
            file = $archiveName
            bytes = (Get-Item -LiteralPath $archivePath).Length
            sha256 = $archiveHash
            entries = $entryNames.Count
        }
        gates = [ordered]@{
            checksum = "passed"
            zip_paths = "passed"
            sensitive_content = "passed"
            isolated_smoke_test = "passed"
            antivirus = $antivirusResult
            authenticode = $signatureResults
        }
        signing_policy = (
            "Unsigned release: no code-signing certificate is available. " +
            "Authenticity is provided through the GitHub Release and SHA-256 checksum."
        )
        verified_at_utc = (Get-Date).ToUniversalTime().ToString("o")
    }

    if (-not [string]::IsNullOrWhiteSpace($ReportPath)) {
        $resolvedReportPath = [IO.Path]::GetFullPath($ReportPath)
        $reportParent = Split-Path -Parent $resolvedReportPath
        New-Item -ItemType Directory -Path $reportParent -Force | Out-Null
        [IO.File]::WriteAllText(
            $resolvedReportPath,
            ($report | ConvertTo-Json -Depth 8) + "`n",
            [Text.UTF8Encoding]::new($false)
        )
    }

    $completed = $true
    Write-Host "Release auditada correctamente:" -ForegroundColor Green
    Write-Host "  ZIP: $archivePath"
    Write-Host "  SHA-256: $archiveHash"
    Write-Host "  Contenido sensible: 0 archivos"
    Write-Host "  Smoke test aislado: aprobado"
    Write-Host "  Defender: $($antivirusResult.status)"
}
finally {
    if (Test-Path -LiteralPath $auditDirectory -PathType Container) {
        Remove-ValidatedTemporaryDirectory -Path $auditDirectory
    }
    if (-not $completed) {
        Write-Warning "La auditoria de release no se completo."
    }
}
