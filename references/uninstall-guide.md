# PAL Subagent 卸载指南

卸载读取 `~/.config/pal-subagent/install.json`，先核对当前用户级 MCP 配置与共享服务路径，再只移除所选客户端的托管 skill 文件和 PAL 注册。skill 文件及配置先备份。conda 环境始终保留。

## 只卸载一端

```bash
bash <skill目录>/scripts/pal-subagent-uninstall.sh --client claude --dry-run
# 确认具体方案后执行；终端交互运行可以省略 --yes
bash <skill目录>/scripts/pal-subagent-uninstall.sh --client claude --yes
```

可选 `--client claude/codex/both`；未指定时终端询问，非交互时停止。两端调用方式会随对应 skill 的移除而消失，另一端不受影响。即使共享服务位于被卸载端的 skill 目录内，也保留该服务目录。

## 删除共享服务

只有用户明确要求时，加入 `--remove-server`：

```bash
bash <skill目录>/scripts/pal-subagent-uninstall.sh --client both --remove-server --dry-run
bash <skill目录>/scripts/pal-subagent-uninstall.sh --client both --remove-server --yes
```

执行前检查两端是否仍引用服务：未选中的客户端有 PAL 注册或已安装 skill 时拒绝删除；配置指向了其他服务时也停止。自动删除仅接受包含 `server.py`、`requirements.txt` 且名称为 `pal-mcp-server` 的已记录目录。自定义其他目录名时先卸载两端，再由用户另行明确清理该目录。

skill 备份保存在共享记录同目录的 `backups/` 下；配置备份位于原配置文件旁。skill 中的服务、用户创建的其他文件与备份保留，不直接递归删除整个 skill 根目录。

删除共享服务后移除活动安装记录；历史备份仍保留。`pal-mcp-server` conda 环境保留，用户明确要求删除环境时再单独执行 conda 环境移除操作。

## 旧安装

没有共享记录时先运行新安装器，复用旧服务和环境、补齐 skill 并生成记录，再使用新卸载器。不要根据当前脚本所在目录猜测服务位置。

重启客户端后 MCP 配置变更生效。项目内同名 PAL 注册不属于此次用户级卸载的管理范围，应在对应项目单独检查。
