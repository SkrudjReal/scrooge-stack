$ErrorActionPreference = 'Stop'
$Script = Join-Path $PSScriptRoot 'obsidian-live.py'
& py -3 $Script
if ($LASTEXITCODE -ne 0) { throw 'Native Windows Obsidian live test failed' }
