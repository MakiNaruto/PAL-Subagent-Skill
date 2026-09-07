# PAL Subagent Skill

[English](README.md) | [简体中文](README_zh.md)

## 项目来源

基于开源 git 项目 [PAL MCP Server](https://github.com/BeehiveInnovations/pal-mcp-server)。安装脚本会将其克隆到本 skill 目录下的 `pal-mcp-server/`，入口为 `server.py`。

## 项目定位

本项目是 PAL MCP Server 的**快速配置与使用的一键化 skill**：

- 提供一键安装 / 卸载脚本（`scripts/`），自动完成环境创建、依赖安装与 MCP 注册
- 为主 agent 提供"规划-执行"分离的子 agent 委派能力：通过 PAL MCP 的 `clink` 工具，将简单任务委派给隔离子 agent（**Codex CLI 或 Claude Code**），节省主上下文 token

## 使用说明

### 1. 一键安装

前置要求：

| 依赖 | 必需性 | 说明 |
|------|--------|------|
| conda（Miniconda/Anaconda） | 必需 | Python 环境管理 |
| git | 必需 | 克隆 PAL MCP Server 仓库 |
| Codex CLI / Claude Code | 至少其一 | 子 agent 的实际执行者（Codex 需已登录）；MCP 注册目标 |
| 网络 | 必需 | 首次安装需访问 GitHub |

```bash
# 交互式（回车使用默认环境名 pal-mcp-server）
bash <本skill目录>/scripts/pal-subagent-install.sh

# 非交互式（指定环境名）
bash <本skill目录>/scripts/pal-subagent-install.sh --env-name pal-mcp-server
```

脚本自动完成：克隆仓库 → 写入 `.env`（本地模型自定义 API 端点，已存在则保留）→ 创建/复用 conda 环境（Python 3.12）→ 安装依赖 → 注册 Claude MCP → 备份并写入 Codex `config.toml`。

### 2. MCP 添加方法（手动添加）

不跑脚本时，先准备好 server（已克隆 PAL MCP Server 仓库并安装依赖）：

```bash
git clone --depth 1 https://github.com/BeehiveInnovations/pal-mcp-server.git
conda create -n pal-mcp-server python=3.12 -y
conda run -n pal-mcp-server python -m pip install "mcp>=1.28,<2" -r requirements.txt

# 获取 conda 环境的 Python 绝对路径，替换下方 <PYTHON>
conda run -n pal-mcp-server python -c 'import sys; print(sys.executable)'
```

以下路径均为示例占位：`<PYTHON>` 即 `/path/to/pal-mcp-server/bin/python`，`server.py` 即 `/path/to/pal-mcp-server/server.py`。

**Trae / 通用 MCP 客户端**（编辑器 MCP 配置中添加）：

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

**Claude Code**：

```bash
claude mcp add pal -s user -- /path/to/pal-mcp-server/bin/python /path/to/pal-mcp-server/server.py
```

**Codex**（`~/.codex/config.toml` 追加）：

```toml
[mcp_servers.pal]
type = "stdio"
command = "/path/to/pal-mcp-server/bin/python"
args = ["/path/to/pal-mcp-server/server.py"]
tool_timeout_sec = 1200
```

### 3. 生效与验证

MCP 添加完成后**重启会话**使注册生效。主 agent 工具列表中出现 PAL 的工具（如 `clink`）即环境就绪，可直接委派任务。

命令行自行验证（关注核心输出）：

```bash
# Claude：期望 "Status: ✔ Connected"；若为 "✗ Failed to connect" 则注册失败
claude mcp get pal

# Codex：期望 "enabled: true"；"codex mcp list" 中 Status 列应为 enabled
codex mcp get pal
```

### 4. 卸载

```bash
bash <本skill目录>/scripts/pal-subagent-uninstall.sh
```

逐项交互确认：Claude MCP 注册 / Codex 配置段 / conda 环境 / 克隆的仓库。手动卸载则对应移除：`claude mcp remove pal -s user`、`~/.codex/config.toml` 中 `[mcp_servers.pal]` 段、编辑器 MCP 配置项。

## 更多

- 详细安装步骤、参数与故障排查：[references/install-guide.md](references/install-guide.md)
- 卸载详细说明：[references/uninstall-guide.md](references/uninstall-guide.md)
