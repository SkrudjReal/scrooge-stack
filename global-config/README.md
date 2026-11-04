# Global instructions

The canonical OS-specific templates are [Linux/WSL](../prompts/linux/AGENTS.md) and [Windows](../prompts/windows/AGENTS.md). The installers merge the appropriate template into a marked block in Codex and Gemini/AGY CLI global instruction files, backing up existing files before modification. They do not replace other user instructions or Choirboy-managed blocks.

`AGENTS.md` and `CLAUDE.md` in this directory are Linux-oriented reference copies; Claude is not an installer target. Legacy hook examples are retained for historical reference and are not installed. Review and merge instructions yourself if an agent uses a different path.
