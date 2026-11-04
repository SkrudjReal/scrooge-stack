$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$TestRoot = Join-Path $env:TEMP ('scrooge-test-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $TestRoot | Out-Null
$OldHome = $HOME
$OldLocalAppData = $env:LOCALAPPDATA
$OldCodexHome = $env:CODEX_HOME
function global:git {
    $global:ScroogeGitCalls++
    if ($args[0] -eq '-C') {
        $global:LASTEXITCODE = 0
        return [IO.File]::ReadAllText((Join-Path $args[1] '.mock-origin'))
    }
    $Url = $args[$args.Count - 2]
    $Destination = $args[$args.Count - 1]
    if ($env:SCROOGE_TEST_FAIL -and $Url.Contains($env:SCROOGE_TEST_FAIL)) { $global:LASTEXITCODE = 1; return }
    New-Item -ItemType Directory -Force -Path (Join-Path $Destination '.git') | Out-Null
    [IO.File]::WriteAllText((Join-Path $Destination '.mock-origin'), $Url)
    if ($Url -match 'ponytail|agentic-awesome-skills') {
        $Skill = Join-Path $Destination 'skills\example'
        New-Item -ItemType Directory -Force -Path $Skill | Out-Null
        [IO.File]::WriteAllText((Join-Path $Skill 'SKILL.md'), "---`nname: example`ndescription: auto`n---`nbody`n")
    }
    $global:LASTEXITCODE = 0
}
function global:graphify {
    $Skill = Join-Path $env:USERPROFILE '.codex\skills\graphify'
    New-Item -ItemType Directory -Force -Path $Skill | Out-Null
    [IO.File]::WriteAllText((Join-Path $Skill 'SKILL.md'), "---`nname: graphify`ndescription: auto`n---`nbody`n")
    $global:LASTEXITCODE = 0
}
function global:agy { $global:LASTEXITCODE = 0; 'deploychan http'; 'xerj stdio' }
try {
    $global:ScroogeGitCalls = 0
    Set-Variable HOME -Value (Join-Path $TestRoot 'home') -Force
    $env:LOCALAPPDATA = Join-Path $HOME 'AppData\Local'
    $env:CODEX_HOME = $null
    New-Item -ItemType Directory -Path $HOME | Out-Null
    & (Join-Path $Root 'install.ps1') -DryRun -Targets agy -SkipXerj -SkipObsidian
    if (Get-ChildItem -LiteralPath $HOME -Force) { throw 'Dry run modified home' }
    New-Item -ItemType Directory -Force -Path (Join-Path $HOME '.gemini\config') | Out-Null
    $Config = Join-Path $HOME '.gemini\config\mcp_config.json'
    $Unicode = [string][char]0x0416
    [IO.File]::WriteAllText($Config, ('{"mcpServers":{"other":{"command":"kept"}},"other":42,"unicode":"' + $Unicode + '"}'), (New-Object Text.UTF8Encoding($false)))
    $Prompt = Join-Path $HOME '.gemini\GEMINI.md'
    [IO.File]::WriteAllText($Prompt, 'Personal instructions')
    & (Join-Path $Root 'install.ps1') -Targets agy -SkipXerj -SkipObsidian
    $First = [IO.File]::ReadAllText($Config)
    $FirstPrompt = [IO.File]::ReadAllText($Prompt)
    $Data = $First | ConvertFrom-Json
    if ($Data.other -ne 42 -or $Data.unicode -ne $Unicode -or $Data.mcpServers.other.command -ne 'kept' -or $Data.mcpServers.deploychan.serverUrl -ne 'https://mcp.deploychan.webcam/mcp') { throw 'MCP preservation failed' }
    if ([IO.File]::ReadAllBytes($Config)[0] -eq 0xEF) { throw 'Unexpected UTF-8 BOM' }
    if (-not $FirstPrompt.Contains('Personal instructions')) { throw 'Prompt preservation failed' }
    if (-not (Get-ChildItem (Split-Path $Config) -Filter 'mcp_config.json.bak.*')) { throw 'MCP backup missing' }
    & (Join-Path $Root 'install.ps1') -Targets agy -SkipXerj -SkipObsidian
    if ([IO.File]::ReadAllText($Config) -ne $First -or [IO.File]::ReadAllText($Prompt) -ne $FirstPrompt) { throw 'Reinstall changed settings' }
    function global:py { $global:ObsidianTestArgs = @($args); $global:LASTEXITCODE = 0 }
    & (Join-Path $Root 'install.ps1') -Targets agy -SkipXerj -ObsidianVault 'C:\Vault with spaces' -ObsidianRepo 'C:\Repo with spaces' -ObsidianWrite
    if (-not ($global:ObsidianTestArgs -contains 'C:\Vault with spaces') -or -not ($global:ObsidianTestArgs -contains 'C:\Repo with spaces') -or -not ($global:ObsidianTestArgs -contains '--enable-writes')) { throw 'Obsidian flag forwarding failed' }
    $BeforeGit = $global:ScroogeGitCalls
    & (Join-Path $Root 'install.ps1') -OnlyObsidian -Targets 'agy,gemini' -ObsidianVault 'C:\Vault with spaces'
    if ($global:ScroogeGitCalls -ne $BeforeGit) { throw 'Obsidian-only setup ran other components' }
    if (-not ($global:ObsidianTestArgs -contains 'agy,gemini')) { throw 'Obsidian-only target forwarding failed' }
    function global:py { $global:LASTEXITCODE = 7 }
    $Failed = $false
    try { & (Join-Path $Root 'install.ps1') -Targets agy -SkipXerj } catch { $Failed = $_.ToString().Contains('Obsidian installation failed') }
    if (-not $Failed) { throw 'Obsidian failure did not stop installer' }
    Set-Variable HOME -Value (Join-Path $TestRoot 'failure-home') -Force
    $env:LOCALAPPDATA = Join-Path $HOME 'AppData\Local'
    $env:SCROOGE_TEST_FAIL = 'agentic-awesome-skills'
    $Failed = $false
    try { & (Join-Path $Root 'install.ps1') -Targets agy -SkipXerj -SkipObsidian } catch { $Failed = $true }
    if (-not $Failed) { throw 'Failed clone did not stop installer' }
    if (Test-Path (Join-Path $env:LOCALAPPDATA 'scrooge-stack\sources\choirboy-prompt')) { throw 'Choirboy ran after failure' }
    Remove-Item Env:SCROOGE_TEST_FAIL
    Set-Variable HOME -Value (Join-Path $TestRoot 'checksum-home') -Force
    $env:LOCALAPPDATA = Join-Path $HOME 'AppData\Local'
    function global:Invoke-WebRequest {
        param([string]$Uri, [string]$OutFile, [switch]$UseBasicParsing)
        if ($Uri.EndsWith('.sha256')) { [IO.File]::WriteAllText($OutFile, ('0' * 64)) }
        else { [IO.File]::WriteAllText($OutFile, 'not a release') }
    }
    $Failed = $false
    try { & (Join-Path $Root 'install.ps1') -Targets agy -SkipObsidian } catch { $Failed = $_.ToString().Contains('SHA-256') }
    if (-not $Failed) { throw 'Invalid XERJ checksum was not rejected' }
    if (Test-Path (Join-Path $env:LOCALAPPDATA 'scrooge-stack\sources\choirboy-prompt')) { throw 'Choirboy ran after checksum failure' }
    Write-Host 'Windows PowerShell mocked dry run, install, reinstall, UTF-8, failure ordering and checksum rejection passed'
} finally {
    Set-Variable HOME -Value $OldHome -Force
    $env:LOCALAPPDATA = $OldLocalAppData
    $env:CODEX_HOME = $OldCodexHome
    Remove-Item Env:SCROOGE_TEST_FAIL -ErrorAction SilentlyContinue
    Remove-Item Function:\git -ErrorAction SilentlyContinue
    Remove-Item Function:\graphify -ErrorAction SilentlyContinue
    Remove-Item Function:\agy -ErrorAction SilentlyContinue
    Remove-Item Function:\py -ErrorAction SilentlyContinue
    Remove-Item Function:\Invoke-WebRequest -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $TestRoot -Recurse -Force
}
