param(
    [string]$SdkRoot = (Join-Path $PSScriptRoot '..\..\dependencies\sdk2026-win\SDK\SDKVW(832364)'),
    [string]$PlatformToolset = 'v145'
)
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$sdkAbsolute = (Resolve-Path -LiteralPath $SdkRoot).Path
$vsWhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
$buildTools = @(& $vsWhere -products '*' -find 'MSBuild\**\Bin\MSBuild.exe')
if ($buildTools.Count -eq 0) { throw 'MSBuild installation not found' }
$buildLog = Join-Path $repoRoot 'evidence\native-viewport-build.log'
& $buildTools[0] (Join-Path $repoRoot 'native\VwxBridge2026.vcxproj') '-p:Configuration=Release' '-p:Platform=x64' "-p:PlatformToolset=$PlatformToolset" "-p:VWSDK2026=$sdkAbsolute" '-v:minimal' "-flp:logfile=$buildLog;verbosity=normal"
if ($LASTEXITCODE -ne 0) { throw "Native build failed; see $buildLog" }
Write-Output 'Built native bridge only. This command does not close Vectorworks or install the binary.'
