# PAL Subagent Skill

English | [简体中文](README_zh.md)

Use [PAL MCP Server](https://github.com/BeehiveInnovations/pal-mcp-server)'s `clink` tool to delegate well-defined tasks to an authenticated Codex CLI or Claude Code.

The installer puts the skill in **both clients' user skill directories**, while sharing one PAL checkout, `.env`, and conda environment. A fresh installation places PAL inside the initiating client's installed skill directory. Existing installations are adopted rather than cloned again.

## Install

Review the plan with the user first:

```bash
bash scripts/pal-subagent-install.sh --client claude --env-name pal-mcp-server --dry-run
```

After the user authorizes the concrete plan:

```bash
bash scripts/pal-subagent-install.sh --client claude --env-name pal-mcp-server --yes
```

Use `--client codex` when initiating from Codex. Interactive terminal execution can omit `--yes`; noninteractive execution requires prior authorization and `--yes`.

The existing conda environment is reused; only a missing environment is created with Python 3.12. The setup helper needs Python 3.11+, normally provided by conda base. Install at least one of Codex CLI or Claude Code. A missing client's skill is still installed; its MCP registration is skipped until the CLI is installed and setup is rerun.

- Claude: `~/.claude/skills/pal-subagent`.
- Codex: reuse the saved path, otherwise an existing `$CODEX_HOME/skills` (default `~/.codex/skills`), or `~/.agents/skills` for fresh installations. Override with `--codex-skills-dir`.
- Shared record: `~/.config/pal-subagent/install.json`, containing paths and environment metadata, never credentials.
- Select a shared checkout with `--server-dir /absolute/path/pal-mcp-server`.
- Add `--update` only when explicitly requesting PAL source/dependency updates.

Both clients receive lightweight skill files, excluding the PAL checkout, credentials and logs. Existing `.env` files are retained; changed configuration and skill files are backed up. Conflicting service paths stop installation until explicitly resolved. The installer verifies a real MCP handshake and discovery of `clink`.

## Invoke

Restart/reload clients after installation:

```text
Claude: /pal-subagent Run project tests and summarize failures
Codex:  $pal-subagent Run project tests and summarize failures
```

`clink` uses CLI authentication. Other PAL model tools need a working provider; the default local endpoint is a placeholder. Each stdio MCP client may launch its own process, sharing the same code and environment.

## Uninstall

```bash
bash scripts/pal-subagent-uninstall.sh --client claude --dry-run
# After authorization: remove only Claude's skill/MCP, retaining Codex and shared resources
bash scripts/pal-subagent-uninstall.sh --client claude --yes
```

Use `--client both` for both clients. Add `--remove-server` only when explicitly requesting deletion of the shared checkout; remaining references block deletion. The conda environment is always retained.

Detailed instructions: [installation](references/install-guide.md), [uninstallation](references/uninstall-guide.md).

Development verification (Python 3.11+): `python -m unittest discover -s tests -v`.
