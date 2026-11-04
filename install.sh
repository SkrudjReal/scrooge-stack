#!/usr/bin/env bash
# Scrooge Stack bootstrap: Ubuntu / WSL. Does not install AI hosts or run a custom MCP server.
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOME_DIR="$HOME"
DATA_DIR="${XDG_DATA_HOME:-$HOME_DIR/.local/share}/scrooge-stack"
TARGETS="codex,agy,gemini"
DRY_RUN=0
CHOIRBOY_SOURCE=""
SKIP_XERJ=0
SKIP_ZSH=0
SKIP_OBSIDIAN=0
OBSIDIAN_VAULT=""
OBSIDIAN_REPO=""
OBSIDIAN_WRITE=0
URL="https://mcp.deploychan.webcam/mcp"

usage() {
  echo "Usage: bash install.sh [--targets codex,agy,gemini] [--dry-run] [--skip-xerj] [--skip-zsh] [--skip-obsidian] [--obsidian-vault DIR] [--obsidian-repo DIR] [--obsidian-write] [--choirboy-source DIR]"
  echo "Choirboy is cloned last but NOT activated unless --choirboy-source points to an already-personalized checkout."
}
while (($#)); do
  case "$1" in
    --targets) TARGETS="${2:?Missing targets}"; shift 2;;
    --dry-run) DRY_RUN=1; shift;;
    --skip-xerj) SKIP_XERJ=1; shift;;
    --skip-zsh) SKIP_ZSH=1; shift;;
    --skip-obsidian) SKIP_OBSIDIAN=1; shift;;
    --obsidian-vault) OBSIDIAN_VAULT="${2:?Missing vault directory}"; shift 2;;
    --obsidian-repo) OBSIDIAN_REPO="${2:?Missing DataWeave directory}"; shift 2;;
    --obsidian-write) OBSIDIAN_WRITE=1; shift;;
    --choirboy-source) CHOIRBOY_SOURCE="${2:?Missing directory}"; shift 2;;
    -h|--help) usage; exit 0;;
    *) echo "Unknown argument: $1" >&2; usage; exit 2;;
  esac
done
has_target() { [[ ",$TARGETS," == *",$1,"* ]]; }
say() { printf '[scrooge] %s\n' "$*"; }
warn() { printf '[error] %s\n' "$*" >&2; if (( ! DRY_RUN )); then exit 1; fi; }
execute() {
  if ((DRY_RUN)); then printf '[dry-run]'; printf ' %q' "$@"; printf '\n'; return 0; fi
  "$@"
}
backup() {
  local dst="$1"
  if [[ -f "$dst" ]]; then
    if ((DRY_RUN)); then say "Would back up $dst"; else cp -p "$dst" "$dst.bak.$(date +%Y%m%d-%H%M%S-%N)-$$"; fi
  fi
}
clone_once() {
  local url="$1" dst="$2"
  if [[ -d "$dst/.git" ]]; then
    local origin
    origin="$(git -C "$dst" remote get-url origin)" || { warn "Cannot inspect origin: $dst"; return 1; }
    if [[ "${origin%.git}" != "${url%.git}" ]]; then warn "Unexpected origin in $dst; preserving checkout"; return 1; fi
    say "Using existing checkout: $dst"; return
  fi
  if [[ -e "$dst" || -L "$dst" ]]; then warn "Refusing to replace existing non-Git path: $dst"; return 1; fi
  if ! command -v git >/dev/null; then warn "git missing, cannot clone $url"; return 1; fi
  execute mkdir -p "$(dirname "$dst")"
  execute git clone --depth 1 "$url" "$dst"
}
copy_skill_dir() {
  local src="$1" dst="$2"
  [[ -d "$src" ]] || return
  if [[ -e "$dst" || -L "$dst" ]]; then return; fi
  execute mkdir -p "$(dirname "$dst")"
  execute cp -R "$src" "$dst"
}
manual_skill() {
  local src="$1" dst="$2" name="$3"
  [[ -e "$dst" || -L "$dst" ]] && return 0
  copy_skill_dir "$src" "$dst"
  if (( ! DRY_RUN )); then
    python3 "$ROOT/scripts/manual-skill.py" "$dst/SKILL.md" "$name"
  fi
}

