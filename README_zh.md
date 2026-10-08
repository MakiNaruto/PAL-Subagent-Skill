# PAL Subagent Skill

[English](README.md) | 简体中文

基于 [PAL MCP Server](https://github.com/BeehiveInnovations/pal-mcp-server)，通过 `clink` 将明确任务交给已登录的 Codex CLI 或 Claude Code 执行。

安装器会把 `pal-subagent` skill 安装到 **Claude 和 Codex 两端的 skills 目录**，共用一份 PAL 源码、`.env` 和 conda 环境。首次安装默认把服务放在发起端安装后的 skill 目录下，已有服务优先复用。

## 安装

先明确发起端和环境，预览完整方案并与用户沟通：

```bash
bash scripts/pal-subagent-install.sh --client claude --env-name pal-mcp-server --dry-run
```

确认方案后执行（终端交互可省略 `--yes`）：

```bash
bash scripts/pal-subagent-install.sh --client claude --env-name pal-mcp-server --yes
```

从 Codex 发起时使用 `--client codex`。已有 `pal-mcp-server` 环境直接复用，缺失时创建 Python 3.12。引导安装器需要 Python 3.11+，通常使用 conda base。至少已安装 Codex CLI 或 Claude Code；缺失的一端只安装 skill 文件，后续安装 CLI 后重跑即可注册 MCP。

- Claude skill：`~/.claude/skills/pal-subagent`。
- Codex skill：优先沿用记录和已有 `$CODEX_HOME/skills`（默认 `~/.codex/skills`）；新安装用 `~/.agents/skills`。可通过 `--codex-skills-dir` 指定。
- 共享记录：`~/.config/pal-subagent/install.json`，记录路径和环境，不存密钥。
- 自定义/选择已有服务：`--server-dir /绝对路径/pal-mcp-server`。
- 默认不自动更新 PAL；用户明确要求更新时添加 `--update`。

重复安装只同步轻量 skill 文件、复用服务与满足要求的依赖。源码路径冲突时停止并提示选择。已有 `.env` 保留，变更配置及 skill 文件前备份。安装器实际启动 MCP，验证握手及 `clink` 工具。

## 调用

安装完成后重启/重新加载客户端：

```text
Claude: /pal-subagent 运行当前项目测试并汇总失败项
Codex:  $pal-subagent 运行当前项目测试并汇总失败项
```

CLI 子任务需要相应客户端的登录态。仅使用 `clink` 不需要额外 provider API key。默认本地模型端点是占位配置，其他 PAL 模型工具需要可用的 provider。

## 卸载

```bash
bash scripts/pal-subagent-uninstall.sh --client claude --dry-run
# 明确授权后：只卸载 Claude，保留 Codex、共享服务与 conda 环境
bash scripts/pal-subagent-uninstall.sh --client claude --yes
```

卸载两端使用 `--client both`；明确删除共享服务再添加 `--remove-server`，仍有另一端引用时拒绝删除。conda 环境始终保留。

[安装、更新、迁移注意事项与故障排查](references/install-guide.md) · [卸载详细说明](references/uninstall-guide.md)

开发验证（Python 3.11+）：`python -m unittest discover -s tests -v`。
