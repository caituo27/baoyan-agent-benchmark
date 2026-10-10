# 原生 CLI 配置、发题与统一评审

当前20题实验使用 `cli-batch --selection config/selections/public-dev-20-v1.json`；75题公开集使用 `public-dev-75-v1.json`。完整命令见[中文快速开始](quick-start.md)或[English quick start](quick-start.en.md)。旧版本入口见[历史版本说明](historical-workflows.md)。

原生 CLI 入口提供配置、导出、收卷、评分和统计流程，使用同一份题库及代码指纹。1.0.1 的运行与结果使用匹配版本复核。

## 固定选题清单：20题与75题

```sh
python3 -m benchmark cli-batch \
  --selection config/selections/public-dev-20-v1.json \
  --agent gpt-6-1-sol --out ./runs/codex-dev20 --execute
python3 -m benchmark status --batch-dir ./runs/codex-dev20
```

先用 `setup` 配置客户端；去掉 `--execute` 可预览。该入口校验清单中的集合、任务与rubric指纹、案例数及阶段数，冻结完整清单到 `full-batch.json`。清单中两阶段题自动纳入，报告分母按所选题目固定；20题为24阶段，每阶段不是独立计分题。它不改变题面、rubric或认证方式，不自动获得正式榜单资格。

`--selection` 仅用于 `cli-batch` 的公开dev执行，不能与 `--task`、`--include-episodes` 或 `--episode` 混用。使用75题清单时另开目录；不指定清单的历史命令继续按原有全库范围报告。中断后以相同参数加 `--resume`，已完成答卷不重跑，失败或不确定阶段不自动重试。评分沿用 `judge-batch`，结果复算沿用 `leaderboard-export`，完整命令和输出位置见[使用指南](quick-start.md)。现有跨电脑 `cli-package` 不支持此参数，不要将旧包生成的全库面板当成20题报告。

## 配置与发题

```sh
python3 -m benchmark setup
python3 -m benchmark cli-check
python3 -m benchmark cli-batch --out /absolute/runs/native-preview
python3 -m benchmark cli-package --out /absolute/packets/native-round1
```

首次运行 DeepSeek 的完整命令见 [first-run.md](first-run.md)。

setup 选择 Agent、认证方式（subscription/api）、检查路径和版本、检查模型/认证服务的系统 DNS、提示安装与认证；不安装软件、不调用模型。正式执行与独立作答包目前要求macOS Seatbelt；不支持的平台会停止，不退回普通进程。建议Python 3.11+，Kimi订阅配置读取必须使用3.11+的标准库tomllib。密钥不回显，单独存入本机 `*.credentials.json`，权限0600，环境变量优先。CLI示例版本来自已有配方，模型权限仍待真实验收；DeepSeek示例版本留空，导出前必须补齐。可以用 `--agent` 先选择已准备的配置。

默认读取 `runs/config/agents.local.json`，不存在时读取 `config/agents-cli.example.json`，可用 `--registry` 覆盖。默认 setup 会补齐模板中尚未配置的 Agent 供选择，重复配置只更新选中项，并保留其他已配置项；显式 registry 和冻结题包不自动扩充配方。若修改全局重复次数或时限会影响未选项，须另存新 registry。

已有密钥可用 `setup --agent deepseek-v4-1-flash --import-credentials /绝对路径/.env` 显式导入；键值 JSON 也可用，只选取该 Agent 的变量，不执行 shell、不扫描其他项目。冲突密钥不会被覆盖。setup/check 的 `credentials` 仅报告变量名称、环境/本地凭据文件/官方登录文件等来源；`configured_not_verified` 表示已配置，`account_verification: not_checked` 表示未请求服务验证权益。

DNS 预检使用与运行网关相同的目标检查和宿主 HTTPS 代理配置；通过只表示路由配置可用，不证明 TCP/TLS、账号权益或模型可用。

cli-batch 默认只预览，不启动CLI、不读取凭据、不创建输出目录。默认 dev 读取当前副本的单阶段清单；公开发布版本含61题。配置数与重复次数决定总作答量；当前20题实验使用上节的显式选题清单。`--task` 和 `--agent` 均可重复。私有 test 使用全局 `--private-root` 和 `--suite test`，产物必须在交付仓外。

