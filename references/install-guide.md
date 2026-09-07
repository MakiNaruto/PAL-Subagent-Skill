# PAL Subagent 安装指南

本文档是 `scripts/pal-subagent-install.sh` 的详细说明，仅在需要了解安装细节或排查故障时阅读。

## 架构

```
Claude Code / 主 agent
    │
    ▼
PAL MCP Server（MCP 服务，名称: pal）
    │
    ▼
Codex CLI（作为隔离子 agent 执行任务）
```

## 前置要求

| 依赖 | 必需性 | 说明 |
|------|--------|------|
| conda（Miniconda/Anaconda） | 必需 | Python 环境管理 |
| git | 必需 | 克隆 PAL MCP Server 仓库 |
| Claude Code | 至少其一 | 注册 MCP 服务；两者都没有时安装会失败 |
| Codex CLI | 至少其一 | 子 agent 的实际执行者，需已登录（`codex` 可正常启动） |
| 网络 | 必需 | 首次安装需访问 GitHub |

Codex CLI 安装方式：`npm install -g @openai/codex`

## 快速开始

```bash
# 交互式（会询问环境名，回车使用默认 pal-mcp-server）
bash <skill目录>/scripts/pal-subagent-install.sh

# 非交互式（指定环境名，适合自动化/agent 调用）
bash <skill目录>/scripts/pal-subagent-install.sh --env-name pal-mcp-server
```

安装完成后**重启 CLI 会话**，MCP 注册才会生效。验证：

```bash
claude mcp list   # 应看到 pal
```

## 参数说明

| 参数 | 说明 |
|------|------|
| `--env-name NAME` | 指定要创建/复用的 conda 环境名，跳过交互提示 |
| `-h`, `--help` | 显示帮助 |

未提供 `--env-name` 且无 TTY（非交互环境）时，自动使用默认环境名 `pal-mcp-server`。

## 脚本执行内容

按顺序执行以下步骤（与 `steup.sh` 逻辑一致）：

1. **确认环境名**：默认 `pal-mcp-server`，可自定义
2. **检查 conda**：未安装则报错退出
3. **获取仓库**：克隆 `https://github.com/BeehiveInnovations/pal-mcp-server.git`（`--depth 1`）到 skill 目录下的 `pal-mcp-server/`；已存在则 `git pull --ff-only` 更新
4. **校验仓库内容**：确认 `server.py`、`requirements.txt` 存在
5. **创建/复用 conda 环境**：Python `3.12`
6. **安装依赖**：`mcp>=1.28,<2` + `requirements.txt`
7. **注册 Claude MCP**：`claude mcp add pal -s user`（user 级，全局可用）
8. **注册 Codex MCP**：备份 `~/.codex/config.toml` 后写入 `[mcp_servers.pal]` 段（`tool_timeout_sec = 1200`）

Claude 或 Codex 任一未安装时跳过对应注册并警告（不中断）；两者都缺失时报错退出。

## 手动安装（脚本失败时）

```bash
# 1. 克隆仓库到 skill 目录
git clone --depth 1 https://github.com/BeehiveInnovations/pal-mcp-server.git \
    <skill目录>/pal-mcp-server
cd <skill目录>/pal-mcp-server

# 2. 写入 .env（本地模型自定义 API 端点，已存在则跳过）
cat > .env <<'EOF'
# Option 3: Use custom API endpoints for local models (Ollama, vLLM, LM Studio, etc.)
CUSTOM_API_URL=http://localhost:11434/v1                # Ollama example
CUSTOM_API_KEY=safe-code                                # Empty for Ollama (no auth needed)
CUSTOM_MODEL_NAME=llama3.2                              # Default model name
EOF

# 3. 创建环境并安装依赖
conda create -n pal-mcp-server python=3.12 -y
conda run -n pal-mcp-server python -m pip install "mcp>=1.28,<2" -r requirements.txt

# 4. 注册 Claude MCP（PYTHON 替换为实际路径，见下方说明）
claude mcp remove pal -s user || true
claude mcp add pal -s user \
    -e "PATH=/usr/local/bin:/usr/bin:/bin:${HOME}/.local/bin" \
    -- <PYTHON> <skill目录>/pal-mcp-server/server.py

# 4. Codex：编辑 ~/.codex/config.toml，追加
# [mcp_servers.pal]
# type = "stdio"
# command = "<PYTHON>"
# args = ["<skill目录>/pal-mcp-server/server.py"]
# cwd = "<skill目录>/pal-mcp-server"
# tool_timeout_sec = 1200
```

获取 conda 环境的 Python 路径：

```bash
conda run -n pal-mcp-server python -c 'import sys; print(sys.executable)'
```

## 关于 API Key 与 .env

安装脚本会在 `pal-mcp-server/.env` 中写入本地模型自定义端点配置（已存在时不覆盖）：

```dotenv
CUSTOM_API_URL=http://localhost:11434/v1    # 自定义 API 端点（默认 Ollama）
CUSTOM_API_KEY=safe-code                    # 按需修改，Ollama 可留空
CUSTOM_MODEL_NAME=llama3.2                  # 默认模型名
```

- 使用其他本地服务（vLLM / LM Studio）或远端自定义端点时，手动编辑上述三个值
- **仅使用 `clink` 委派 Codex 子 agent**：无需任何 provider API key，认证由 Codex CLI 自身的登录态完成
- **需要 PAL 其他工具**（`chat`/`thinkdeep`/`consensus` 等）：在 `pal-mcp-server/.env` 中配置对应 provider 的 API key（参考仓库内 `.env.example`）

## 故障排查

| 现象 | 原因与处理 |
|------|-----------|
| `conda was not found` | 未安装 Miniconda/Anaconda，或未 `conda init`。安装后重开终端再试 |
| `git clone` 失败 | 网络不通或无法访问 GitHub；配置代理后重跑脚本 |
| `server.py not found` | 仓库克隆不完整，删除 `pal-mcp-server/` 目录后重跑脚本 |
| pip 安装超时 | 网络问题；可为 pip 配置镜像源后重跑 |
| `Neither Claude Code nor Codex CLI was found` | 两个 CLI 都未安装，至少安装其一 |
| Codex MCP 未生效 | 重启 Codex 会话；检查 `~/.codex/config.toml` 中 `[mcp_servers.pal]` 段 |
| Claude MCP 未生效 | 重启会话后执行 `claude mcp list` 验证 |
| 配置被改坏 | 安装脚本每次修改 `config.toml` 前都会备份为 `config.toml.backup.<时间戳>`，可用备份恢复 |

## 重新安装 / 更新

直接重跑安装脚本即可：仓库会 `git pull` 更新，依赖重装，MCP 注册覆盖更新（旧配置自动清理）。


