# Scrooge Stack bootstrap for Windows 10/11 PowerShell 5.1+.
# Uses existing agent CLIs; MCPVault is a client-launched local stdio process.
param(
    [string]$Targets = 'codex,agy,gemini',
    [switch]$DryRun,
    [switch]$SkipXerj,
    [switch]$SkipObsidian,
    [switch]$OnlyObsidian,
    [string]$ObsidianVault = '',
    [string]$ObsidianRepo = '',
    [switch]$ObsidianWrite,
    [string]$ChoirboySource = ''
)
$ErrorActionPreference = 'Stop'
$Root = $PSScriptRoot
$DataDir = Join-Path $env:LOCALAPPDATA 'scrooge-stack\sources'
$CodexHome = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $HOME '.codex' }
$Stamp = (Get-Date -Format 'yyyyMMdd-HHmmss-fffffff')
$Endpoint = 'https://mcp.deploychan.webcam/mcp'
$Selected = @($Targets.Split(',') | ForEach-Object { $_.Trim().ToLowerInvariant() } | Where-Object { $_ })
if ($Selected.Count -eq 0 -or $Targets -match '(^,|,$|,,)') { throw 'Select at least one valid target' }
foreach ($Target in $Selected) {
    if ($Target -notin @('codex','agy','gemini')) { throw "Invalid target: $Target" }
}
function HasTarget([string]$Value) { return $Selected -contains $Value }
function Log([string]$Message) { Write-Host "[scrooge] $Message" }
function Warn([string]$Message) { if ($DryRun) { Write-Warning $Message } else { throw $Message } }
function Available([string]$Command) { return [bool](Get-Command $Command -ErrorAction SilentlyContinue) }
function CodexExists([string]$Name) {
    $ErrorActionPreference = 'Continue'
    & codex mcp get $Name 2>$null | Out-Null
    return $LASTEXITCODE -eq 0
}
function Backup([string]$Path) {
    if (Test-Path -LiteralPath $Path -PathType Leaf) {
        $Copy = "$Path.bak.$(Get-Date -Format yyyyMMdd-HHmmss-fffffff)"
        if ($DryRun) { Log "[dry-run] Backup $Path -> $Copy" }
        else { Copy-Item -LiteralPath $Path -Destination $Copy -ErrorAction Stop }
    }
}
function CloneOnce([string]$Url, [string]$Path) {
    if (Test-Path -LiteralPath (Join-Path $Path '.git')) {
        $Origin = & git -C $Path remote get-url origin
        if ($LASTEXITCODE -ne 0 -or ($Origin -replace '\.git$', '') -ne ($Url -replace '\.git$', '')) { throw "Unexpected Git origin: $Path" }
        Log "Using checkout: $Path"; return $true
    }
    if (Test-Path -LiteralPath $Path) { Warn "Existing non-Git folder, refusing to replace: $Path"; return $false }
    if (-not (Available 'git')) { Warn "git missing; cannot clone $Url"; return $false }
    if ($DryRun) { Log "[dry-run] git clone --depth 1 $Url $Path"; return $true }
    New-Item -ItemType Directory -Path (Split-Path $Path -Parent) -Force | Out-Null
    & git clone --depth 1 $Url $Path
    if ($LASTEXITCODE -ne 0) { Warn "Clone failed: $Url"; return $false }
    return $true
}
function CopySkill([string]$Source, [string]$Destination) {
    if (Test-Path -LiteralPath $Destination) { return }
    if ($DryRun) { Log "[dry-run] Copy skill $Source -> $Destination"; return }
    if (-not (Test-Path -LiteralPath (Join-Path $Source 'SKILL.md'))) { return }
    New-Item -ItemType Directory -Force -Path (Split-Path $Destination -Parent) | Out-Null
    Copy-Item -LiteralPath $Source -Destination $Destination -Recurse -ErrorAction Stop
}
function CopyManualSkill([string]$Source, [string]$Destination, [string]$Name) {
    if (Test-Path -LiteralPath $Destination) { return }
    CopySkill $Source $Destination
    if ($DryRun) { return }
    $Path = Join-Path $Destination 'SKILL.md'
    $Text = [IO.File]::ReadAllText($Path)
    $Parts = $Text -split '---', 3
    if ($Parts.Count -ne 3 -or $Parts[0].Trim()) { throw "Invalid skill frontmatter: $Path" }
    $Pattern = '(?ms)^description:[^\r\n]*(?:\r?\n[ \t]+[^\r\n]*)*'
    $Regex = New-Object Text.RegularExpressions.Regex($Pattern)
    if (-not $Regex.IsMatch($Parts[1])) { throw "Missing skill description: $Path" }
    $Front = $Regex.Replace($Parts[1], ('description: "Use only when the user explicitly requests ' + $Name + '."'), 1)
    [IO.File]::WriteAllText($Path, ('---' + $Front + '---' + $Parts[2]), (New-Object Text.UTF8Encoding($false)))
}
function InstallManualSkills([string]$SourceRoot, [string]$DestRoot) {
    if ($DryRun) { Log "[dry-run] Install explicit-only skills from $SourceRoot to $DestRoot"; return }
    if (-not (Test-Path -LiteralPath $SourceRoot)) { throw "Skill directory missing: $SourceRoot" }
    $Skills = @(Get-ChildItem -LiteralPath $SourceRoot -Directory | Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName 'SKILL.md') })
    if ($Skills.Count -eq 0) { throw "No skills found in $SourceRoot" }
    $Skills | ForEach-Object {
        if (Test-Path -LiteralPath (Join-Path $_.FullName 'SKILL.md')) { CopyManualSkill $_.FullName (Join-Path $DestRoot $_.Name) $_.Name }
    }
}
function InstallSkills([string]$SourceRoot, [string]$DestRoot) {
    if ($DryRun) { Log "[dry-run] Install skills from $SourceRoot to $DestRoot (skip existing)"; return }
    if (-not (Test-Path -LiteralPath $SourceRoot)) { throw "Skill directory missing: $SourceRoot" }
    $Skills = @(Get-ChildItem -LiteralPath $SourceRoot -Directory | Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName 'SKILL.md') })
    if ($Skills.Count -eq 0) { throw "No skills found in $SourceRoot" }
    $Skills | ForEach-Object {
        if (Test-Path -LiteralPath (Join-Path $_.FullName 'SKILL.md')) {
            CopySkill $_.FullName (Join-Path $DestRoot $_.Name)
        }
    }
}
function WritePrompt([string]$Destination) {
    $Source = Join-Path $Root 'prompts\windows\AGENTS.md'
    $Begin = '<!-- scrooge-stack:begin -->'
    $End = '<!-- scrooge-stack:end -->'
    $Old = if (Test-Path -LiteralPath $Destination) { [IO.File]::ReadAllText($Destination) } else { '' }
    $Start = $Old.IndexOf($Begin); $Finish = $Old.IndexOf($End)
    if (($Start -lt 0) -ne ($Finish -lt 0) -or ($Start -ge 0 -and ($Finish -lt $Start -or $Old.IndexOf($Begin, $Start + 1) -ge 0 -or $Old.IndexOf($End, $Finish + 1) -ge 0))) { throw "Invalid managed markers: $Destination" }
    $Block = $Begin + "`n" + ([IO.File]::ReadAllText($Source).TrimEnd()) + "`n" + $End
    if ($Start -ge 0) { $New = $Old.Substring(0, $Start) + $Block + $Old.Substring($Finish + $End.Length) }
    else { $New = $Old; if ($New -and -not $New.EndsWith("`n")) { $New += "`n" }; if ($New) { $New += "`n" }; $New += $Block + "`n" }
    if ($Old -eq $New) { Log "Already current: $Destination"; return }
    if ($DryRun) { Log "[dry-run] Merge prompt into $Destination with backup"; return }
    New-Item -ItemType Directory -Path (Split-Path $Destination -Parent) -Force | Out-Null
    Backup $Destination
    [IO.File]::WriteAllText($Destination, $New, (New-Object Text.UTF8Encoding($false)))
}