cli-package 每个Agent生成一个 `candidates/<agent>.zip`。只发送对应 ZIP；组织者目录含评分快照，留在评分电脑。题包传入与本仓 App/CLI 相同的候选消息：题目、阶段背景、交付要求和来源规则；不传评分标准、参考或其他答卷。

## 答题电脑与收卷

在独立、干净的答题电脑解压相应 ZIP：

```sh
python3 run_agent.py setup
python3 run_agent.py check
python3 run_agent.py
python3 run_agent.py --out answers --execute
```

独立作答包setup只配置可执行文件路径和所选认证的本机凭据；认证方式、模型、版本、思考设置和题目已冻结。要更改认证方式须由组织者生成新配方和新题包。单阶段旧题包每题新进程、新会话和临时目录。失败立即停止；`--resume` 只继续未尝试题，失败和已完成答卷均不覆盖、不自动重试。只回传打印的 `answers-*.zip`，不回传 `.local/` 和登录文件。白名单不主动打包凭据文件，原始事件和诊断日志仅供内部复核。

组织者解压回传文件，使用原始发题目录收卷：

```sh
python3 -m benchmark cli-import --package /absolute/packets/native-round1 \
  --results /absolute/returned/agent-a --out /absolute/runs/native-agent-a
python3 -m benchmark review-batch --batch-dir /absolute/runs/native-agent-a \
  --out /absolute/reviews/reviewer-a
```

导入在写入输出前校验配方、代码、题面、评审快照、会话、答卷和事件一致性。输出标准 batch.json、reproduction.json 和 run.json；未尝试题保留为prepared，不把部分收卷视为完整结果。原始答卷保留，导入批次只用于复核，不能恢复执行。

在匿名评审包中填写实际评审者设置及逐项判断，然后执行：

```sh
python3 -m benchmark review-apply --batch-dir /absolute/runs/native-agent-a \
  --reviews /absolute/reviews/reviewer-a --out /absolute/scored/native-agent-a
python3 -m benchmark results-verify --batch-dir /absolute/scored/native-agent-a
python3 -m benchmark statistics --batch-dir /absolute/scored/native-agent-a \
  --out /absolute/reports/native-statistics
```

statistics 的 `--batch-dir` 可重复以合并不同Agent批次。同配置缺题、少重复、失败或评分待核时没有整套均分。多评审从同一份原始答卷分别生成review-batch/review-apply输出，再用calibration-compare比较。方法与裁决流程见 [实验准备指南](study.md)。需要多次重复时，先在新registry中固定次数再导出；不能把重复1的结果事后当成重复3。

## 本机执行与协议

```sh
python3 -m benchmark cli-batch --registry /absolute/config/agents.local.json \
  --agent gpt-6-astra --task BY-A-PLAN --out /absolute/runs/native-trial --execute
```

本机执行同样输出标准批次，接入上述评审与统计。新版运行上下文将完整发布指纹留作溯源，另外固定运行组件、评分组件和所选配方指纹；说明文档、收集页或未选 Agent 的配置变化不再单独使批次失效。旧 `.1` 上下文仍使用原有完整指纹规则。resume 在任何模型请求前核对相关代码、数据、协议、配方、选择范围和已有捕获文件；失败/已完成尝试跳过，running状态或改过的答卷拒绝恢复。正式实验仍应使用独立答题环境。

默认预览协议为config/native-cli.protocol.json，自定义registry中的重复和时限固定到批次上下文。显式 `--protocol` 要求重复和时限与registry相同。正式协议准备可用：

```sh
python3 -m benchmark study-prepare --registry config/agents-cli.example.json \
  --out /absolute/studies/native-v1
```

生成的原生CLI registry和8配置验收模板仍全部待验证。配置草案registry并固定版本、来源模式、数据及配方指纹后，使用cli-package或cli-batch的 `--registry`、`--protocol` 开始试验。验收记录的CLI版本必须与固定registry一致。主评审、稳定性、校准及运行证据齐全后才能study-check/study-freeze。不会自动生成真实验收证据或启用正式结果。

## Gemini → Antigravity 迁移状态（2026-10-09）

