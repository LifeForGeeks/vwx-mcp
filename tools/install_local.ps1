param(
    [string]$PluginDirectory = "$env:APPDATA\Nemetschek\Vectorworks\2026\Plug-ins\VWX-MCP",
    [string]$ServerDirectory = "$env:USERPROFILE\.local\share\vwx-mcp"
)
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
if (!(Test-Path -LiteralPath $PluginDirectory) -or !(Test-Path -LiteralPath $ServerDirectory)) {
    throw 'Existing Vectorworks bridge/server installation required. This updater does not create a new native bridge.'
}
$releaseStamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$backupRoot = Join-Path $repoRoot "evidence\deployment-$releaseStamp"
New-Item -ItemType Directory -Path $backupRoot -Force | Out-Null
$entries = @(
    @{Source='mcp-server\gdtf_files.py'; Destination=(Join-Path $ServerDirectory 'gdtf_files.py')},
    @{Source='mcp-server\gdtf_files.py'; Destination=(Join-Path $PluginDirectory 'gdtf_files.py')},
    @{Source='mcp-server\cable_parts_catalog.py'; Destination=(Join-Path $ServerDirectory 'cable_parts_catalog.py')},
    @{Source='vwx-plugin\entertainment.py'; Destination=(Join-Path $PluginDirectory 'entertainment.py')},
    @{Source='vwx-plugin\commands.py'; Destination=(Join-Path $PluginDirectory 'commands.py')},
    @{Source='vwx-plugin\vwx_pump.py'; Destination=(Join-Path $PluginDirectory 'vwx_pump.py')},
    @{Source='vwx-plugin\vs_index.json'; Destination=(Join-Path $PluginDirectory 'vs_index.json')},
    @{Source='mcp-server\entertainment_tools.py'; Destination=(Join-Path $ServerDirectory 'entertainment_tools.py')},
    @{Source='mcp-server\tool_tags.py'; Destination=(Join-Path $ServerDirectory 'tool_tags.py')},
    @{Source='mcp-server\vwx_mcp_server.py'; Destination=(Join-Path $ServerDirectory 'vwx_mcp_server.py')}
)
$manifest = foreach ($entry in $entries) {
    $sourcePath = Join-Path $repoRoot $entry.Source
    $backupName = $entry.Source.Replace('\','--')
    $backupPath = Join-Path $backupRoot $backupName
    $existed = Test-Path -LiteralPath $entry.Destination
    if ($existed) { Copy-Item -LiteralPath $entry.Destination -Destination $backupPath }
    Copy-Item -LiteralPath $sourcePath -Destination ($entry.Destination + '.vm-update') -Force
    Move-Item -LiteralPath ($entry.Destination + '.vm-update') -Destination $entry.Destination -Force
    @{source=$sourcePath; destination=$entry.Destination; existed=$existed; backup=$backupPath;
      sha256=(Get-FileHash -LiteralPath $entry.Destination -Algorithm SHA256).Hash}
}
$manifest | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $backupRoot 'manifest.json') -Encoding utf8
Write-Output "Deployed Velvet Mirror toolkit. Backup: $backupRoot"
Write-Output 'Native Python commands hot-reload. Reconnect the MCP server to load the named tools and automatic two-event creation. Old clients must follow requires_finalization results explicitly; see README-VM.md.'
