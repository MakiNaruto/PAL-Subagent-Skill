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

## 安装 / 卸载

环境未就绪（当前可用工具中无 PAL MCP 工具，如 `clink`）时，参见 [README_zh.md](README_zh.md)：先确认项目来源与定位，再按"使用说明"通过一键脚本安装，或按 Claude Code / Codex / Trae 各自的 MCP 添加方法手动注册，重启会话后即可使用。

安装 / 卸载脚本位于本 skill 目录的 `scripts/` 下（即本 SKILL.md 所在目录）：

```bash
# 安装
bash <本skill目录>/scripts/pal-subagent-install.sh --env-name <环境名>

# 卸载
bash <本skill目录>/scripts/pal-subagent-uninstall.sh
```

详细步骤、参数与故障排查：[references/install-guide.md](references/install-guide.md)；卸载详细说明：[references/uninstall-guide.md](references/uninstall-guide.md)
