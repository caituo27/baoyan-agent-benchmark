# 运行与评分指南

以下命令在下载或解压后的仓库根目录执行。先跑一道题确认客户端可用，再运行固定20题，最后独立评分并查看报告。

### 1. 准备环境与账号

- Python 3.10+；使用 Kimi 订阅配置时需要 Python 3.11+。框架只使用 Python 标准库，无需 `pip install`。
- 原生 CLI 自动执行目前需要 macOS 的 Seatbelt 沙箱。Linux/Windows 的 App 手工收卷见[复现指南](reproduction.md)。
- 安装并登录要测的官方客户端。下例使用 Codex 的 `gpt-6-1-sol` 配置；也可以按[客户端指南](native-cli.md)配置其他产品。模型访问权限由自己的账号决定。

```sh
python3 -m benchmark setup --agent gpt-6-1-sol
python3 -m benchmark cli-check --agent gpt-6-1-sol
```

`setup` 固定本机客户端路径、版本、模型和认证方式，保存到 `runs/config/agents.local.json`。订阅与 API 是不同参评配置，不自动切换。`cli-check` 返回 `ready_for_trial` 才进入下一步；它检查环境，不证明账号额度、模型权限或端到端调用成功。不要提交本机配置、凭据或登录文件。

### 2. 实际运行一道题

下面会调用模型并使用你的账号额度。去掉 `--execute` 只预览，不调用模型、不创建运行目录。

```sh
python3 -m benchmark cli-batch --suite dev \
  --agent gpt-6-1-sol --task N02-01 \
  --out ./runs/codex-one-task --execute
```

终端与 `status` 可查看是否完成：

```sh
python3 -m benchmark status --batch-dir ./runs/codex-one-task
```

这道题的答卷位于 `runs/codex-one-task/gpt-6-1-sol/N02-01/r1/workspace/answer.md`，同目录保存运行记录。单题试跑用于检查执行，不是20题成绩；下一步使用新目录重新答题。

### 3. 运行固定20题

`--selection` 校验选题清单、题面和 rubric 的指纹，将完整清单写入批次计划，并以所选题目作为报告分母。自动包含清单中的两阶段题，不需要手动列20个 `--task`。

```sh
# 先预览：每个配置、每次重复为20题、24阶段
python3 -m benchmark cli-batch \
  --selection config/selections/public-dev-20-v1.json \
  --agent gpt-6-1-sol --out ./runs/codex-dev20

# 确认预览后实际执行
python3 -m benchmark cli-batch \
  --selection config/selections/public-dev-20-v1.json \
  --agent gpt-6-1-sol --out ./runs/codex-dev20 --execute
```

所有参评配置使用相同选题清单。增加其他配置时，先完成对应 `setup`，再重复 `--agent <配置ID>`；总调用量随配置数和 registry 中的重复次数增加。`--selection` 不能与 `--task`、衍生连续任务参数混用。若要另开75题公开集实验，替换为 `config/selections/public-dev-75-v1.json` 并使用新输出目录；75题与20题报告分开。

被测 Agent 只接收当前题面。两阶段题在同一原生会话中完成 S0 后才释放 S1，不同题使用隔离会话；rubric 留在评审端。

### 4. 查看进度与恢复

```sh
python3 -m benchmark status --batch-dir ./runs/codex-dev20

# 中断后使用原来的参数和目录恢复
python3 -m benchmark cli-batch \
  --selection config/selections/public-dev-20-v1.json \
  --agent gpt-6-1-sol --out ./runs/codex-dev20 --resume --execute
```

`--resume` 继续未尝试任务及成功的阶段边界，保留已完成答卷；失败、超时或结果不确定的阶段不自动重跑。改变题集、模型配置、执行代码或预算时，使用新目录。历史批次要配合当时冻结的运行代码复核。

| 产物 | 位置，相对于 `runs/codex-dev20/` |
| --- | --- |
| 固定选题、执行计划与预期范围 | `full-batch.json` |
| 固定客户端配置 | `agents.frozen.json` |
| 已完成调度步骤的状态快照 | `full-status.json`；实时状态使用上述 `status` 命令 |
| 单阶段原始答卷 | `single/<配置ID>/<题号>/r1/workspace/answer.md` |
| 两阶段记录、各阶段答卷和工具事件 | `staged/<配置ID>/<题号>/r1/` |

### 5. 配置独立评审并评分

被测客户端与评审模型分别配置。先复制模板，在 `config/judge.local.json` 中填写 `provider`、`model`、`expected_response_model`、`endpoint`，并确认 `parameters` 与服务兼容。`expected_response_model` 应匹配服务实际返回的模型标识，不要保留模板占位值。API Key 通过模板指定的 `BENCHMARK_JUDGE_API_KEY` 环境变量提供，不写进配置。

```sh
cp config/judge.example.json config/judge.local.json
# 用编辑器填写 config/judge.local.json；在终端安全设置 BENCHMARK_JUDGE_API_KEY

# 先生成评审请求，不调用评审模型
python3 -m benchmark judge-batch --batch-dir ./runs/codex-dev20 \
  --config config/judge.local.json --out ./runs/codex-dev20-judged

# 执行刚准备的评审：会使用独立 Judge 的 API 额度
python3 -m benchmark judge-batch --batch-dir ./runs/codex-dev20 \
  --config config/judge.local.json --out ./runs/codex-dev20-judged \
  --resume --execute
```

Judge 按逐题 rubric 输出判断，程序校验答卷引句并计算分数。两阶段题合并两轮评一次。当前 API Judge 没有外部浏览能力，证据不足的判断保留待核；生成模板不等于完成评审。人工评审、争议与复核见[评审流程](review-protocol.md)。答题批次停止后再评审；已经开始评审的原始答卷目录不要继续写入。

### 6. 查看与复核报告

评审流程自动生成 `runs/codex-dev20-judged/leaderboard/index.html` 和 `leaderboard.json`。浏览器打开 HTML；JSON 包含逐题状态、得分、完成率及汇总。也可以从已保存的评审重新校验、复算并导出到新目录，不再调用模型：

```sh
python3 -m benchmark leaderboard-export \
  --batch-dir ./runs/codex-dev20-judged \
  --out ./runs/codex-dev20-report
```

打开 `runs/codex-dev20-report/index.html`。**报告分母固定为20题；全部预期重复都有有效评分才显示完整均分。** 缺答、失败、缺评审或待核均单列，不能只平均成功项。报告不完整时，导出仍保留 HTML/JSON，退出码为1；校验错误为2。它是本地实验报告，不自动成为正式榜单。

报告范围以选题清单为准。单题试跑不作为固定20题实验成绩；其他执行入口见[原生CLI指南](native-cli.md)。
