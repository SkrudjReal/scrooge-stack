# Start official XERJ local node with authentication enabled.
$ErrorActionPreference = 'Stop'
$Data = Join-Path $env:LOCALAPPDATA 'scrooge-stack\xerj-data'
$Bin = Join-Path $env:LOCALAPPDATA 'Programs\xerj\xerj.exe'
if (Get-Command xerj -ErrorAction SilentlyContinue) { $Bin = (Get-Command xerj).Source }
New-Item -ItemType Directory -Force -Path $Data | Out-Null
Remove-Item Env:XERJ_CONFIG -ErrorAction SilentlyContinue
Remove-Item Env:XERJ_BIND_ADDRESS -ErrorAction SilentlyContinue
$Config = [IO.Path]::GetTempFileName()
try {
    [IO.File]::WriteAllText($Config, "[auth]`nenabled = true`n", (New-Object Text.UTF8Encoding($false)))
    & $Bin --config $Config --bind 127.0.0.1 --data-dir $Data
    $Code = $LASTEXITCODE
} finally { Remove-Item -LiteralPath $Config -Force }
exit $Code