function InstallObsidian {
    $ObsidianArgs = @((Join-Path $Root 'scripts\install-obsidian.py'), '--targets', $Targets,
        '--data-dir', (Join-Path $env:LOCALAPPDATA 'scrooge-stack\obsidian'))
    if ($ObsidianVault) { $ObsidianArgs += @('--vault', $ObsidianVault) }
    if ($ObsidianRepo) { $ObsidianArgs += @('--repo', $ObsidianRepo) }
    if ($ObsidianWrite) { $ObsidianArgs += '--enable-writes' }
    if ($DryRun) { Log ('[dry-run] Python 3.11+ ' + ($ObsidianArgs -join ' ') + ' --dry-run') }
    else {
        if (Available 'py') { & py -3 @ObsidianArgs }
        elseif (Available 'python') { & python @ObsidianArgs }
        else { throw 'Obsidian setup requires Python 3.11+ (py or python) and Node >=22.12 with npm' }
        if ($LASTEXITCODE -ne 0) { throw 'Obsidian installation failed; global instructions/Choirboy not applied' }
    }
}

if ($OnlyObsidian) {
    if ($SkipObsidian) { throw '-OnlyObsidian conflicts with -SkipObsidian' }
    Log "Obsidian-only setup for: $Targets (no other stack components)"
    InstallObsidian
    return
}

