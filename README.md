# PAL Subagent Skill

[English](README.md) | [简体中文](README_zh.md)

## Source

Based on the open-source git project [PAL MCP Server](https://github.com/BeehiveInnovations/pal-mcp-server). The install script clones it into `pal-mcp-server/` under this skill directory, with `server.py` as the entry point.

## Overview

This project is a **one-click skill for quickly configuring and using PAL MCP Server**:

- One-click install/uninstall scripts (`scripts/`) that automatically set up the environment, install dependencies, and register the MCP server
- Provides the main agent with a "plan-execute" separated subagent delegation capability: via the `clink` tool of PAL MCP, simple tasks are delegated to an isolated subagent (**Codex CLI or Claude Code**), saving main-context tokens

## Usage

### 1. One-click Installation

Prerequisites:

| Dependency | Required | Notes |
|------|--------|------|
| conda (Miniconda/Anaconda) | Yes | Python environment management |
| git | Yes | Clones the PAL MCP Server repo |
| Codex CLI / Claude Code | At least one | The actual executor of subagent tasks (Codex must be logged in); MCP registration target |
| Network | Yes | First installation needs access to GitHub |

```bash
# Interactive (press Enter to use the default env name pal-mcp-server)
bash <skill-dir>/scripts/pal-subagent-install.sh

# Non-interactive (specify env name)
bash <skill-dir>/scripts/pal-subagent-install.sh --env-name pal-mcp-server
```

The script automatically: clones the repo → writes `.env` (custom API endpoints for local models; kept if it already exists) → creates/reuses a conda env (Python 3.12) → installs dependencies → registers the Claude MCP → backs up and writes the Codex `config.toml`.

### 2. Manual MCP Setup (without running the script)

First prepare the server (clone the PAL MCP Server repo and install dependencies):

```bash
git clone --depth 1 https://github.com/BeehiveInnovations/pal-mcp-server.git
conda create -n pal-mcp-server python=3.12 -y
conda run -n pal-mcp-server python -m pip install "mcp>=1.28,<2" -r requirements.txt

# Get the absolute path of the conda env's Python, replace <PYTHON> below
conda run -n pal-mcp-server python -c 'import sys; print(sys.executable)'
```

All paths below are placeholders: `<PYTHON>` stands for `/path/to/pal-mcp-server/bin/python`, and `server.py` stands for `/path/to/pal-mcp-server/server.py`.

**Trae / generic MCP clients** (add in the editor's MCP config):

```json
{
  "mcpServers": {
    "pal": {
      "command": "/path/to/pal-mcp-server/bin/python",
      "args": [
        "/path/to/pal-mcp-server/server.py"
      ]
    }
  }
}
```

**Claude Code**:

```bash
claude mcp add pal -s user -- /path/to/pal-mcp-server/bin/python /path/to/pal-mcp-server/server.py
```

**Codex** (append to `~/.codex/config.toml`):

```toml
[mcp_servers.pal]
type = "stdio"
command = "/path/to/pal-mcp-server/bin/python"
args = ["/path/to/pal-mcp-server/server.py"]
tool_timeout_sec = 1200
```

### 3. Activation & Verification

After adding the MCP server, **restart the session** for the registration to take effect. The environment is ready once the PAL tools (e.g. `clink`) appear in the main agent's tool list, and tasks can be delegated directly.

CLI self-verification (key point to check):

```bash
# Claude: expect "Status: ✔ Connected"; "✗ Failed to connect" means registration failed
claude mcp get pal

# Codex: expect "enabled: true"; "codex mcp list" should show Status = enabled
codex mcp get pal
```

### 4. Uninstallation

```bash
bash <skill-dir>/scripts/pal-subagent-uninstall.sh
```

Confirm item by item: Claude MCP registration / Codex config section / conda env / cloned repo. For manual uninstall, remove accordingly: `claude mcp remove pal -s user`, the `[mcp_servers.pal]` section in `~/.codex/config.toml`, and the MCP config entry in the editor.

## More

- Detailed installation steps, parameters, and troubleshooting: [references/install-guide.md](references/install-guide.md)
- Detailed uninstall guide: [references/uninstall-guide.md](references/uninstall-guide.md)
