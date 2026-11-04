# Official XERJ binary is the MCP server; this wrapper only loads local credentials.
$ErrorActionPreference = 'Stop'
$Data = Join-Path $env:LOCALAPPDATA 'scrooge-stack\xerj-data'
$Bin = Join-Path $env:LOCALAPPDATA 'Programs\xerj\xerj.exe'
if (Get-Command xerj -ErrorAction SilentlyContinue) { $Bin = (Get-Command xerj).Source }
$env:XERJ_URL = 'http://127.0.0.1:9200'
$KeyFile = Join-Path $Data 'admin.key'
if (-not (Test-Path -LiteralPath $KeyFile -PathType Leaf) -or (Get-Item -LiteralPath $KeyFile).Length -eq 0) { throw 'XERJ admin.key is missing; start the authenticated node first' }
$env:XERJ_AUTH = 'ApiKey ' + ([IO.File]::ReadAllText($KeyFile).Trim())
& $Bin mcp
exit $LASTEXITCODE