Log "Targets: $Targets (native Windows; WSL requires separate install.sh)"
foreach ($Command in (@('git') + $Selected)) {
    if (-not (Available $Command)) { Warn "Missing prerequisite: $Command; install it and retry" }
}
$env:PATH = (Join-Path $HOME '.local\bin') + ';' + $env:PATH

# 1. Ponytail: skills ONLY, so the Codex plugin / Gemini extension cannot enable always-on hooks.
Log '1/8 Ponytail (manual skills only)'
$Pony = Join-Path $DataDir 'ponytail'
if (CloneOnce 'https://github.com/DietrichGebert/ponytail.git' $Pony) {
    $PonySkills = Join-Path $Pony 'skills'
    if (HasTarget 'codex') { InstallManualSkills $PonySkills (Join-Path $CodexHome 'skills') }
    if (HasTarget 'agy') { InstallManualSkills $PonySkills (Join-Path $HOME '.gemini\config\skills') }
    if (HasTarget 'gemini') { InstallManualSkills $PonySkills (Join-Path $HOME '.gemini\skills') }
}

# 2. Graphify
Log '2/8 Graphify'
if (-not (Available 'graphify')) {
    if (Available 'uv') {
        if ($DryRun) { Log '[dry-run] uv tool install graphifyy' }
        else { & uv tool install graphifyy; if ($LASTEXITCODE -ne 0) { Warn 'Graphify install failed' } }
    } elseif (Available 'pipx') {
        if ($DryRun) { Log '[dry-run] pipx install graphifyy' }
        else { & pipx install graphifyy; if ($LASTEXITCODE -ne 0) { Warn 'Graphify install failed' } }
    } else { Warn 'graphify missing; install uv or pipx first' }
}
if (-not $DryRun -and -not (Available 'graphify')) { throw 'Graphify was installed but is not on PATH; add its tool bin directory and retry' }
if (Available 'graphify') {
    if ($DryRun) { Log '[dry-run] Extract Graphify skill in an isolated directory; install only missing skills' }
    else {
        $TempGraph = Join-Path ([IO.Path]::GetTempPath()) ('scrooge-graphify-' + [guid]::NewGuid().ToString('N'))
        New-Item -ItemType Directory -Path $TempGraph | Out-Null
        $OldProfile = $env:USERPROFILE; $OldHome = $env:HOME; $OldCodex = $env:CODEX_HOME
        try {
            $env:USERPROFILE = $TempGraph; $env:HOME = $TempGraph; $env:CODEX_HOME = Join-Path $TempGraph '.codex'
            Push-Location $TempGraph
            try { & graphify install --platform codex; if ($LASTEXITCODE -ne 0) { throw 'Graphify extraction failed' } } finally { Pop-Location }
            $GraphSkill = Join-Path $TempGraph '.codex\skills\graphify'
            if (-not (Test-Path -LiteralPath (Join-Path $GraphSkill 'SKILL.md'))) { throw 'Graphify did not produce a skill' }
        } finally { $env:USERPROFILE = $OldProfile; $env:HOME = $OldHome; $env:CODEX_HOME = $OldCodex }
        try {
            if (HasTarget 'codex') { CopyManualSkill $GraphSkill (Join-Path $CodexHome 'skills\graphify') 'graphify' }
            if (HasTarget 'agy') { CopyManualSkill $GraphSkill (Join-Path $HOME '.gemini\config\skills\graphify') 'graphify' }
            if (HasTarget 'gemini') { CopyManualSkill $GraphSkill (Join-Path $HOME '.gemini\skills\graphify') 'graphify' }
        } finally { Remove-Item -LiteralPath $TempGraph -Recurse -Force }
    }
}

