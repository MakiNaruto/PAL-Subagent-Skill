# PAL Subagent 卸载指南

本文档是 `scripts/pal-subagent-uninstall.sh` 的详细说明，仅在需要了解卸载影响或手动清理时阅读。

## 卸载项说明

脚本在终端中**逐项交互确认**（默认回答 `no`，直接回车即跳过），共 4 项：

| 项 | 操作 | 影响 |
|----|------|------|
| 1. Claude MCP | `claude mcp remove pal -s user` | Claude Code 中不再加载 pal MCP，`clink` 等工具消失 |
| 2. Codex 配置 | 备份后删除 `~/.codex/config.toml` 中的 `[mcp_servers.pal]` 段 | Codex 中不再加载 pal MCP；配置其他段不受影响 |
| 3. conda 环境 | `conda env remove -n <env> -y` | **不可恢复**。仅删除 pal 专用环境，不影响其他项目 |
| 4. 克隆仓库 | 删除 skill 目录下的 `pal-mcp-server/` | 释放磁盘；重装时重新克隆 |

## 运行方式

```bash
bash <skill目录>/scripts/pal-subagent-uninstall.sh
```

**必须在终端中交互运行**（需要 TTY）。脚本非交互运行时会直接退出并提示，不会误删任何内容。

### 参数

| 参数 | 说明 |
|------|------|
| `--env-name NAME` | 指定要考虑移除的 conda 环境名（安装时用了自定义环境名时使用），运行中仍可修改 |
| `-h`, `--help` | 显示帮助 |

环境名在第 3 步会再次提示确认，回车沿用默认/参数值。若不确定环境名，先查看：

```bash
conda env list
```

## 手动卸载（不走脚本）

```bash
# 1. Claude MCP
claude mcp remove pal -s user

# 2. Codex：编辑 ~/.codex/config.toml，删除 [mcp_servers.pal] 到下一个 [section] 之间的内容
#    （建议先备份：cp ~/.codex/config.toml ~/.codex/config.toml.bak）

# 3. conda 环境
conda env remove -n pal-mcp-server -y

# 4. 克隆的仓库
rm -rf <skill目录>/pal-mcp-server
```

## 注意事项

- **备份保留**：Codex 配置的备份文件（`config.toml.backup.<时间戳>`）不会被删除，确认卸载无误后可自行清理 `~/.codex/` 下的备份
- **卸载顺序无强制要求**：各项独立，可只卸载其中一项（例如只移除 Claude MCP、保留 Codex）
- **环境名自定义**：安装时若使用了非默认环境名，卸载时需传 `--env-name` 或在提示时输入正确名称，否则会提示"环境不存在"而跳过
- **仓库删除不影响配置文件**：`[mcp_servers.pal]` 段和 Claude 注册指向仓库内的 `server.py`；只删仓库不卸注册会导致 MCP 启动失败，建议一并清理或重装
- **重装**：卸载后随时可通过 `pal-subagent-install.sh` 重新安装
