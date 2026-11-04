# Archived task-specific skills

Most directories preserve earlier KISA skill publications and are not part of the Scrooge Stack installation. The `aas-skill-selector` directory is the Scrooge-maintained fallback selector. See the [Scrooge Stack README](../README.md).

Review a skill's instructions, dependencies and runtime assumptions before choosing to use it. Install only a specifically selected skill:

```bash
./scripts/install-archived-skill.sh <skill-name> --claude
./scripts/install-archived-skill.sh <skill-name> --codex
./scripts/install-archived-skill.sh <skill-name> --hermes
```

Run the archived-skill installer from the repository root. Bulk installation is disabled.