# 3. Deploychan remote MCP
Log '3/8 Deploychan remote MCP'
if (HasTarget 'codex') {
    if (Available 'codex') {
        if ($DryRun) { Log "[dry-run] codex mcp add deploychan --url $Endpoint" }
        else {
            if (-not (CodexExists 'deploychan')) {
                Backup (Join-Path $CodexHome 'config.toml')
                & codex mcp add deploychan --url $Endpoint
                if ($LASTEXITCODE -ne 0) { Warn 'Codex MCP registration failed' }
            } else {
                $Existing = (& codex mcp get deploychan --json | ConvertFrom-Json)
                if ($LASTEXITCODE -ne 0 -or $Existing.transport.url -ne $Endpoint) { throw 'Existing Codex Deploychan differs' }
            }
            if (-not (CodexExists 'deploychan')) { throw 'Codex Deploychan verification failed' }
        }
    } else { Warn 'codex is not on PATH; skipping Codex MCP registration' }
}
if (HasTarget 'agy') {
    $McpPath = Join-Path $HOME '.gemini\config\mcp_config.json'
    if ($DryRun) { Log "[dry-run] Merge Deploychan into $McpPath" }
    else {
        New-Item -ItemType Directory -Path (Split-Path $McpPath -Parent) -Force | Out-Null
        $Data = if (Test-Path -LiteralPath $McpPath) { [IO.File]::ReadAllText($McpPath, (New-Object Text.UTF8Encoding($false,$true))) | ConvertFrom-Json } else { [pscustomobject]@{} }
        if ($null -eq $Data -or $Data -is [array]) { throw 'Invalid AGY MCP JSON root' }
        if (-not $Data.PSObject.Properties['mcpServers']) { $Data | Add-Member -NotePropertyName mcpServers -NotePropertyValue ([pscustomobject]@{}) }
        if ($null -eq $Data.mcpServers -or $Data.mcpServers -isnot [pscustomobject]) { throw 'Invalid mcpServers section' }
        $Existing = $Data.mcpServers.PSObject.Properties['deploychan']
        if ($Existing -and $Existing.Value.serverUrl -ne $Endpoint) { throw 'Existing Deploychan MCP differs; preserving it' }
        if (-not $Existing) {
            Backup $McpPath
            $Data.mcpServers | Add-Member -NotePropertyName deploychan -NotePropertyValue ([pscustomobject]@{serverUrl=$Endpoint}) -Force
            [System.IO.File]::WriteAllText($McpPath, ($Data | ConvertTo-Json -Depth 60) + "`n", (New-Object System.Text.UTF8Encoding($false)))
        }
        $List = & agy mcp list
        if ($LASTEXITCODE -ne 0 -or -not ($List -match '^deploychan\s')) { throw 'AGY Deploychan registration verification failed' }
    }
}
function GeminiMcp([string]$Name, [string]$Expected, [string[]]$Arguments) {
    if ($DryRun) { Log "[dry-run] Verify or register Gemini MCP: $Name"; return }
    $Path = Join-Path $HOME '.gemini\settings.json'
    $Settings = if (Test-Path -LiteralPath $Path) { [IO.File]::ReadAllText($Path) | ConvertFrom-Json } else { [pscustomobject]@{} }
    if ($Settings -isnot [pscustomobject]) { throw 'Invalid Gemini settings root' }
    $Servers = $Settings.mcpServers
    if ($null -ne $Servers -and $Servers -isnot [pscustomobject]) { throw 'Invalid Gemini mcpServers' }
    $Property = if ($Servers) { $Servers.PSObject.Properties[$Name] } else { $null }
    if ($Property) {
        $Actual = if ($Name -eq 'deploychan') { if ($Property.Value.url) { $Property.Value.url } else { $Property.Value.httpUrl } } else { $Property.Value.command }
        if ($Actual -ne $Expected) { throw "Existing Gemini $Name differs; preserving it" }
        if ($Name -eq 'xerj' -and ($Property.Value.args -join '|') -ne ($Arguments[1..($Arguments.Count - 1)] -join '|')) { throw 'Existing Gemini XERJ arguments differ; preserving them' }
    } else {
        Backup $Path
        & gemini mcp add --scope user $Name @Arguments
        if ($LASTEXITCODE -ne 0) { throw "Gemini $Name registration failed" }
        $Settings = [IO.File]::ReadAllText($Path) | ConvertFrom-Json
        if (-not $Settings.mcpServers.PSObject.Properties[$Name]) { throw "Gemini $Name verification failed" }
    }
}
if (HasTarget 'gemini') {
    if (Available 'gemini') { GeminiMcp 'deploychan' $Endpoint @('--transport','http',$Endpoint) }
    else { Warn 'gemini is missing; install Gemini CLI first' }
}



