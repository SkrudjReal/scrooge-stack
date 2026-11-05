<div align="center">

# ✦ Scrooge Stack

**One setup. Three coding agents. Your tools and context.**

[![Issues](https://img.shields.io/github/issues/SkrudjReal/scrooge-stack?style=for-the-badge&color=f0abfc&labelColor=19152e)](https://github.com/SkrudjReal/scrooge-stack/issues)
[![Pull requests](https://img.shields.io/github/issues-pr/SkrudjReal/scrooge-stack?style=for-the-badge&label=Pull%20requests&color=a5b4fc&labelColor=19152e)](https://github.com/SkrudjReal/scrooge-stack/pulls)
[![Stars](https://img.shields.io/github/stars/SkrudjReal/scrooge-stack?style=for-the-badge&color=c4b5fd&labelColor=19152e)](https://github.com/SkrudjReal/scrooge-stack/stargazers)
[![Forks](https://img.shields.io/github/forks/SkrudjReal/scrooge-stack?style=for-the-badge&color=a5b4fc&labelColor=19152e)](https://github.com/SkrudjReal/scrooge-stack/forks)

<img src="assets/scrooge-stack-cosmic-command-center.png" alt="Scrooge Stack: a cosmic overview of coding agents, knowledge tools and integrations" width="100%">

[Quick start](#quick-start) · [The stack](#the-stack) · [Documentation](docs/SETUP.md) · [Report a bug](https://github.com/SkrudjReal/scrooge-stack/issues/new)

<sub>Windows · WSL · Ubuntu — installation commands below.</sub>

</div>

---

Scrooge Stack sets up skills, MCP integrations and global instructions for **Codex, Antigravity and Gemini CLI**, while preserving existing configuration.

## The stack

| | Tools | Purpose |
| :--- | :--- | :--- |
| ✦ Workflow | [Ponytail](https://github.com/DietrichGebert/ponytail), [AAS](https://github.com/sickn33/agentic-awesome-skills) | Focused skills and task-based selection |
| ◇ Search | [Graphify](https://github.com/Graphify-Labs/graphify), [XERJ](https://github.com/xerj-org/xerj), [Deploychan](https://github.com/howdeploy/deploychan_mcp) | Knowledge graphs, local search and a technical catalog |
| ✧ Knowledge | [MCPVault](https://github.com/bitbonsai/mcpvault), [ObsidianDataWeave](https://github.com/howdeploy/ObsidianDataWeave), [Choirboy](https://github.com/howdeploy/choirboy-prompt) | Obsidian workflows and optional personal context |
| ⌘ Environment | [ShellCheck](https://www.shellcheck.net/), [Oh My Zsh](https://github.com/ohmyzsh/ohmyzsh) | Shell checks and optional Ubuntu/WSL configuration |
| ♡ Presentation | [GitHub Markdown style](skills/github-markdown-style/SKILL.md) | Your [reference style](https://github.com/SkrudjReal/example-git-markdown), checked by the agent before each GitHub push |

Ponytail and Graphify activate only when requested. Choirboy is staged without activation until personalized.

## Quick start

Install **Git and your selected agent CLIs** first. Choose only the agents you have installed.

| Environment | Prerequisites |
| :--- | :--- |
| Ubuntu / WSL | Python 3, curl, tar, sha256sum; Graphify or uv/pipx; zsh unless skipped |
| Windows 10/11 | PowerShell 5.1+, Git and the selected agent CLIs |
| Obsidian integration | Python 3.11+ with venv/pip, Node.js 22.12+ with npm, an existing vault |

**Ubuntu / WSL**

```bash
git clone https://github.com/SkrudjReal/scrooge-stack.git
cd scrooge-stack
bash install.sh --dry-run --targets codex,agy
bash install.sh --targets codex,agy
```

**Windows · PowerShell**

```powershell
git clone https://github.com/SkrudjReal/scrooge-stack.git
cd scrooge-stack
powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 -DryRun -Targets 'codex,agy'
powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 -Targets 'codex,agy'
```

Add `gemini` to the target list when installed. Restart your agents after setup. Windows and WSL need separate installations.

<details>
<summary>✧ Optional components and existing Obsidian vaults</summary>

| Option | Ubuntu / WSL | PowerShell |
| :--- | :--- | :--- |
| Skip XERJ | `--skip-xerj` | `-SkipXerj` |
| Skip Obsidian | `--skip-obsidian` | `-SkipObsidian` |
| Skip Oh My Zsh | `--skip-zsh` | Not installed on Windows |
| Set vault | `--obsidian-vault "/path/to/Vault"` | `-ObsidianVault 'C:\path\to\Vault'` |
| Obsidian only | `--only-obsidian` | `-OnlyObsidian` |

New Obsidian setups are read-only. [Write access and backup details →](docs/SETUP.md#obsidian-knowledge-integration)

</details>

> [!NOTE]
> Configuration changes get backups; existing skills are preserved. Reruns reuse source checkouts rather than updating them. A dry run previews actions without testing integrations.

---

## Documentation

[Setup & configuration](docs/SETUP.md) · [Updates & recovery](docs/SETUP.md#updates-rollback-and-troubleshooting) · [Checks & limitations](docs/SETUP.md#verification-and-limitations) · [Obsidian verification](obsidian/VERIFICATION.md)

Based on [KISA Stack](https://github.com/howdeploy/kisa-stack). Upstream attribution and licenses remain with their authors. [Archived skills](skills/README.md) are separate from the main installer.

<div align="center">

✦ **Build your stack. Keep your context.**

</div>
