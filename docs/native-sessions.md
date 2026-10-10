# 原生会话适配与验收边界

题型调度、信息释放、收卷和评分共用；会话恢复按 CLI 适配。同一 CLI 下的模型共用适配器。模型名、认证方式和预算来自固定 registry，不在失败时切换。

| CLI | 后续轮接口 | 保存的原生状态 |
| --- | --- | --- |
| Codex | `exec resume <SESSION_ID>` | 本次隔离 HOME 下的 sessions JSONL |
| Claude Code | `--resume <SESSION_ID>` | 本次 projects 会话 JSONL；多轮时启用持久化 |
| Gemini CLI | `--resume <SESSION_ID>` | 本次 chats/session JSON/JSONL 和项目目录索引 |
| Qwen Code | `--resume <SESSION_ID>` | 本次 projects 会话与工具结果；显式启用 chat recording |
| Kimi Code | `--session <SESSION_ID>` | 本次会话索引、state、wire 与计划文件 |
| DeepSeek Harness | `--session-id <SESSION_ID>` | 本次 sessions JSONL 或其原生 zstd 编码 |

恢复参数只在通过外层隔离检查后调用，不应从配方中复制到宿主机直接运行。Codex 与 Claude 的单阶段禁用持久化行为保持不变；多轮才启用本次任务内的会话保存。

每轮结束后保存受限的原生会话文件与本次工作区交付文件，不保存认证文件、客户端设置、插件、个人历史、进程锁或后台任务。题面和输出 answer 文件由评测器重新管理，不从上一轮恢复。路径、文件数量、总字节数与内容哈希均受检查，符号链接被拒绝。必要的会话日志缺失时该阶段失败，不能把新会话当成成功续接。

为兼容按 cwd 索引或校验会话的客户端，下一轮只在原临时路径已经不存在时重新创建相同工作目录。绝不接管已存在目录；原路径被占用则失败。每轮重新放入明确选择的认证，结束立即清理沙箱。检查点不含复制的登录状态；原生日志和交付物可能包含题目内容，应作为本地评测材料保存。

当前已实现六种适配器，并用合成可执行程序验证了多轮调用、身份检查、文件续接和清理。2026-10-09 已核实本机已有项目目录内安装的 DeepSeek Harness `0.2.0-rc.2`，其版本、headless `--json` 和 `--session-id` 帮助参数通过实际客户端沙箱探针；其他五种 CLI 此前也通过恢复帮助参数检查。DeepSeek 不在全局 PATH 中，当前项目通过本机 registry 的绝对 `binary` 路径复用安装。帮助探针不等于真实任务或会话恢复已经运行成功。

这些证据不证明真实模型推理、账号权限、原生工具或各版本会话存储均通过验收。正式实验前应对每个固定客户端版本和模型配置执行真实小规模试跑，再冻结实验条件。不能把合成结果作为模型成绩。

接口依据：
- [Codex CLI](https://developers.openai.com/codex/cli/reference/)
- [Claude Code sessions](https://code.claude.com/docs/en/sessions)
- [Gemini session management](https://geminicli.com/docs/cli/tutorials/session-management/)
- [Qwen Code](https://github.com/QwenLM/qwen-code)（本机 0.25.0 的 help、Storage 与会话实现）
- [Kimi sessions](https://github.com/MoonshotAI/kimi-code/blob/main/docs/en/guides/sessions.md)及[数据路径](https://github.com/MoonshotAI/kimi-code/blob/main/docs/en/configuration/data-locations.md)
- [DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness)（发布的 headless 与 session-persistence-jsonl 源码，显式校验 cwd）


## Antigravity 迁移边界

Antigravity 1.3.2 使用 `--conversation <ID>`。会话白名单仅包含 `.gemini/antigravity-cli/conversation_summaries.db` 、`conversations/<UUID>.db` 和 `brain/<UUID>/` 本次会话生成的工具输出/产物，以及同一工作区的产物；不保存令牌、settings、MCP 配置、客户端运行日志或其他历史。恢复时重建原临时路径，重新暂存当前登录凭据，校验返回会话 ID 不变。每份 checkpoint 保存此前累计 usage 与用户轮数；下一轮必须恰好增加一轮，累计用量不能倒退，报告使用两轮累计值之差。

2026-10-09 本机订阅试跑已验证：写入标记，销毁第一轮 HOME，再恢复同一会话读出标记并追加文件。后续已验证 PTY 终端工具在首次调用和恢复会话后均能运行；未完成正式全题集测试，见[迁移状态](native-cli.md#gemini--antigravity-迁移状态2026-10-09)。