# 4. Install checksummed upstream XERJ binary; register its official MCP stdio adapter.
Log '4/8 XERJ (verified upstream release; no automatic indexing or server startup)'
if (-not $SkipXerj) {
    $XerjBin = Join-Path $env:LOCALAPPDATA 'Programs\xerj\xerj.exe'
    if (Available 'xerj') { $XerjBin = (Get-Command xerj).Source }
    $XerjScripts = Join-Path $env:LOCALAPPDATA 'scrooge-stack\bin'
    $XerjMcp = Join-Path $XerjScripts 'xerj-mcp.ps1'
    if (-not (Test-Path -LiteralPath $XerjBin)) {
        $Arch = if ($env:PROCESSOR_ARCHITECTURE -eq 'ARM64') { 'aarch64-pc-windows-msvc' } elseif ($env:PROCESSOR_ARCHITECTURE -eq 'AMD64') { 'x86_64-pc-windows-msvc' } else { '' }
        if (-not $Arch) { Warn 'Unsupported XERJ Windows architecture (only AMD64 and ARM64)' }
        elseif ($DryRun) { Log "[dry-run] Download and verify XERJ v1.0.0-rc.100 $Arch" }
        else {
            $Temp = Join-Path ([System.IO.Path]::GetTempPath()) ('scrooge-xerj-' + [guid]::NewGuid().ToString('N'))
            try {
                New-Item -ItemType Directory -Force -Path $Temp | Out-Null
                $File = 'xerj-1.0.0-rc.100-' + $Arch + '.zip'
                $Url = 'https://github.com/xerj-org/xerj/releases/download/v1.0.0-rc.100/' + $File
                $Archive = Join-Path $Temp $File
                $HashPath = "$Archive.sha256"
                Invoke-WebRequest -Uri $Url -OutFile $Archive -UseBasicParsing
                Invoke-WebRequest -Uri ($Url + '.sha256') -OutFile $HashPath -UseBasicParsing
                $Expected = ([IO.File]::ReadAllText($HashPath) -split '\s+')[0].ToUpperInvariant()
                $Actual = (Get-FileHash -LiteralPath $Archive -Algorithm SHA256).Hash
                if ($Expected -notmatch '^[0-9A-F]{64}$' -or $Expected -ne $Actual) { throw 'XERJ SHA-256 check failed' }
                $Extract = Join-Path $Temp 'extract'
                Expand-Archive -LiteralPath $Archive -DestinationPath $Extract -Force
                $Found = Get-ChildItem -LiteralPath $Extract -Recurse -File -Filter 'xerj.exe' | Select-Object -First 1
                if (-not $Found) { throw 'Release archive did not contain xerj.exe' }
                New-Item -ItemType Directory -Force -Path (Split-Path $XerjBin -Parent) | Out-Null
                Copy-Item -LiteralPath $Found.FullName -Destination $XerjBin -ErrorAction Stop
                Log "XERJ installed: $XerjBin"
            } catch { throw "XERJ install failed: $_" }
            finally { Remove-Item -LiteralPath $Temp -Recurse -Force -ErrorAction SilentlyContinue }
        }
    } else { Log "XERJ already installed: $XerjBin" }
    if ((Test-Path -LiteralPath $XerjBin) -or $DryRun) {
        foreach ($Filename in @('xerj-mcp.ps1','xerj-start.ps1')) {
            $Source = Join-Path $Root (Join-Path 'scripts' $Filename)
            $Dest = Join-Path $XerjScripts $Filename
            if ($DryRun) { Log "[dry-run] Install $Dest" }
            elseif ((-not (Test-Path -LiteralPath $Dest)) -or (Get-FileHash $Source -Algorithm SHA256).Hash -ne (Get-FileHash $Dest -Algorithm SHA256).Hash) {
                New-Item -ItemType Directory -Force -Path $XerjScripts | Out-Null
                Backup $Dest
                Copy-Item -LiteralPath $Source -Destination $Dest -Force
            }
        }
        if (HasTarget 'codex') {
            if (Available 'codex') {
                if ($DryRun) { Log "[dry-run] codex mcp add xerj -- powershell.exe -NoProfile -ExecutionPolicy Bypass -File $XerjMcp" }
                else {
                    if (-not (CodexExists 'xerj')) {
                        Backup (Join-Path $CodexHome 'config.toml')
                        & codex mcp add xerj -- powershell.exe -NoProfile -ExecutionPolicy Bypass -File $XerjMcp
                        if ($LASTEXITCODE -ne 0) { Warn 'Codex XERJ registration failed' }
                    } else {
                        $ExistingXerj = (& codex mcp get xerj --json | ConvertFrom-Json).transport
                        if ($ExistingXerj.command -ne 'powershell.exe' -or ($ExistingXerj.args -join '|') -ne (@('-NoProfile','-ExecutionPolicy','Bypass','-File',$XerjMcp) -join '|')) { throw 'Existing Codex XERJ differs; preserving it' }
                    }
                    if (-not (CodexExists 'xerj')) { throw 'Codex XERJ verification failed' }
                }
            } else { Warn 'Codex is missing; XERJ registration skipped' }
        }
        if (HasTarget 'agy') {
            $McpPath = Join-Path $HOME '.gemini\config\mcp_config.json'
            if ($DryRun) { Log "[dry-run] Merge XERJ into AGY $McpPath" }
            else {
                New-Item -ItemType Directory -Path (Split-Path $McpPath -Parent) -Force | Out-Null
                $Data = if (Test-Path -LiteralPath $McpPath) { [IO.File]::ReadAllText($McpPath, (New-Object Text.UTF8Encoding($false,$true))) | ConvertFrom-Json } else { [pscustomobject]@{} }
                if ($null -eq $Data -or $Data -is [array]) { throw 'AGY MCP root must be an object' }
                if (-not $Data.PSObject.Properties['mcpServers']) { $Data | Add-Member -NotePropertyName mcpServers -NotePropertyValue ([pscustomobject]@{}) }
                if ($null -eq $Data.mcpServers -or $Data.mcpServers -isnot [pscustomobject]) { throw 'Invalid AGY mcpServers' }
                $ExistingXerj = $Data.mcpServers.PSObject.Properties['xerj']
                if ($ExistingXerj -and ($ExistingXerj.Value.command -ne 'powershell.exe' -or ($ExistingXerj.Value.args -join '|') -ne (@('-NoProfile','-ExecutionPolicy','Bypass','-File',$XerjMcp) -join '|'))) { throw 'Existing AGY XERJ differs; preserving it' }
                if (-not $ExistingXerj) {
                    Backup $McpPath
                    $Data.mcpServers | Add-Member -NotePropertyName xerj -NotePropertyValue ([pscustomobject]@{
                        command = 'powershell.exe'; args = @('-NoProfile','-ExecutionPolicy','Bypass','-File',$XerjMcp)
                    })
                    [IO.File]::WriteAllText($McpPath, ($Data | ConvertTo-Json -Depth 60) + "`n", (New-Object Text.UTF8Encoding($false)))
                }
                $List = & agy mcp list
                if ($LASTEXITCODE -ne 0 -or -not ($List -match '^xerj\s')) { throw 'AGY XERJ registration verification failed' }
            }
        }
        if (HasTarget 'gemini') {
            if (Available 'gemini') { GeminiMcp 'xerj' 'powershell.exe' @('powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',$XerjMcp) }
            else { Warn 'Gemini is missing; XERJ registration skipped' }
        }
        Log "Start authenticated XERJ manually: powershell -NoProfile -ExecutionPolicy Bypass -File `"$(Join-Path $XerjScripts 'xerj-start.ps1')`""
    }
}

# 5. AAS — EXACT sickn33 upstream. No npm registry substitution.
Log '5/8 AAS library (sickn33 upstream)'
$Aas = Join-Path $DataDir 'agentic-awesome-skills'
if (CloneOnce 'https://github.com/sickn33/agentic-awesome-skills.git' $Aas) {
    $AasSkills = Join-Path $Aas 'skills'
    if (HasTarget 'codex') { InstallSkills $AasSkills (Join-Path $CodexHome 'skills') }
    if (HasTarget 'agy') { InstallSkills $AasSkills (Join-Path $HOME '.gemini\config\skills') }
    if (HasTarget 'gemini') { InstallSkills $AasSkills (Join-Path $HOME '.gemini\skills') }
}
$Selector = Join-Path $Root 'skills\aas-skill-selector'
if (HasTarget 'codex') { CopySkill $Selector (Join-Path $CodexHome 'skills\aas-skill-selector') }
if (HasTarget 'agy') { CopySkill $Selector (Join-Path $HOME '.gemini\config\skills\aas-skill-selector') }
if (HasTarget 'gemini') { CopySkill $Selector (Join-Path $HOME '.gemini\skills\aas-skill-selector') }

# Owner's GitHub publication style; preserve existing local skills on reruns.
$GitHubStyle = Join-Path $Root 'skills\github-markdown-style'
if (HasTarget 'codex') { CopySkill $GitHubStyle (Join-Path $CodexHome 'skills\github-markdown-style') }
if (HasTarget 'agy') { CopySkill $GitHubStyle (Join-Path $HOME '.gemini\config\skills\github-markdown-style') }
if (HasTarget 'gemini') { CopySkill $GitHubStyle (Join-Path $HOME '.gemini\skills\github-markdown-style') }

# 6. Same portable helper as Linux; native Python, no Bash or REST API required.
Log '6/8 Obsidian (MCPVault + DataWeave + FTS5)'
if (-not $SkipObsidian) { InstallObsidian }

# 7. Prompt first, Choirboy afterwards.
Log '7/8 Global instructions'
if (HasTarget 'codex') { WritePrompt (Join-Path $CodexHome 'AGENTS.md') }
if ((HasTarget 'agy') -or (HasTarget 'gemini')) { WritePrompt (Join-Path $HOME '.gemini\GEMINI.md') }

# 8. Choirboy LAST. The original repo contains the author's personal memory.
Log '8/8 Choirboy (last)'
if ($ChoirboySource) {
    $Installer = Join-Path $ChoirboySource 'install.ps1'
    if (-not (Test-Path -LiteralPath $Installer)) { throw 'Provide an already-personalized Choirboy checkout containing install.ps1' }
    foreach ($File in @('.scrooge-personalized', 'lore.md', 'user.md')) { $Path = Join-Path $ChoirboySource $File; if (-not (Test-Path -LiteralPath $Path -PathType Leaf) -or (Get-Item -LiteralPath $Path).Length -eq 0) { throw "Personalized Choirboy requires nonempty $File" } }
    if ($DryRun) { Log "[dry-run] Install customized Choirboy from $ChoirboySource" }
    else {
        if (-not (Available 'pwsh')) { throw 'Choirboy activation requires PowerShell 7 (pwsh); install it first to avoid an automatic bootstrap' }
        $PwshMajor = & pwsh -NoProfile -Command '$PSVersionTable.PSVersion.Major'
        if ($LASTEXITCODE -ne 0 -or [int]$PwshMajor -lt 7) { throw 'Choirboy activation requires PowerShell 7 or newer' }
        & pwsh -NoProfile -ExecutionPolicy Bypass -File $Installer --target $Targets
        if ($LASTEXITCODE -ne 0) { Warn 'Choirboy installation failed; review output' }
    }
} else {
    $ChoirStage = Join-Path $DataDir 'choirboy-prompt'
    if (-not (CloneOnce 'https://github.com/howdeploy/choirboy-prompt.git' $ChoirStage)) { throw 'Choirboy staging failed' }
    Log "Choirboy staged last at $ChoirStage but NOT activated. Personalize the memory files first."
    Log 'Do not use the upstream author personal lore as your own.'
}
Log 'Oh My Zsh is managed only by install.sh in Ubuntu/WSL, not by this Windows installer.'
if ($DryRun) { Log 'Dry run complete; no changes were made and integrations were not verified.' }
else { Log 'Completed requested steps. Restart selected agents and review staged integrations.' }
