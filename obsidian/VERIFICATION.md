# Obsidian integration verification

Checked on 2026-11-04. The integration is portable; no personal vault content,
user-specific configuration paths, login state, tokens or runtime databases are
part of the published repository.

## Reproduce local checks

```bash
python3 -m unittest discover -s tests -v
shellcheck install.sh scripts/*.sh
bash -n install.sh
git diff --check
```

On native Windows PowerShell 5.1:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\windows-integration.ps1
```

Opt-in **real download/install tests**, using isolated synthetic profiles:

```bash
python3 tests/obsidian-live.py
```

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\obsidian-live.ps1
```

The live test requires Python 3.11+, Node >=22.12/npm and Git. It downloads
upstream packages into a retained temporary profile, never the real vault or
agent configs. It performs a read-only install, explicit write enablement with
SHA-256 backup, and an ordinary rerun. All three selected host configs are
parsed/written, and repeated runs preserve existing settings and enabled writes.
The retained fixture path is printed. No model generation or account login runs.

## Actual results

- Linux unit suite: **35 tests passed**, including dry-run isolation, shell flag
  forwarding, failure ordering, vault discovery/ambiguity, all three host config
  merges, malformed/conflicting config refusal, multiline TOML preservation,
  UTF-8/BOM/CRLF handling, backups and no silent vault creation.
- ShellCheck, Bash syntax and diff whitespace checks passed.
- Windows PowerShell 5.1: parsing and mocked installation/reinstallation,
  config/UTF-8 preservation, flags passed to the shared Python helper, failure
  propagation and checksum rejection passed.
- Real Linux isolated install: official Git clone, venv/pip, npm MCPVault, initial
  read-only registration, write transition with verified backup and repeat install
  passed. Final native probes also passed with the portable patches applied.
- Real **native Windows Python 3.12.10 + Node** isolated install: the same sequence
  passed through `tests/obsidian-live.ps1`, including paths containing spaces.
  This is real dependency installation and stdio/native processing, not a mock
  of Obsidian or its filesystem.
- Every install probes actual MCP stdio initialization/tool discovery, hidden and
  rejected writes in read-only mode, creation/patch/read/frontmatter preservation,
  wiki-links, and rejection of `../` reads/writes against an outside sentinel.
- Native probes verify FTS5 build/update/search, nested folder-filter paths,
  atomic-plan rendering/writing, MOC creation/update/replay, duplicate candidate
  detection, Wiki init/ingest/index regeneration/strict lint. They run only on
  temporary vaults and never invoke an LLM.
- Pinned DataWeave plus all compatibility patches and copied regression tests:
  **222 pytest tests passed on Linux**. Installers do not install pytest or run
  this developer suite automatically; they run the focused native/MCP probes.

## Compatibility problems found and fixed

The initial Windows live checks failed, rather than claiming a successful install:

1. Python's Windows code-page output could not be decoded by UTF-8 subprocess
   consumers. The installer forces `PYTHONUTF8=1` and `PYTHONIOENCODING=utf-8` for
   child commands; the installed skill documents the same per-terminal setting.
2. Upstream serializes native Windows relative paths with backslashes while Wiki
   contracts and folder filters expect `/`. The portable-path patch uses POSIX
   relative paths for stored index keys and Wiki snapshots/routing/linting.
3. Upstream interpolates Windows source paths into double-quoted YAML without
   escaping `\`. The YAML patch uses JSON string quoting (valid YAML), preserving
   backslashes, quotes and newlines in source attribution.

The original integration patch also fixes excluded cache traversal, external
symlink scanning, generated destination containment, and the missing atom-plan
JSON prompt contract. Patches are applied only after `git apply --check` and
recognized on reruns with reverse checks. Existing conflicting edits are left
for manual review; there is no reset, checkout of existing work, or silent pull.

## Limits

The user's native Windows and WSL profiles were configured separately for AGY
and Gemini. Both real vault backups verified 3,379 files, both FTS5 indexes
contained 2,259 Markdown notes, and the temporary MCP/native probes passed in
each environment. Existing MCP entries, hooks and instruction text were checked
against private before-snapshots; Codex configuration stayed byte-identical.
AGY `mcp list` discovers the enabled native-path server on both hosts. The new
standalone Obsidian instruction block and both host skill copies were verified.
The final Linux isolated install/reinstall also passed with instruction merging.

Initial AGY model-driven read attempts timed out after 70 seconds. A WSL retry
with `gemini-3.8-flash-low` in the default execution mode succeeded and returned
the 11 Markdown files in the requested directory. Plan mode only generated an
approval plan. Native Windows retries timed out without a result, including
with the explicit model; server discovery and direct stdio tests do not prove
that model-driven client path. Gemini CLI is absent on both profiles, so its
config is ready but a live Gemini client call was not tested.

Full installation of every other Scrooge component on a real Windows user profile
was not repeated. Live model atomization/Wiki compilation, account integrations,
and interactive IDE reload were not verified. Native processing/formatting and transport are verified; model
quality and remote account access remain separate. Native scripts need an already
installed Codex for their `--backend codex` LLM step.

Backups deliberately exclude `.smart-env`, `.git`, `.trash`; symlinks are copied
without following them. Hash verification fails safely before a new write-mode
configuration is committed. Existing compatible write-enabled MCP entries are
preserved; this installer does not revoke previous authorization.
