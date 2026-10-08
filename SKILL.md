---
name: "pal-subagent"
description: "通过 PAL MCP 的 clink 工具，将简单、明确的任务委派给子 agent（Codex CLI 或 Claude Code）执行，节省主上下文 token。当用户要求使用子代理、委派任务，或安装/卸载 PAL 子代理环境时调用。"
---

# PAL Subagent — 子 agent 委派执行

通过 PAL MCP Server 的 `clink` 工具，将 **Codex CLI 或 Claude Code** 作为隔离子 agent 执行简单任务，形成"规划-执行"分离架构：主 agent 负责规划与决策，subagent 负责执行明确、重复、逻辑简单的子任务，从而降低主上下文的 token 消耗。

## 架构

```
主 agent（当前会话）
    │  调用 PAL MCP 的 clink 工具
    ▼
PAL MCP Server
    │  codex exec / claude -p（隔离进程、独立上下文）
    ▼
Codex CLI / Claude Code 子 agent
    │  自主执行：文件读写 / 跑脚本 / 验证结果
    ▼
仅回传最终结果（不污染主上下文）
```

## 何时委派给 subagent

**适合委派**（结果明确、无需中间决策，委派可显著节省 token）：

| 能力类别 | 具体任务示例 |
|---------|------------|
| 文件操作 | 读取/写入/追加/删除文件、目录遍历与检查、批量重命名 |
| 代码执行 | 运行 Python/Shell 脚本、构建、跑测试，捕获 stdout/stderr 和退出码 |
| 结果验证 | 执行测试用例、比对预期输出、校验代码正确性 |
| 环境处理 | 检测并安装缺失依赖、处理路径问题、失败自动重试 |
| 信息汇总 | 遍历大量文件提取信息、汇总日志，仅回传结论 |

**不要委派**（主 agent 自己处理）：

- 复杂任务的规划、拆解与方案设计
- 多方案权衡、需要用户确认的决策
- 需要与用户交互（提问、澄清）的任务
- 涉及密钥、生产环境等高风险操作

## 委派规范

### 1. 结构化任务下发

主 agent 下发任务时，prompt 中必须包含：

- **目标**：要完成什么，一句话说清
- **输入**：涉及的文件绝对路径 / 要执行的命令
- **预期结果**：成功的判定标准（如"测试全部通过"、"生成 xxx 文件"）
- **约束**：不允许改动的范围（如"只允许修改 src/ 目录"）

### 2. 自主执行

subagent 收到任务后独立完成，主 agent 不介入中间过程。执行中遇到环境问题（缺依赖、路径错误）由 subagent 自行检测、修复并重试，不向主 agent 请求中间决策。

### 3. 结构化结果回传

要求 subagent 在最终回答中返回：

- 状态：成功 / 失败
- 执行输出摘要（关键日志、退出码）
- 变更文件清单
- 失败时的错误信息与修复建议

### 4. 异常上报

subagent 无法自主解决时（如权限不足、依赖冲突、判定标准本身有歧义），主 agent 根据其回传的上下文决定：补充信息重新委派 / 主 agent 亲自执行 / 上报用户。

## 调用方式（clink）

环境就绪后，调用 PAL MCP 暴露的 `clink` 工具。关键参数：

| 参数 | 说明 |
|------|------|
| `prompt` | 结构化任务描述（必填） |
| `cli_name` | `codex` 或 `claude`（选择子 agent 使用的 CLI，按任务与已安装的 CLI 选择） |
| `role` | `default`（通用任务）/ `planner` / `codereviewer` |
| `files` | 相关文件路径列表（只传路径，由 subagent 自己读取，节省 token） |
| `continuation_id` | 需要多轮补充上下文时延续同一子会话 |

调用示例（委派一个测试执行任务）：

```
clink(
  cli_name = "codex",
  role = "default",
  files = ["/abs/path/to/project"],
  prompt = """
目标：运行项目测试并修复失败项
输入：项目位于 /abs/path/to/project，测试命令为 pytest tests/ -x
预期结果：全部测试通过
约束：只允许修改 tests/ 与 src/ 下的文件；不要改动配置
完成后返回：状态、失败项摘要、修改的文件清单
"""
)
```

注意：`clink` 会以放宽权限模式启动子 agent（自动应用编辑、执行命令），请仅在可信的工作区内委派任务。

## 安装、更新与卸载

安装会将本 skill 分别安装到 Claude 与 Codex 的用户级 skills 目录；两端只共用一份 PAL 服务源码、一份 `.env` 和同一个 conda 环境。首次安装默认将 `pal-mcp-server/` 放在发起端**安装后的 skill 目录**下，发现已有服务时优先复用。两个 stdio MCP 客户端可分别启动进程，共享的是源码与环境。

- Claude：`/pal-subagent <任务>`；Codex：`$pal-subagent <任务>`。
- 用户请求安装、更新、修复或卸载时，读取 [安装指南](references/install-guide.md) 或 [卸载指南](references/uninstall-guide.md)。当前会话没有 `clink` 不等于尚未安装：先检查共享记录与 MCP 配置，已安装时提示重新加载/重启会话。
- 安装前运行 `--dry-run`，向用户说明两端 skill 路径、唯一服务路径、复用或创建的 conda 环境及 MCP 配置变更。用户未确定路径时允许选择其他目录；已经授权的方案无需重复确认。
- 已取得用户对具体安装方案的授权后，可以带 `--yes` 非交互执行。不要因为脚本支持 `--yes` 就跳过沟通。发起客户端通过 `--client claude` 或 `--client codex` 明确传入，不从 CLI 是否存在猜测。
- 安装默认复用源码和满足要求的依赖。只有用户要求更新时才使用 `--update`；两端路径冲突时展示路径，请用户明确选择 `--server-dir`，不要自动选一份覆盖。
- 共享记录位于 `~/.config/pal-subagent/install.json`；修改/卸载从此记录及当前 MCP 配置解析路径，不把当前 skill 目录当作服务目录。
- 卸载某一端时保留另一端和共享服务。删除共享服务必须明确授权，并确认两端引用均已移除。conda 环境始终保留，删除环境是另一个需要用户明确要求的操作。

```bash
# 先预览安装方案，发起端按当前客户端选择
bash <本skill目录>/scripts/pal-subagent-install.sh --client claude --env-name pal-mcp-server --dry-run
# 用户已同意上述具体方案后执行
bash <本skill目录>/scripts/pal-subagent-install.sh --client claude --env-name pal-mcp-server --yes
```
