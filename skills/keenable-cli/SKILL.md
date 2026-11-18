---
name: keenable-cli
description: Install and use the Keenable CLI for fast web search and page fetching from the terminal. Use when you need to search the web, fetch a page as clean markdown, or configure Keenable as the search provider (MCP) for AI clients like Claude Code or Cursor.
---

# Keenable CLI

`keenable` is a single-binary CLI for Keenable's web search and content APIs. Default output is YAML, designed to be parsed by agents.

Search and fetch work without login, on a pool shared per IP and capped at 1,000 requests an hour. Log in before doing real work: limits then count per organization, the hourly cap goes away, each call reports what it cost, and the first 100,000 requests a month are free.

## Installation

Homebrew (macOS / Linux):

```bash
brew install keenableai/tap/keenable-cli
```

Installer script (macOS / Linux, installs to `~/.cargo/bin` or `~/.local/bin`; two steps so no pipe is needed):

```bash
curl --proto '=https' --tlsv1.2 -LsSf -o /tmp/keenable-install.sh \
  https://github.com/keenableai/keenable-cli/releases/latest/download/keenable-cli-installer.sh
sh /tmp/keenable-install.sh
```

The installer updates PATH for future shells only. To use `keenable` in the current shell, source the env file it wrote (or restart the shell). Sourcing both covers either install dir — `~/.cargo/env` may exist from rustup even when keenable went to `~/.local/bin`:

```bash
[ -f "$HOME/.cargo/env" ] && . "$HOME/.cargo/env"
[ -f "$HOME/.local/bin/env" ] && . "$HOME/.local/bin/env"
```

Windows (PowerShell):

```powershell
Invoke-WebRequest -OutFile $env:TEMP\keenable-install.ps1 `
  https://github.com/keenableai/keenable-cli/releases/latest/download/keenable-cli-installer.ps1
& $env:TEMP\keenable-install.ps1
```

From source: `cargo install --git https://github.com/keenableai/keenable-cli`

Verify with `keenable --version`. Update via `brew upgrade keenable-cli` or by re-running the installer.

## Authentication (recommended)

```bash
# Device-code flow: prints a link + code for the user to approve. Works in headless/agent environments.
keenable login
# Save an API key directly (CI, servers)
keenable login --api-key keen_***
# Clear credentials from ~/.keenable/
keenable logout
```

Any command also accepts `--api-key <KEY>`, overriding the stored key.

## Configure MCP in AI clients

Supported clients: Claude Code, Cursor, Windsurf, Codex, OpenCode.

Claude Desktop is not one of them — its config file takes stdio servers only. Add the
Keenable Web Search connector in Claude's Connectors Directory, or, to send an API key,
configure the `npx -y @keenable/mcp` bridge by hand in `claude_desktop_config.json`. See
https://docs.keenable.ai/mcp-server.md

Run `keenable login` first: `configure-mcp` writes the credentials the CLI holds at the
time into each client's config, so configure after logging in rather than before.

```bash
# Show which clients are detected/configured
keenable configure-mcp
# Configure all detected clients
keenable configure-mcp --all
# One client (also: --cursor, --codex, ...)
keenable configure-mcp --claude-code
# Remove Keenable MCP, restore defaults
keenable reset --all
```

## Search

```bash
# YAML output (for agents)
keenable search "rust async patterns"
# Pretty output (for humans)
keenable search "rust async patterns" -p
# Restrict to one site
keenable search "anthropic" --site techcrunch.com
# Date filter
keenable search "AI news" --published-after 2026-05-01
# Point-in-time search: the index as it stood then
keenable search "champions league final" --query-time 2025-05-30T00:00:00Z
```

Date filters — `--published-after/-before` (publication date), `--acquired-after/-before` (index date) — accept `YYYY-MM-DD`, ISO 8601 datetimes, or relative values (`12h`, `7d`, `3mo`, `1y`).

`--query-time` excludes pages acquired after that instant, so the answer is the one
the index would have given then rather than today's answer filtered down. It does
not re-base relative deltas: with `--query-time` set, `--published-after 30d` still
means thirty days before now. Pair `--query-time` with absolute dates.

Each YAML result has `title`, `url`, `snippet`, `acquired_at` and, when known, `published_at`. Read `snippet` for the page text; there is no `description` field.

## Fetch

```bash
# YAML: url, title, content (markdown), total_chars, truncated
keenable fetch https://example.com
```

## CLI configuration

```bash
# View all settings
keenable config
```

## Links

- MCP endpoint: https://api.keenable.ai/mcp
- Full docs: https://docs.keenable.ai (append `.md` to any docs URL for markdown)
- CLI reference: https://docs.keenable.ai/cli.md
