# 历史79题评测登记接口

本页只用于匹配历史运行。新20题或75题实验使用[当前执行流程](native-cli.md#固定选题清单20题与75题)，范围差异见[历史版本说明](historical-workflows.md)。

`formal-prepare` 登记本项目正式公开题集评测：79 道原题（65 道单阶段、14 道两阶段）和 4 条衍生连续任务。每配置每重复共 83 个执行单元、108 个作答阶段。数据目录仍名为 `dev`；此口径不宣称独立私有留出测试、教师校准或不可变的后端模型身份。

`official: true` 表示已登记到项目正式公开评测；`publication_ready: true` 才表示本次导出的所有配置已通过完整结果准入。作答、评分和连续任务评审没有全部完成时，面板保留进度与缺评审状态。原题完整均分要求 79 道原题的所有预期重复都有数值分，连续任务单列，不重复加入原题均分。

## 历史版本的登记方式

先完成原生客户端配置。以下准备命令不调用模型，也不复制密钥：

```sh
python3 -m benchmark formal-prepare \
  --agent deepseek-v4-1-flash --out runs/deepseek-official
python3 -m benchmark formal-run \
  --batch-dir runs/deepseek-official --execute
python3 -m benchmark status --batch-dir runs/deepseek-official
```

`--agent` 可重复；省略时使用 registry 中所有配置。默认 registry 是 `runs/config/agents.local.json`。准备时冻结所选模型、认证方式、客户端版本、重复次数、每阶段时限、题目、rubric、评分与运行代码；保存到批次 `source/` 和 `agents.frozen.json`。执行与评审在独立 Python 进程中使用该源码快照，后续编辑工作仓不改变已冻结批次。快照被修改会拒绝继续。

`formal-run` 不带 `--execute` 只读状态。重复运行相同执行命令只继续尚未尝试的项目，不自动重试中断或失败项。凭据从默认 registry 对应的本地凭据文件和环境变量加载，可通过 `--credentials-registry /absolute/path/agents.local.json` 指定凭据来源；它不会覆盖冻结的模型配方。模型调用仍采用现有原生客户端、沙箱、独立 HOME 和网络限制。

## 显式接收已完成答卷

先停止原批次，用其匹配源码进行校验后接收：

```sh
python3 -m benchmark formal-prepare \
  --agent deepseek-v4-1-flash \
  --source-root /absolute/path/to/matching-release \
  --reuse-batch /absolute/path/to/stopped-full-batch \
  --out runs/deepseek-official
```

必须使用相同题目、评分规则、协议、配置、完整范围和相关运行代码。已完成项原样复制，包含原始答案、日志、哈希和原来的 `official: false` 捕获标签；正式登记记录在外层 `formal-batch.json`，不反写历史。登记清单绑定每个复用文件，并披露这是登记前已产生的答卷，不伪称预注册。

登记前由用户中断的尝试单独保存到 `prior-attempts/`，并在清单和面板中披露；新批次重新准备该题。失败、超时、身份不匹配等尝试不走这条重置路径，不自动挑选最佳重试。原批次始终保留。登记后再次中断的项目不会因 `formal-run` 自动重跑。

## 评分与正式面板

全部作答完成后，配置独立 Judge 及其 API Key 环境变量。此公开流程在首次评审前固定 Judge 配置，不宣称该评审配置已在答题前预注册。评审目录应独立于正式批次：

```sh
python3 -m benchmark judge-batch --batch-dir runs/deepseek-official \
  --config config/judge.local.json --out runs/deepseek-official-review
python3 -m benchmark judge-batch --batch-dir runs/deepseek-official \
  --config config/judge.local.json --out runs/deepseek-official-review --resume --execute
python3 -m benchmark leaderboard-export \
  --batch-dir runs/deepseek-official --out runs/official-leaderboard
```

评审执行后也会自动在评审目录下生成正式面板。手动导出时传入外层正式批次，不能传入内部 `answers/`，后者仍按原始捕获流程显示预览。尚未启动或已停止、尚未评审时可导出面板查看进度；运行期间使用 `status`，导出会要求先结束当前执行以避免读取半写入的记录；返回 `formal_results_pending` 和退出码 1，表示完整结果待准入，页面仍成功生成。

合并面板时重复传入所有正式批次；要求题库、评分标准、预算、重复和 Judge 配置可比，拒绝重复配置或混入预览批次。更新已生成面板加 `--update`。只有完整原题评分、完整连续任务评审以及原始记录与确定性算分校验通过，配置才显示“正式结果”。缺失、失败或待核项不算零分，不以已评分子集冒充完整均分。

导出仅生成本地文件，不自动上传网站。页面不包含凭据、原始答卷或绝对路径。公开题集结果的正式登记不代表第三方认证；事实与语义核实不足仍按原评分规则保留待核。
