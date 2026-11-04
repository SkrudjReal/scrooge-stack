# Integrations

Scrooge Stack integrates existing upstream projects, not a proprietary MCP server. See the [README](README.md) for installation, explicit activation, verification, and rollback.

| Integration | Source | Role |
| --- | --- | --- |
| Ponytail | https://github.com/DietrichGebert/ponytail | Explicitly invoked skills |
| Graphify | https://github.com/Graphify-Labs/graphify | Optional code and document graph |
| KISA Deploychan | https://github.com/howdeploy/deploychan_mcp | Remote technical catalog |
| XERJ | https://github.com/xerj-org/xerj | Local search and native MCP |
| AAS | https://github.com/sickn33/agentic-awesome-skills | Skill library; selector maintained in this repository |
| ShellCheck | https://www.shellcheck.net/ | Shell script analysis; installed on Ubuntu/WSL |
| Oh My Zsh | https://github.com/ohmyzsh/ohmyzsh | Linux/WSL shell |
| Choirboy | https://github.com/howdeploy/choirboy-prompt | User-owned project context, staged last |

Existing integrations and personal context are not removed or automatically updated.

## Obsidian knowledge

MCPVault 0.18.3 provides a local stdio connection to an existing vault (read-only by default). ObsidianDataWeave adds native FTS5 recall, atomic notes, MOCs, duplicate previews and isolated LLM Wiki. Both install scripts use `scripts/install-obsidian.py`; select a vault explicitly if discovery is ambiguous. No REST plugin, embeddings, extra MCP bridge or account login is required. See the README and `obsidian/VERIFICATION.md`.