IFS=',' read -r -a items <<< "$TARGETS"
if ((${#items[@]} == 0)) || [[ "$TARGETS" == ,* || "$TARGETS" == *, || "$TARGETS" == *,,* ]]; then warn 'Select at least one valid target'; exit 2; fi
for target in "${items[@]}"; do
  case "$target" in codex|agy|gemini) ;; *) warn "Invalid target: $target"; exit 2;; esac
done
say "Targets: $TARGETS; Windows and WSL are separate installations"
for command in git python3 "${items[@]}"; do
  if ! command -v "$command" >/dev/null; then warn "Missing prerequisite: $command; install it and retry"; fi
done
export PATH="$HOME_DIR/.local/bin:$PATH"

# 1. Ponytail — skills only. Do NOT install always-on Codex/Gemini plugins/hooks.
say "1/10 Ponytail (manual skill, no always-on hooks)"
PONY_SRC="$DATA_DIR/sources/ponytail"
if clone_once https://github.com/DietrichGebert/ponytail.git "$PONY_SRC"; then
  if ((DRY_RUN)); then say "Would copy the Ponytail skill directories into each selected agent"; else
    found_ponytail=0
    for skill in "$PONY_SRC"/skills/*; do
      [[ -f "$skill/SKILL.md" ]] || continue
      found_ponytail=1
      name="$(basename "$skill")"
      if has_target codex; then manual_skill "$skill" "${CODEX_HOME:-$HOME_DIR/.codex}/skills/$name" "$name"; fi
      if has_target agy; then manual_skill "$skill" "$HOME_DIR/.gemini/config/skills/$name" "$name"; fi
      if has_target gemini; then manual_skill "$skill" "$HOME_DIR/.gemini/skills/$name" "$name"; fi
    done
    ((found_ponytail)) || warn 'Ponytail checkout contains no skills'
  fi
else warn 'Ponytail installation failed'; fi

# 2. Graphify — isolated package when missing, register skills for each target.
say "2/10 Graphify"
if ! command -v graphify >/dev/null; then
  if command -v uv >/dev/null; then execute uv tool install graphifyy || warn "Graphify installation failed"
  elif command -v pipx >/dev/null; then execute pipx install graphifyy || warn "Graphify installation failed"
  else warn "Install uv or pipx, then run 'uv tool install graphifyy'"; fi
fi
if (( ! DRY_RUN )) && ! command -v graphify >/dev/null; then warn 'Graphify was installed but is not on PATH; add its tool bin directory and retry'; fi
if command -v graphify >/dev/null && (( ! DRY_RUN )); then
  temp_graphify="$(mktemp -d)"
  (cd "$temp_graphify" && HOME="$temp_graphify" CODEX_HOME="$temp_graphify/.codex" graphify install --platform codex) || warn 'Graphify skill extraction failed'
  [[ -f "$temp_graphify/.codex/skills/graphify/SKILL.md" ]] || warn 'Graphify did not produce a skill'
  if has_target codex; then manual_skill "$temp_graphify/.codex/skills/graphify" "${CODEX_HOME:-$HOME_DIR/.codex}/skills/graphify" graphify; fi
  if has_target agy; then manual_skill "$temp_graphify/.codex/skills/graphify" "$HOME_DIR/.gemini/config/skills/graphify" graphify; fi
  if has_target gemini; then manual_skill "$temp_graphify/.codex/skills/graphify" "$HOME_DIR/.gemini/skills/graphify" graphify; fi
  rm -rf -- "$temp_graphify"
elif ((DRY_RUN)); then say "Would register Graphify per target if available"; fi

# 3. Deploychan remote MCP. Do NOT create or host an MCP service.
say "3/10 Deploychan remote MCP"
if has_target codex; then
  if command -v codex >/dev/null; then
    if ((DRY_RUN)); then say 'Would verify or register Codex Deploychan'; else
    if codex mcp get deploychan >/dev/null 2>&1; then
      codex mcp get deploychan --json | python3 -c 'import json,sys; d=json.load(sys.stdin); assert d.get("transport",{}).get("url") == "https://mcp.deploychan.webcam/mcp", "Existing deploychan differs"' || warn 'Existing Codex Deploychan differs or is invalid'
    else backup "${CODEX_HOME:-$HOME_DIR/.codex}/config.toml"; execute codex mcp add deploychan --url "$URL" || warn "Codex MCP registration failed"; fi
    codex mcp get deploychan >/dev/null || warn 'Codex Deploychan verification failed'
    fi
  else warn "codex command missing; Codex MCP not configured"; fi
fi
if has_target agy; then
  if command -v python3 >/dev/null; then
    if ((DRY_RUN)); then say "Would merge Deploychan into ~/.gemini/config/mcp_config.json"; else
      SCROOGE_MCP_URL="$URL" python3 - <<'PY'
import json, os
from pathlib import Path
from datetime import datetime
p=Path.home()/'.gemini/config/mcp_config.json'
p.parent.mkdir(parents=True, exist_ok=True)
if p.exists():
    data=json.loads(p.read_text(encoding='utf-8-sig'))
    if not isinstance(data,dict): raise ValueError('MCP config root must be an object')
else: data={}
servers=data.setdefault('mcpServers',{})
if not isinstance(servers,dict): raise ValueError('mcpServers must be an object')
entry={'serverUrl':os.environ['SCROOGE_MCP_URL']}
if 'deploychan' in servers and servers['deploychan'] != entry:
    raise ValueError('Existing deploychan MCP differs; preserve it and resolve manually')
if 'deploychan' not in servers:
    if p.exists():
        import shutil
        shutil.copy2(p, str(p)+'.bak.'+datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
    servers['deploychan']=entry
    p.write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
print('AGY MCP configured:',p)
PY
    fi
  else warn "python3 missing, cannot safely merge AGY MCP config"; fi
  if (( ! DRY_RUN )); then agy mcp list | grep -Eq '^deploychan[[:space:]]' || warn 'AGY Deploychan registration verification failed'; fi
fi
gemini_mcp() {
  local name="$1" expected="$2"; shift 2
  local settings="$HOME_DIR/.gemini/settings.json" status=0
  if ((DRY_RUN)); then say "Would verify or register Gemini $name"; return; fi
  python3 "$ROOT/scripts/check-gemini-mcp.py" "$settings" "$name" "$expected" || status=$?
  case "$status" in
    0) say "Gemini $name already registered" ;;
    1) backup "$settings"; gemini mcp add --scope user "$name" "$@" || warn "Gemini $name registration failed" ;;
    *) warn "Gemini $name configuration conflicts" ;;
  esac
  python3 "$ROOT/scripts/check-gemini-mcp.py" "$settings" "$name" "$expected" || warn "Gemini $name verification failed"
}
if has_target gemini; then
  if command -v gemini >/dev/null; then gemini_mcp deploychan "$URL" --transport http "$URL"
  else warn 'gemini command missing; Gemini MCP not configured'; fi
fi


# 4. XERJ official local search engine + its own MCP stdio adapter.
# Only download checksummed GitHub releases; never start/index automatically.
say "4/10 XERJ (verified upstream release, localhost-only by default)"
XERJ_BIN="$(command -v xerj || true)"
XERJ_BIN="${XERJ_BIN:-$HOME_DIR/.local/bin/xerj}"
XERJ_MCP="$DATA_DIR/bin/xerj-mcp.sh"
XERJ_START="$DATA_DIR/bin/xerj-start.sh"
if (( ! SKIP_XERJ )); then
  if [[ -x "$XERJ_BIN" ]]; then
    say "XERJ binary already installed: $XERJ_BIN"
  else
    case "$(uname -m)" in
      x86_64) XERJ_ARCH='x86_64-unknown-linux-gnu';;
      aarch64|arm64) XERJ_ARCH='aarch64-unknown-linux-gnu';;
      *) warn "Unsupported XERJ Linux architecture: $(uname -m)"; XERJ_ARCH='';;
    esac
    if [[ -n "$XERJ_ARCH" ]]; then
      if ((DRY_RUN)); then
        say "Would download and SHA-256 verify XERJ v1.0.0-rc.100 ($XERJ_ARCH)"
      elif command -v curl >/dev/null && command -v sha256sum >/dev/null; then
        (
          set -Eeuo pipefail
          temp="$(mktemp -d)"; trap 'rm -rf "$temp"' EXIT
          tag='v1.0.0-rc.100'
          filename="xerj-1.0.0-rc.100-$XERJ_ARCH.tar.gz"
          link="https://github.com/xerj-org/xerj/releases/download/$tag/$filename"
          curl -fLsS --retry 2 "$link" -o "$temp/$filename"
          curl -fLsS --retry 2 "$link.sha256" -o "$temp/$filename.sha256"
          expected="$(awk 'NR == 1 { print $1 }' "$temp/$filename.sha256")"
          actual="$(sha256sum "$temp/$filename" | awk '{ print $1 }')"
          [[ "$expected" =~ ^[a-fA-F0-9]{64}$ && "$expected" == "$actual" ]] || { echo 'XERJ SHA-256 verification failed' >&2; exit 1; }
          binary="$temp/xerj"
          python3 - "$temp/$filename" "$binary" <<'PY'
import pathlib, shutil, sys, tarfile
with tarfile.open(sys.argv[1], 'r:gz') as archive:
    matches = [m for m in archive.getmembers() if m.isfile() and pathlib.PurePosixPath(m.name).name == 'xerj']
    if len(matches) != 1:
        raise SystemExit('XERJ release must contain exactly one regular xerj binary')
    with archive.extractfile(matches[0]) as source, open(sys.argv[2], 'wb') as target:
        shutil.copyfileobj(source, target)
PY
          install -d "$HOME_DIR/.local/bin"
          install -m 0755 "$binary" "$XERJ_BIN"
        ) || warn "XERJ install failed; no MCP registration will be attempted"
      else
        warn "XERJ requires curl and sha256sum"
      fi
    fi
  fi
  if [[ -x "$XERJ_BIN" || "$DRY_RUN" -eq 1 ]]; then
    execute mkdir -p "$DATA_DIR/bin"
    for helper in xerj-mcp.sh xerj-start.sh; do
      dst="$DATA_DIR/bin/$helper"
      if [[ ! -f "$dst" ]] || ! cmp -s "$ROOT/scripts/$helper" "$dst"; then
        backup "$dst"
        execute install -m 0755 "$ROOT/scripts/$helper" "$dst"
      fi
    done
    if has_target codex; then
      if command -v codex >/dev/null; then
        if ((DRY_RUN)); then say 'Would verify or register Codex XERJ'; else
        if codex mcp get xerj >/dev/null 2>&1; then
          codex mcp get xerj --json | python3 -c 'import json,sys; d=json.load(sys.stdin); assert d.get("transport",{}).get("command") == sys.argv[1] and not d.get("transport",{}).get("args"), "Existing XERJ differs"' "$XERJ_MCP" || warn 'Existing Codex XERJ differs or is invalid'
        else backup "${CODEX_HOME:-$HOME_DIR/.codex}/config.toml"; execute codex mcp add xerj -- "$XERJ_MCP" || warn 'Codex XERJ MCP registration failed'; fi
        codex mcp get xerj >/dev/null || warn 'Codex XERJ verification failed'
        fi
      else warn 'codex missing; XERJ MCP not registered for Codex'; fi
    fi
    if has_target agy; then
      if ((DRY_RUN)); then say 'Would merge XERJ stdio MCP into AGY config'; else
        XERJ_MCP_SCRIPT="$XERJ_MCP" python3 - <<'PYCODE'
import json, os, shutil
from datetime import datetime
from pathlib import Path
p=Path.home()/'.gemini/config/mcp_config.json'
p.parent.mkdir(parents=True, exist_ok=True)
d=json.loads(p.read_text(encoding='utf-8-sig')) if p.exists() else {}
if not isinstance(d,dict): raise ValueError('AGY MCP root must be JSON object')
servers=d.setdefault('mcpServers',{})
if not isinstance(servers,dict): raise ValueError('AGY mcpServers must be JSON object')
entry={'command': os.environ['XERJ_MCP_SCRIPT'], 'args': []}
if 'xerj' in servers and servers['xerj'] != entry:
    raise ValueError('Existing XERJ MCP differs; preserving it')
if 'xerj' not in servers:
    if p.exists(): shutil.copy2(p,str(p)+'.bak.'+datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
    servers['xerj']=entry
    p.write_text(json.dumps(d,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
print('AGY XERJ MCP:',p)
PYCODE
      fi
      if (( ! DRY_RUN )); then agy mcp list | grep -Eq '^xerj[[:space:]]' || warn 'AGY XERJ registration verification failed'; fi
    fi
    if has_target gemini; then
      if command -v gemini >/dev/null; then gemini_mcp xerj "$XERJ_MCP" "$XERJ_MCP"
      else warn 'gemini missing; XERJ MCP not registered for Gemini'; fi
    fi
    say "Start authenticated XERJ manually: $XERJ_START"
    say 'No autoindex was performed. XERJ must be running before using MCP tools.'
  fi
fi

# 5. AAS — clone EXACT user-specified repository (not the similarly-named npm registry release).
say "5/10 AAS skills library (sickn33 upstream)"
AAS_SRC="$DATA_DIR/sources/agentic-awesome-skills"
if clone_once https://github.com/sickn33/agentic-awesome-skills.git "$AAS_SRC"; then
  if ((DRY_RUN)); then say "Would copy available AAS skills without replacing existing skills"; else
    found_aas=0
    for skill in "$AAS_SRC"/skills/*; do
      [[ -f "$skill/SKILL.md" ]] || continue
      found_aas=1
      name="$(basename "$skill")"
      if has_target codex; then copy_skill_dir "$skill" "${CODEX_HOME:-$HOME_DIR/.codex}/skills/$name"; fi
      if has_target agy; then copy_skill_dir "$skill" "$HOME_DIR/.gemini/config/skills/$name"; fi
      if has_target gemini; then copy_skill_dir "$skill" "$HOME_DIR/.gemini/skills/$name"; fi
    done
    ((found_aas)) || warn 'AAS checkout contains no skills'
  fi
else warn 'AAS installation failed'; fi
# Upstream AAS does not expose a checked-in aas-skill-selector; install an explicit local fallback if absent.
if has_target codex; then copy_skill_dir "$ROOT/skills/aas-skill-selector" "${CODEX_HOME:-$HOME_DIR/.codex}/skills/aas-skill-selector"; fi
if has_target agy; then copy_skill_dir "$ROOT/skills/aas-skill-selector" "$HOME_DIR/.gemini/config/skills/aas-skill-selector"; fi
if has_target gemini; then copy_skill_dir "$ROOT/skills/aas-skill-selector" "$HOME_DIR/.gemini/skills/aas-skill-selector"; fi

# 6. ShellCheck checks shell scripts and is installed from Ubuntu's package repository.
say '6/10 ShellCheck'
if command -v shellcheck >/dev/null; then
  say 'ShellCheck already installed'
elif ! command -v apt-get >/dev/null; then
  warn 'apt-get is unavailable; install ShellCheck using your system package manager and retry'
elif [[ $(id -u) -eq 0 ]]; then
  execute apt-get install -y shellcheck || warn 'ShellCheck installation failed; run apt-get update and retry'
elif command -v sudo >/dev/null; then
  execute sudo apt-get install -y shellcheck || warn 'ShellCheck installation failed; run sudo apt-get update and retry'
else
  warn 'sudo is unavailable; install ShellCheck as administrator with apt-get install shellcheck'
fi
if (( ! DRY_RUN )) && ! command -v shellcheck >/dev/null; then warn 'ShellCheck was not found after installation'; fi

# 7. Oh My Zsh is an Ubuntu/WSL-only optional shell layer.
say "7/10 Oh My Zsh (theme/plugins and auto-update; preserve unrelated .zshrc)"
if (( ! SKIP_ZSH )); then
  if ! command -v zsh >/dev/null; then warn 'Install zsh first (Ubuntu: sudo apt install zsh)'; fi
  if [[ ! -d "$HOME_DIR/.oh-my-zsh" ]]; then
    clone_once https://github.com/ohmyzsh/ohmyzsh.git "$HOME_DIR/.oh-my-zsh" || warn 'Oh My Zsh clone failed'
  fi
  ZSH_PLUGINS="${ZSH_CUSTOM:-$HOME_DIR/.oh-my-zsh/custom}/plugins"
  clone_once https://github.com/zsh-users/zsh-autosuggestions.git "$ZSH_PLUGINS/zsh-autosuggestions" || warn 'autosuggestions install failed'
  clone_once https://github.com/zsh-users/zsh-syntax-highlighting.git "$ZSH_PLUGINS/zsh-syntax-highlighting" || warn 'syntax-highlighting install failed'
  if command -v python3 >/dev/null; then
    if ((DRY_RUN)); then execute python3 "$ROOT/scripts/configure-omz.py" --dry-run;
    else python3 "$ROOT/scripts/configure-omz.py"; fi
  else warn 'python3 required to safely update only the .zshrc theme/plugins/update settings'; fi
  say 'Oh My Zsh auto-update mode enabled; installer reruns refresh the three managed .zshrc settings.'
fi

# 8. Obsidian: existing vault only; local upstream stdio MCP, read-only by default.
say '8/10 Obsidian (MCPVault + DataWeave + FTS5)'
if (( ! SKIP_OBSIDIAN )); then
  obsidian_args=(--targets "$TARGETS" --data-dir "$DATA_DIR/obsidian")
  if [[ -n "$OBSIDIAN_VAULT" ]]; then obsidian_args+=(--vault "$OBSIDIAN_VAULT"); fi
  if [[ -n "$OBSIDIAN_REPO" ]]; then obsidian_args+=(--repo "$OBSIDIAN_REPO"); fi
  if ((OBSIDIAN_WRITE)); then obsidian_args+=(--enable-writes); fi
  if ((DRY_RUN)); then
    execute python3 "$ROOT/scripts/install-obsidian.py" "${obsidian_args[@]}" --dry-run
  else
    python3 -c 'import sys; assert sys.version_info >= (3, 11), "Obsidian setup requires Python 3.11+"'
    python3 "$ROOT/scripts/install-obsidian.py" "${obsidian_args[@]}" || warn 'Obsidian installation failed'
  fi
fi

# 9. Global instructions BEFORE Choirboy so its managed blocks are not overwritten.
say "9/10 Global instructions"
PROMPT="$ROOT/prompts/linux/AGENTS.md"
write_prompt() {
  local dst="$1"
  if ((DRY_RUN)); then say "Would merge managed instructions into $dst with a backup"; return; fi
  python3 "$ROOT/scripts/merge-prompt.py" "$PROMPT" "$dst"
}
if has_target codex; then write_prompt "${CODEX_HOME:-$HOME_DIR/.codex}/AGENTS.md"; fi
# Gemini CLI and AGY CLI both read ~/.gemini/GEMINI.md as global context.
if has_target agy || has_target gemini; then write_prompt "$HOME_DIR/.gemini/GEMINI.md"; fi

# 10. Choirboy strictly last. Never activate the upstream author's personal lore.
say "10/10 Choirboy (last)"
if [[ -n "$CHOIRBOY_SOURCE" ]]; then
  if [[ ! -d "$CHOIRBOY_SOURCE" || ! -f "$CHOIRBOY_SOURCE/install.sh" ]]; then warn "--choirboy-source must be an existing personalized choirboy-prompt checkout"; exit 2; fi
  if [[ ! -s "$CHOIRBOY_SOURCE/.scrooge-personalized" || ! -s "$CHOIRBOY_SOURCE/lore.md" || ! -s "$CHOIRBOY_SOURCE/user.md" ]]; then warn 'Personalized Choirboy requires nonempty lore.md, user.md and .scrooge-personalized acknowledgement'; exit 2; fi
  if ((DRY_RUN)); then say "Would run personalized Choirboy installer last"; else
    (cd "$CHOIRBOY_SOURCE" && bash ./install.sh --target "$TARGETS") || warn "Choirboy installation failed. Inspect output."
  fi
else
  CHOIR_STAGE="$DATA_DIR/sources/choirboy-prompt"
  clone_once https://github.com/howdeploy/choirboy-prompt.git "$CHOIR_STAGE" || warn "Choirboy staging failed"
  say "Choirboy staged last at $CHOIR_STAGE but NOT activated. Personalize the memory files first."
  say "Never activate unmodified howdeploy/choirboy-prompt: it includes the author's personal lore."
fi
if ((DRY_RUN)); then say 'Dry run complete; no changes were made and integrations were not verified.'
else say 'Completed requested steps. Restart selected agents and review any manually staged integrations.'; fi
