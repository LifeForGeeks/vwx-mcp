param(
    [Parameter(Mandatory=$true)][ValidatePattern('^[a-z0-9][a-z0-9-]{0,80}$')][string]$StageName,
    [Parameter(Mandatory=$true)][string[]]$Functions
)
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$stageRoot = Join-Path $repoRoot "evidence\$StageName"
if (Test-Path -LiteralPath $stageRoot) { throw 'Stage already exists; inspect its receipt instead of replacing it.' }
New-Item -ItemType Directory -Path $stageRoot | Out-Null
$components = foreach ($extension in @('vlb','vwr')) {
    $built = Join-Path $repoRoot "native\Output\Release\VwxBridge.$extension"
    $installed = Join-Path $env:APPDATA "Nemetschek\Vectorworks\2026\Plug-ins\VwxBridge.$extension"
    $staged = Join-Path $stageRoot "VwxBridge.staged.$extension"
    $backup = Join-Path $stageRoot "VwxBridge.before.$extension"
    Copy-Item -LiteralPath $built -Destination $staged
    Copy-Item -LiteralPath $installed -Destination $backup
    @{source=$staged;destination=$installed;backup=$backup;
      before_sha256=(Get-FileHash -LiteralPath $installed).Hash.ToLowerInvariant();
      build_sha256=(Get-FileHash -LiteralPath $staged).Hash.ToLowerInvariant()}
}
$manifest = Join-Path $stageRoot 'manifest.json'
@{state='staged_not_installed';created=[DateTime]::UtcNow.ToString('o');components=@($components);
  functions=$Functions;runtime_validated=$false} | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $manifest -Encoding utf8
Write-Output "Staged and backed up native pair: $manifest"