Google 已于 2026-06-18 停止 Gemini CLI 的免费个人及 Pro/Ultra 账号服务；官方仍支持付费 API 和 Code Assist Standard/Enterprise，但本仓旧 `subscription` 配方无法区分并验证企业权益，因此在执行前阻断。参见[官方公告](https://developers.googleblog.com/an-important-update-transitioning-gemini-cli-to-antigravity-cli/)。保留旧结果解析和显式 API 运行，不把已停用的个人登录描述为“缺少登录文件”。

新示例用独立 ID `antigravity-gemini-3-8-flash-high`，记录 `cli: antigravity`、`binary: agy`、版本 `1.3.2`、模型 `gemini-3.8-flash-high` 和 `high` effort。本机已核对 `agy --version`、`--help`、`models`，并通过订阅最小请求、文件工具和跨临时 HOME 的会话恢复试跑；模型列表及 `init.model` 不证明不可变模型版本。旧本机 registry 与冻结题包不会被覆盖；默认 setup 会把新 ID 加入可选项，需显式选择它，旧 Gemini 项不会自动改名。

```sh
python3 -m benchmark setup --agent antigravity-gemini-3-8-flash-high
python3 -m benchmark cli-check --agent antigravity-gemini-3-8-flash-high
```

当前边界：

- **订阅执行已接通。** 启动器读取 `BENCH_ANTIGRAVITY_AUTH_FILE` 指定的原生登录文件，或默认 `.gemini/antigravity-cli/antigravity-oauth-token`；文件不存在时仅读取 macOS 钥匙串中 service=`gemini`、account=`antigravity` 的单项。只接受 `consumer` 登录，以 0600 暂存到本次独立 HOME，退出后销毁。候选进程仍不能访问宿主钥匙串；不复制个人配置、历史或插件，不转用 API。
- 显式选择 API 时，单次执行适配写入临时 `modelProvider: gemini`，只传入选定密钥和端点，并使用 Antigravity 自己的参数。API 模型 ID 必须按该认证渠道重新确认，不能假定订阅目录的 ID 可直接用于 Gemini API。该路径尚未真实请求验收。
- [Headless 协议](https://antigravity.google/docs/cli/headless/)使用 `event`、`conversation_id`、嵌套 `result`；成功终态的 `response` 另存为 `final-response.md`，评分正文取工作区交付的 `answer.md`，同时保留原始事件及 usage。`init.model` 仅是请求设置，不当作实际模型版本证明，也不把订阅估算用量当作费用。
- 连续任务使用 `--conversation`，仅保存会话 SQLite 数据库、摘要数据库、该会话 brain 中的工具输出/产物和工作区产物；在相同临时路径重建独立 HOME。校验会话 ID 和逐次增加的用户轮数，按终态累计 usage 的差值记当轮 token，避免重复计数。
- 仅该客户端启用回环监听及 `com.apple.trustd.agent` 证书验证 IPC，出站仍限本次代理；Antigravity 的 13 项边界探针继续验证宿主文件、本地服务和终端隔离（其他客户端保留原有 9 项）。订阅域名见 `native_runtime.PROVIDER_HOSTS`，头像域名仅放行实测需要的 `lh3.googleusercontent.com`。
- **终端 PTY 已接通。** 仅 Antigravity 启用 `allow_pty`；使用 macOS `com.apple.sandbox.pty` 扩展，将设备访问限定为沙箱自己创建的 PTY。该规则来自本机系统 `application.sb`，亦可参考 [Codex Seatbelt 策略](https://github.com/openai/codex/blob/main/codex-rs/sandboxing/src/seatbelt_base_policy.sbpl)。真实 `run_command` 已执行 `pwd`、`ls`、终端检测和文件写入；恢复同一会话后仍能执行命令并追加产物。探针和回归测试验证宿主/其他沙箱的 PTY 不可读写、文件限制继续生效、超时后终端子进程退出。`write_to_file`、`view_file`、`search_web`、`read_url_content` 也已实测成功；桌面 GUI 等其他工具不由这些测试保证。

上述为本机未计分诊断，不是完整题集验收或正式结果；正式比较仍需另行完成题集验收。Gemini 官方 App 的手动收卷流程不受影响。

## 显式订阅与 API

示例中的Codex、Claude Code、Kimi Code和Antigravity选择`"auth": "subscription"`；Qwen与DeepSeek选择`"auth": "api"`。订阅配方不允许同时出现`api_key_env`或`base_url`；API配方必须明确这两项。`setup`可为新配方选择方式；冻结题包不能改变。认证缺失、额度不足或模型不可用时停止，不切换认证、不自动重试。

| CLI | 订阅认证准备 | 每题带入的状态 |
| --- | --- | --- |
| Codex | 官方`codex login`，使用文件登录；可通过`CODEX_HOME`选择账号目录 | 仅ChatGPT类型`auth.json`，禁止API Key混入运行环境 |
| Claude Code | 官方`claude setup-token`；将令牌配置为`CLAUDE_CODE_OAUTH_TOKEN`或在setup中私密保存 | 仅OAuth令牌，不开放宿主Keychain，不转用ANTHROPIC_API_KEY |
| Kimi Code | 官方`kimi login`；可通过`KIMI_CODE_HOME`选择登录目录 | 默认官方OAuth凭据、已有device_id、选定模型的托管配置及订阅检索配置；不复制整个HOME |
| Antigravity | `agy` 交互订阅登录；指定原生令牌文件或 macOS 指定钥匙串项 | 启动器暂存单项凭据到独立 HOME，进程无宿主钥匙串权限；不自动切换 API |
| Gemini CLI（旧配方） | 个人 Google 登录已停用；旧 subscription 配方阻断，企业权益尚无独立验收 | 显式 API 配方仍保留，不修改冻结历史配方 |

Kimi订阅使用官方`api.kimi.com`/`api.kimi.ai`托管服务和默认文件OAuth引用，所选模型必须存在于登录后的模型配置。默认`oauth/kimi-code`引用对应`credentials/kimi-code.json`；当前K3示例使用登录配置中的模型标识`k3`。自定义OAuth服务、旧格式或Keychain-only登录不会被猜测迁移。API模式的Moonshot端点是另一条明确选择的路径，API Key也可能对应订阅产品，因此实际计费以所选服务为准。临时凭据刷新不会写回用户原登录文件；失效时重新进行官方登录。账号权益和实际模型访问仍需用户授权的真实试跑确认。

Qwen Code 0.25.0 的原生 `web_search` 默认通过同一 DashScope API Key 另调 `qwen3.8-flash`（Responses API），即使主模型是 `qwen3.8-max-0902`。为该配方创建受限密钥时，需要同时授权这两个模型；仅授权 Max 会导致搜索请求返回权限拒绝。Flash 属于原生搜索辅助模型，其调用按账号规则计费，不能把整个 Agent 的运行描述成仅调用 Max。版本或原生设置变化后须重新检查，`setup` 的离线凭据检查不验证这项权限。

## 原生工具、隔离与运行证据

本机cli-batch与独立作答包共用`native_runtime.py`，每次创建新的HOME、工作目录和临时目录。沙箱仅允许读取系统工具、选定CLI及必要运行库、本题材料和本次状态；禁止读取组织者目录、其他答卷、个人历史、宿主Keychain和本机服务。评分仍在作答环境之外运行。无需额外的 Python 依赖。

先运行真实边界探针，再启动CLI。Codex在外层沙箱内允许终端和写文件；Claude恢复原生工具集，使用非交互权限模式；Gemini/Qwen/Antigravity 使用各自原生自动执行参数；Kimi保留print模式工具；DeepSeek保留headless配置。只在外层隔离通过后使用这些权限参数，禁止把相关命令拿到宿主机直接执行。CLI可以使用自己的内置工具，但本配方没有附加个人Skills、MCP、插件或跨题记忆。桌面GUI控制和任意宿主软件未因此开放，工具可用性仍须逐家验收。

- 联网题通过每次运行自己的代理访问公网HTTPS（443），拒绝本机、私网地址、直接绕过代理以及HTTP；不兼容代理的工具请求会失败，不静默放开网络。运行网关读取宿主已有的HTTPS代理（环境变量或macOS系统设置，当前支持无需代理认证的HTTP CONNECT），不修改系统网络。公网DNS结果经代理时固定到已检查IP；仅配方中精确列出的模型/认证域名可在Fake-IP DNS（198.18.0.0/15）下交由该代理解析，依赖所配置代理的正确转发及CLI的TLS校验。
- 对联网题的其他网页域名，只有系统DNS全部返回Fake-IP且已配置上述代理时，运行器才通过代理向固定的 `https://1.1.1.1/dns-query` 发起 [Cloudflare DNS-over-HTTPS](https://developers.cloudflare.com/1.1.1.1/encryption/dns-over-https/make-api-requests/dns-json/) A/AAAA 查询，检查问答匹配、CNAME链及所有地址均为公网，再把 CONNECT 固定到已检查IP。只发送域名和DNS记录类型，不发送题目、密钥或网页请求正文；不修改系统DNS。该路径依赖Cloudflare可用性和现有公共CA，验证TLS、不跟随重定向，失败时拒绝连接。IP字面量、本机/私网/混合DNS结果、给定材料题不触发此解析；模型仍不能访问本机服务。运行证据记录解析服务与规则。
- 给定材料题只允许选定模型/认证服务的域名。服务端检索仍可能走同一服务，域名限制不等于已经证明资料来源合规；历史时间点和给定材料规则仍需审阅轨迹。
- Kimi运行允许访问macOS FSEvents服务以启动原生文件监听；文件读取范围仍受沙箱限制，宿主目录监听已用针对性测试验证拒绝。
- Codex 单独允许 `com.apple.system.opendirectoryd.libinfo` 用户信息查询，供 macOS managed preferences 初始化解析当前系统用户。该权限可读取系统账户元信息；不会开放宿主 HOME、偏好文件、钥匙串、评分标准或其他答卷，运行证据记录 `system_user_lookup`。未启用该权限的客户端保持原有规则。
- 环境变量从空白白名单构建，只带所选认证和运行器生成的设置；不继承其他厂商密钥、个人路由或NODE_OPTIONS。TLS保留证书校验，可使用既有公共CA证书配置，不开放宿主钥匙串。
- 正常结束、错误、超时、SIGINT或SIGTERM时清理本次进程组、代理和临时目录；不会终止其他任务。强制SIGKILL/系统崩溃无法保证执行清理，不设置常驻清理程序。

保存的记录包括：

| 文件 | 内容 |
| --- | --- |
| 原生事件JSONL | CLI原始输出，包含它实际报告的工具调用、检索及错误 |
| trace.jsonl | 按原生行号索引的统一事件封装，保留原事件，不能识别的事件不伪造类型 |
| execution.json | 认证方式、CLI版本、请求模型、网络模式、上游代理地址与Fake-IP规则、边界探针、TLS证书摘要及清理状态；不保存凭据值 |
| answer.md / run.json | 最终答案、状态、时间、会话、模型观测和可用usage |
| final-response.md | 客户端最后一条聊天回复，独立留存，不覆盖模型写入的完整答卷 |

答卷采集优先保留候选工作目录中 `answer.md` 的原始字节。单轮任务必须交付非空 UTF-8 正文文件；文件缺失或无效时记为 `invalid_output`，不把“已写入文件”等完成说明当成正文。Codex 的 `--output-last-message` 使用独立临时路径。多阶段咨询允许按原题要求在聊天中交付：存在正文文件时保留文件，否则保存最终回复，并在 `execution.json` 的 `answer_capture` 中记录来源及正文、最终回复的哈希。思考过程、检索结果与工具日志不拼入答案。超时或中断前已写出的文件也会保留，但不会因此标记为成功。

该修复只适用于新运行器生成的批次。旧批次、冻结代码和原始记录不得原地覆盖；旧版标记为完成的记录仍需单独审计，不能据此认定正文完整，也不能通过续跑将其自动修复。

本机`isolation_verified=true`只表示本次本机边界探针通过并完成清理，不表示VM隔离、安全审计、模型能力验收或正式榜单资格。回传包的同类记录保留为提交者证据，导入后`isolation_verified=false`，不会升级成组织者独立核验。`official=false`、`host_configuration_verified=false`保持不变。凭据文件不进入回传包；原生日志可能包含敏感题面和客户端诊断，只供内部复核。

比较单位仍是“原生CLI产品＋指定模型＋记录配方”。记录请求和CLI实际报告的模型；辅助模型也保留，出现不同模型时停止供复核。各家推理预算和工具并不等价，当前只限制执行墙钟时间。缺失token、费用或模型身份保持null/未知，订阅token不能换算成实际账单。题库、rubric和评分流程保持不变；多阶段覆盖由下文的显式参数选择。

实现参考：[Harbor 原生适配器](https://github.com/harbor-framework/harbor/tree/862d472390c08031e3fbf944f0a253f3c2affa21/src/harbor/agents/installed)、[Kimi 官方登录](https://www.kimi.com/code/docs/en/kimi-code-cli/reference/kimi-command.html)。本项目复用自身沙箱实现，无Harbor运行依赖。

## 退出状态

预览、成功配置及完整执行返回0；setup/check未就绪、失败/超时/模型不符、部分执行或收卷返回1；参数/校验错误返回2；运行中断返回130。stdout保留JSON报告，非零退出码不会删除原始证据。

## 全部题型统一运行

当前公开集包含61道单阶段题、14道两阶段题，共75题、89阶段。常规评测使用 `--selection config/selections/public-dev-75-v1.json`。以下完整集合入口供需要额外运行连续案例的实验使用，按所在版本的manifest决定范围；连续案例单列，不增加原题数量。

```sh
# 预览：不调用模型、不读凭据、不创建批次。
python3 -m benchmark cli-batch --suite dev \
  --agent deepseek-v4-1-flash --include-staged --include-episodes \
  --out ./runs/deepseek-full
# 真正执行：使用同样参数，明确添加 --execute。
python3 -m benchmark cli-batch --suite dev \
  --agent deepseek-v4-1-flash --include-staged --include-episodes \
  --out ./runs/deepseek-full --execute
# 查询进度，不启动客户端。
python3 -m benchmark status --batch-dir ./runs/deepseek-full
```

`--agent` 可重复；省略时运行当前 registry 的全部配置。`--task` 可选择单阶段或两阶段原题；`--episode` 可重复选择连续任务，必须同时加 `--include-episodes`。未选题仍在面板的预期范围中显示为未作答，不能据此获得全题库均分。开始模型调用前统一检查全部所选客户端、凭据和多轮恢复参数，任何未就绪配置都不会静默跳过。

单阶段一题一会话；两阶段题在同一原生会话中完成 S0 后再释放 S1；连续任务按其阶段序列执行。不同题之间新建隔离 HOME 和工作目录。同一题恢复其原生会话、工作目录和已生成文件；仅当前题面可见，评分规则及未来阶段始终留在组织者侧。两阶段题不额外添加连续任务的行动记录要求。

Codex、Claude Code、Gemini CLI、Qwen Code、Kimi Code、DeepSeek Harness 共用调度层，并各自实现显式会话恢复。已实现的适配与验证边界见[会话适配说明](native-sessions.md)。模型配置共用对应 CLI 的适配器；本机帮助探针和合成测试不代表真实模型/工具已通过验收。

终端向 stderr 输出当前配置、题目、重复编号、阶段开始/结束、状态与耗时；stdout 保留最终 JSON。`full-batch.json` 固定计划，`full-status.json` 保存已结束调度步骤的快照；`status` 命令读取子任务当前记录。单阶段产物在 `single/`，两阶段在 `staged/`，连续任务在 `episode/`；后两者每阶段有 `events.jsonl`、`stderr.log`、原文 `answer.md` 和续接校验记录。可对正在执行阶段的事件文件使用 `tail -f`；刷新频率由客户端决定。

统一批跑保留失败项并继续其他独立任务，不自动重试。中断后以相同参数加 `--resume --execute`：已完成任务跳过，阶段边界继续；失败或执行结果不确定的阶段不重跑。客户端、代码、题库、预算或选择变化需新建批次。旧批次使用原冻结版本复核，不转换成新范围成绩。

### 显式并行补跑

用户明确授权重试后，可从已停止的正式公开批次建立独立补跑集合。原 `formal-run`、`cli-batch --resume` 的策略保持不变。新集合冻结修复后的代码、原题目和配方，标记 `official: false`；不修改原正式登记，也不把跨运行器版本的补跑结果直接当作原协议正式成绩。

```sh
python3 -m benchmark parallel-prepare \
  --prior-batch ./runs/first-stopped-formal-batch \
  --prior-batch ./runs/second-stopped-formal-batch \
  --out ./runs/recovery
python3 -m benchmark parallel-audit --batch-dir ./runs/recovery --decisions ./capture-audit.json
python3 -m benchmark parallel-run --batch-dir ./runs/recovery \
  --credentials-registry ./runs/config/agents.local.json --execute
python3 -m benchmark parallel-status --batch-dir ./runs/recovery
```

- 每个独立题目由独立工作进程执行，各自使用原有沙箱；两阶段题、连续咨询的全部轮次作为一个调度单元顺序执行。默认每个产品最多 2 个工作进程，Codex 每个模型配置最多 1 个，Astra 和 Sol 合计不超过 2 个。多账号也保守共用该产品上限。
- 原失败/中断尝试加一次补跑合计最多 2 次；原未尝试题首次运行后，仅临时网络、过载或超时可再试一次，默认间隔 30 秒。多轮题重试时从第一轮建立新会话，原多轮尝试完整保留。额度、认证、隔离检查错误或未分类失败暂停该产品的新任务；不轮换账号、切换模型或认证。用户停止后不自动重试被中断的新尝试。
- 原“已完成”记录先进入 `legacy_review`，不会自动视为完整。审计 JSON 为对象数组，每项有 `index`、`action` 和 `reason`：`retain` 还须提供原 `answer_sha256`，保留已确认包含完整正文的旧最终回复；`recover` 仅从完整且成功确认的 Kimi/Qwen 文件写入事件提取正文，并记录轨迹哈希与事件位置；`recapture` 用于已确认的采集缺陷，重新采集并记录原因。正文提取不包含思考和检索日志，不运行轨迹中的命令，不修改原文件。
- 新尝试在 `attempts/<job-index>/a1`、`a2` 中独立保存；恢复正文在 `recovered/`，原答卷保持原路径。`parallel-state.json` 记录选择的答卷、全部尝试与原批次关系；选择首次成功采集，不按评分选优。后续评审须分别披露首次失败、补跑次数、累计用量及旧版最终回复/轨迹恢复的来源差异。
- SIGINT/SIGTERM 或集合目录中的 `stop-request.json` 会停止派发并中断本调度器拥有的工作进程，保留已写正文与日志。正常退出后再次运行同一命令只继续排队任务；遇到未确认退出的进程或被修改的证据则拒绝恢复。它不会重启原冻结代码的批次。
- 调度器本身需要修复时，可显式运行 `parallel-rebase --previous-recovery <已停止集合> --out <新目录>` 冻结新代码。只允许迁移一次，复制并校验全部旧尝试；每题至多排除一次控制器停止造成的中断，或仅有客户端版本事件、尚未推理的授权拒绝。排除记录写入冻结清单，全部费用和失败记录仍须披露，物理尝试最多增加到 `a3`。旧集合及原正式批次保持不变。

## 全部题型统一评审与面板

配置独立 Judge 后：

```sh
python3 -m benchmark judge-batch --batch-dir ./runs/deepseek-full \
  --config config/judge.local.json --out ./runs/judge-full
python3 -m benchmark judge-batch --batch-dir ./runs/deepseek-full \
  --config config/judge.local.json --out ./runs/judge-full --resume --execute
python3 -m benchmark leaderboard-export \
  --batch-dir ./runs/judge-full --out ./runs/full-leaderboard
```

`judge-batch` 默认只冻结评审请求；`--execute` 才调用评审模型，之后自动生成 `runs/judge-full/leaderboard/index.html`。单阶段沿用原流程；两阶段合并两轮回答、按原题 rubric 评一次；连续任务按来源原题评分，另作跨阶段诊断。评早期原题的请求只含截至该题结束的历史和交付文件。失败/中断的评审请求不会因 resume 再次扣费。Judge 仍无外部浏览能力，证据不足保留 pending。

面板分母由批次记录固定：使用 `--selection` 时为清单题量；不使用清单时为所在版本的完整集合，不能将手动 `--task` 子集当成完整集合成绩。连续任务单列，不加入原题均分。全部预期题目和重复都有数值分后才显示完整均分。多个评审目录合并时须保证题库、协议、Judge配置相容且无重复答卷。

此统一入口支持本地公开 dev 批跑及下述完整跨电脑答题包。原 `submission-export/import`、不带完整范围参数的 `cli-package` 和私有 study/test 保留原单阶段契约。

## 完整题库跨电脑答题与统一收卷

使用75题公开发布副本准备题包，由答题者使用自己的Claude Code订阅作答，组织者保留题库版本并统一评审：

```sh
python3 -m benchmark cli-package --suite dev \
  --registry config/agents-cli.example.json --agent claude-opus-5-5 \
  --include-staged --include-episodes --out runs/claude-transfer
```

只发送 `runs/claude-transfer/candidates/claude-opus-5-5.zip`，保留组织者目录直到收卷与评审结束。题包范围由生成时的manifest决定：75题公开副本包含61道单阶段和14道两阶段题；`--include-episodes`额外加入4条连续案例，单独报告。也可用 `--selection <清单.json>` 固定任务范围与报告分母，自动包含清单内两阶段题；不能与 `--task` 或衍生连续任务混用。仅使用旧 `--task` 过滤仍不会缩小完整集合报告分母。GPT社区补跑见[贡献者指南](community-runs.md)。

答题电脑需要 Python 3.11+、macOS 和冻结版本的原生 CLI。解压后按包内 README 执行 `setup`、`check`、预览，再执行 `python3 run_agent.py --out answers --execute`。使用答题者本机账号；无需共享账号、密钥或整个仓库。setup 只允许配置本机可执行路径和凭据，不改变冻结的认证方式、模型、版本或预算。check 不调用模型，也不证明订阅有该模型的权益。

未来阶段题面保存在答题电脑的脚本目录，模型沙箱每轮只得到当前题面；请通过脚本启动，不要让 Agent 直接在整个题包目录作答。同题逐轮恢复原生会话、目录及白名单交付文件，不同题新建会话。用 `--max-stages N` 可在阶段间暂停，再在同一电脑用 `--execute --resume` 继续。失败、超时、中断或结果不确定的阶段不自动重跑；该题后续阶段停止，其他未尝试题继续。未确认结果的 running 记录会拒绝恢复。同题不能在中途换电脑后继续。

结束或正常暂停会生成 `answers-*.zip`；也可用 `python3 run_agent.py export --out answers` 重新打包，费用为零。只回传该 ZIP；它包含所有计划项状态、原始回答字节、事件和隔离记录、会话检查点及任务交付文件，不打包 `.local/`、登录文件或个人 HOME。诊断日志与原生会话仅供内部复核。每文件最多 128 MiB、总计最多 2 GiB，超限明确拒绝，不删减证据。

组织者可直接导入 ZIP，无需手动解压：

```sh
python3 -m benchmark cli-import --package runs/claude-transfer \
  --results /absolute/returned/answers-xxxx.zip --out runs/claude-incoming
python3 -m benchmark judge-batch --batch-dir runs/claude-incoming \
  --config config/judge.example.json --out runs/claude-judged
# 核对并配置 Judge 后，显式执行评审：
python3 -m benchmark judge-batch --batch-dir runs/claude-incoming \
  --config config/judge.example.json --out runs/claude-judged --execute --resume
```

新传输格式为 `native-full-packet.1` / `native-full-return.1`，与旧 answer-only 包分开识别。导入校验原发题包、范围、配方、题面、运行组件、阶段顺序、检查点链、会话独立性、答卷与事件一致性及原始字节指纹；拒绝越界、链接、未知文件、缺项和篡改，全部校验通过后才创建收卷目录。不执行回传文件或在评审电脑恢复其会话。原始提交证据完整保留，导入只供评审，`isolation_verified=false`、`official=false`；内容指纹不能证明提交者身份或远端记录真实性。

统一评审生成 `runs/claude-judged/leaderboard/index.html`，按题包绑定的原题集合与连续任务分别统计。缺题不产生完整均分。合成测试不代表答题者账号或第二台电脑已完成真实模型验收。

## 单条连续任务与人工接口

`episode-run` 对六种已适配 CLI 共用：默认预览，`--execute` 才调用模型，`--max-stages` 限制本次阶段数，`--resume` 只从成功阶段边界续跑。

```sh
python3 -m benchmark episode-run --episode LONG-A \
  --agent deepseek-v4-1-flash --out ./runs/long-a
```

每阶段必须交付非空 UTF-8 `artifacts/action-record.md`；后续轮保留并修订。总执行预算为阶段数乘以配置时限。原生 session ID 改变、必要状态缺失或输出不确定即停止该条任务，不改成拼接历史的新会话。

手动中转仍可用 `python3 -m benchmark.longitudinal prepare/record/next`；完整答卷可用同模块 `review/score` 人工评审。原题等权预览均分不代表已校准的长期能力综合分。
