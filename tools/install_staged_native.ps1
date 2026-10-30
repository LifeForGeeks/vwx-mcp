param([Parameter(Mandatory=$true)][string]$ManifestPath)
$ErrorActionPreference = 'Stop'
if (Get-Process Vectorworks2026 -ErrorAction SilentlyContinue) {
    throw 'Close Vectorworks normally before installing the staged native bridge. No files were changed.'
}
$manifestAbsolute = (Resolve-Path -LiteralPath $ManifestPath).Path
$receipt = Get-Content -LiteralPath $manifestAbsolute -Raw | ConvertFrom-Json
if ($receipt.state -ne 'staged_not_installed') { throw "Inspect existing receipt state before proceeding: $($receipt.state)" }
foreach ($entry in $receipt.components) {
    $sourceHash = (Get-FileHash -LiteralPath $entry.source -Algorithm SHA256).Hash.ToLowerInvariant()
    $currentHash = (Get-FileHash -LiteralPath $entry.destination -Algorithm SHA256).Hash.ToLowerInvariant()
    $backupHash = (Get-FileHash -LiteralPath $entry.backup -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($sourceHash -ne $entry.build_sha256 -or $currentHash -ne $entry.before_sha256 -or $backupHash -ne $entry.before_sha256) {
        throw 'Build, installation or backup changed since staging. Inspect before creating a new receipt.'
    }
}
try {
    foreach ($entry in $receipt.components) { Copy-Item -LiteralPath $entry.source -Destination $entry.destination -Force }
    foreach ($entry in $receipt.components) {
        if ((Get-FileHash -LiteralPath $entry.destination -Algorithm SHA256).Hash.ToLowerInvariant() -ne $entry.build_sha256) { throw 'Installed binary checksum mismatch' }
    }
    $receipt.state = 'installed_pending_runtime_validation'
    $receipt | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $manifestAbsolute -Encoding utf8
} catch {
    foreach ($entry in $receipt.components) { Copy-Item -LiteralPath $entry.backup -Destination $entry.destination -Force }
    throw
}
Write-Output 'Native bridge installed. Start Vectorworks and validate the staged functions in the separate QA file; installation alone does not establish runtime support.'
