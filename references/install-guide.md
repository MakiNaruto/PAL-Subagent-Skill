# PAL Subagent 安装指南

## 安装布局

安装器先把 skill 文件装入 Claude 与 Codex 的用户级 skills 目录，再准备唯一一份 PAL 服务并注册 MCP。轻量 skill 副本只含 `SKILL.md`、脚本、参考文档及可选的 agents/assets；不复制服务仓库、`.env`、日志、测试或 `.git`。

首次从 Claude 安装：

```text
~/.claude/skills/pal-subagent/
  SKILL.md、scripts/、references/
  pal-mcp-server/                   ← 唯一服务
<Codex skills目录>/pal-subagent/
  SKILL.md、scripts/、references/    ← 轻量副本
~/.config/pal-subagent/install.json ← 共享记录，无密钥
```

从 Codex 发起时，服务默认放在 Codex 安装后的 skill 目录下。已有安装优先复用共享记录、两端用户级 MCP 配置或来源目录内的服务；不会因换客户端而下载第二份。源码目录与服务目录可以不同。共用源码和 conda 环境，不要求两个 stdio 客户端共用单一进程。

## 前置要求

- conda；安装器的引导 Python 需要 3.11+，通常直接使用 conda base 的 Python。PAL 环境独立复用/创建，不需要激活。
- git（首次下载/明确更新时）、网络（需要下载源码或依赖时）。
- 至少安装 Codex CLI 或 Claude Code，并为实际执行子任务的 CLI 完成登录。

Claude skill 路径：`~/.claude/skills/pal-subagent`。Codex 默认复用共享记录中的路径，其次使用已有 `$CODEX_HOME/skills`（未设置时为 `~/.codex/skills`）；新安装使用 `~/.agents/skills`，也可通过 `--codex-skills-dir` 指定。客户端版本支持应以实际 skill 发现结果为准，不在多个 Codex 搜索目录重复安装。

## 沟通与执行

先确定发起端，用只读预览展示两端路径、服务路径和环境名。向用户解释：已有环境复用，缺失环境会创建 Python 3.12；已有服务复用，`.env` 保留；将修改两端 MCP 配置。没有明确授权时等待用户选择/确认。

```bash
bash <skill目录>/scripts/pal-subagent-install.sh --client claude --env-name pal-mcp-server --dry-run
```

用户已经授权具体方案后，agent 可非交互执行：

```bash
bash <skill目录>/scripts/pal-subagent-install.sh --client claude --env-name pal-mcp-server --yes
```

终端直接运行时先显示方案并询问 `Apply this plan? [y/N]`。非交互且没有 `--yes` 时停止，避免未沟通就写入。`--yes` 表示先前已经获得授权，不替代沟通。

### 参数

| 参数 | 含义 |
|---|---|
| `--client claude/codex` | 发起端，决定首次默认服务位置；共享记录已有发起端时可省略 |
| `--env-name NAME` | 复用/创建的环境；省略时使用共享记录或 `pal-mcp-server` |
| `--server-dir PATH` | 明确选择唯一服务目录，也用于解决两端配置冲突；不会迁移/删除原目录 |
| `--codex-skills-dir PATH` | Codex skills 的父目录（安装器会追加 `pal-subagent`） |
| `--dry-run` | 只读展示方案，不复制文件、下载或写配置 |
| `--yes` | 在先前授权后应用方案 |
| `--update` | 明确更新服务源码（`git pull --ff-only`）并安装依赖；有已跟踪的本地改动时停止 |

指定新服务目录会在该目录准备一份服务并统一 MCP 指向，旧目录保留。若只是复用既有安装，应指定已有目录，不把该参数当作移动命令。想要迁移应另外提出明确迁移请求。

## 安装步骤与重复执行

1. 检查现有记录和用户级配置；发现不同服务路径时停止，要求明确 `--server-dir`。现有记录指向缺失目录时停止，避免悄悄创建第二份。
2. 安装两端轻量 skill；已有文件内容不同时先备份，服务目录及用户文件保留。
3. 准备唯一服务；已有源码默认不更新，`.env` 已有时不覆盖。
4. 复用 conda 环境；只有环境不存在时创建。依赖已经满足要求时跳过网络安装，否则合并安装 `mcp>=1.28,<2` 和仓库 requirements，再执行 `pip check`。
5. 写入共享记录，备份并注册两端 MCP。两端使用同一个 Python 和绝对 `server.py` 路径；PAL 的 PATH 包含当前 CLI 所在目录，Codex `tool_timeout_sec=1200`。
6. 用实际环境启动 MCP、完成握手并验证 `clink`，共享记录标记 `verified=true`。注册/验证失败则返回非零并保留记录，修复后可重跑。

未安装某端 CLI 时也安装其 skill 文件，跳过对应 MCP 注册并提示。后续安装该 CLI 后重跑安装器即可。配置是用户级的；项目内同名 PAL 配置可能覆盖它，需要在目标项目额外检查。

## 验证与调用

重启/重新加载客户端，使 skill 与 MCP 配置生效：

```text
Claude: /pal-subagent 检查当前项目测试结果
Codex:  $pal-subagent 检查当前项目测试结果
```

命令行查看配置：`codex mcp get pal`、`claude mcp get pal`。实际 MCP 握手验证：

```bash
<共享记录中的Python> <skill目录>/scripts/pal_subagent_setup.py probe --server-dir <共享服务目录>
```

仅使用 `clink` 时认证来自 Codex/Claude CLI，不需要为 PAL 另设 provider 密钥。默认 `.env` 中的 Ollama 端点是占位配置；使用其他模型工具时须配置真实可用的 provider。

## 故障排查与回退

- 引导 Python 缺少 `tomllib`：用 Python 3.11+ 直接执行 `pal_subagent_setup.py install ...`；无需重建 PAL 环境。
- 路径冲突：先展示现有路径，选择要复用的一份，再传 `--server-dir`。
- 失败后检查共享记录的 `registered_clients`/`verified` 和错误输出，再重跑；不自动改换环境或服务路径。
- 配置及被覆盖的 skill 文件会生成 `.backup.<时间戳>`。需要回退时选择相应备份，不删除共享服务或已有 conda 环境。

开发验证：Python 3.11+ 执行 `python -m unittest discover -s tests -v`；测试只操作临时目录，不触及真实配置。
