# 首次使用：执行、手工交卷与成绩复核

**运行当前固定20题实验，请先看[完整使用流程](quick-start.md)**：配置客户端 → 单题试跑 → 读取20题清单批跑 → 恢复 → 独立Judge评分 → 查看20题报告。

在下载或解压后的仓库根目录执行。Python 3.10+ 即可运行本仓工具，无需 pip 安装；Kimi 订阅入口需要 Python 3.11+。真实 CLI 自动执行目前只支持 macOS，Linux/Windows 可使用 App 手工收卷，但不能绕过隔离执行 CLI。

## 1. 配置 DeepSeek 参评项

本仓使用官方 **DeepSeek Harness**：npm 包为 `@deepseek-ai/dsh`，命令为 `dsh`，批跑入口为 `--profile headless`。已有安装时，直接运行下面的 setup，并填入现有 `dsh` 可执行文件的绝对路径；项目目录内安装不一定出现在全局 PATH 中，找不到全局命令不代表未安装。

尚无安装时，先安装 Node.js/npm，再依照 [DeepSeek Harness 官方说明](https://github.com/deepseek-ai/deepseek-harness)安装 CLI。官方目前将 Harness 标为开发预览；版本会改变，因此每次新实验都要固定本机实际版本。示例固定为 `0.2.0-rc.2`，可以在仓库的忽略目录内安装，不改变全局安装：

```sh
npm install --prefix ./runs/tools/deepseek --no-audit --no-fund @deepseek-ai/dsh@0.2.0-rc.2
```

配置已有或刚安装的 CLI：

```sh
python3 -m benchmark setup --agent deepseek-v4-1-flash
```

在 setup 的 CLI 路径提示中输入 `当前仓库绝对路径/runs/tools/deepseek/node_modules/.bin/dsh`。setup 会检查版本并将其固定到 `runs/config/agents.local.json`。输入你自己的 DeepSeek API Key；输入不回显，保存到同目录的 `agents.local.credentials.json`（0600），不写入题包或发布包。已有 `DEEPSEEK_API_KEY` 环境变量也可使用。已有密钥文件可显式导入：`python3 -m benchmark setup --agent deepseek-v4-1-flash --import-credentials /绝对路径/.env`；也支持键值 JSON，只读取所选 Agent 的变量，不执行文件、不自动扫描其他项目。不要把密钥发到聊天、写进模型配方或提交到 Git。

```sh
python3 -m benchmark cli-check --agent deepseek-v4-1-flash
python3 -m benchmark cli-batch --suite dev --task N02-01 \
  --agent deepseek-v4-1-flash --out "$PWD/runs/deepseek-one-task"
```

`cli-check` 应返回 `ready_for_trial`，仅说明本机版本、必需参数、凭据可用性、隔离探针和服务 DNS 检查通过；不验证账号余额、模型权限或完整网络连接。第二条命令只预览公开dev题N02-01，不创建批次、不收费。首次执行保留 `--task N02-01`，避免选择全部单阶段题。

遇到这些状态请先处理，再重新检查：

| 提示 | 下一步 |
| --- | --- |
| CLI executable not found | 安装 CLI，或在 setup 中填入正确的可执行文件绝对路径 |
| No credential configured for this run | 此运行目录尚未配置；用 setup、`--import-credentials` 或同名环境变量提供已有 Key |
| Pin cli_version / CLI version mismatch | 重新运行 setup，明确固定已安装版本；已冻结题包应安装它要求的版本 |
| DNS resolves to a non-public address | 核对系统代理/VPN与预检报告。精确允许的服务域名可经已有 HTTP CONNECT 代理解析 Fake-IP；没有可用代理时仍拒绝。任意检索域名与普通私网无此例外；细则见 native-cli.md。程序不修改系统代理 |
| Required sandbox unavailable | 确认使用受支持的 macOS；其他平台暂用 App 流程 |

## 2. 显式执行并检查答卷

这一步会使用自己的 API 额度：

```sh
python3 -m benchmark cli-batch --suite dev --task N02-01 \
  --agent deepseek-v4-1-flash --out "$PWD/runs/deepseek-one-task" --execute
```

查看终端状态和批次目录中的 `run.json`、`execution.json`、原始事件及 `workspace/answer.md`。失败、超时和实际报告模型不符都要保留；不能删除失败项以改善结果。不要自动改模型或重复扣费。中断后只有尚未尝试的题可以通过相同参数加 `--resume` 继续；运行或评分组件、题目、协议或所选配方改变后请用新批次目录；仅说明文档或未选配置改变不再使新版运行记录失效。

## 3. 交卷、人工评审与复核

本机也可以分目录模拟答题电脑与评审电脑：

```sh
python3 -m benchmark submission-export \
  --batch-dir "$PWD/runs/deepseek-one-task" --out "$PWD/runs/deepseek-answers.zip"
python3 -m benchmark submission-import \
  --package "$PWD/runs/deepseek-answers.zip" --out "$PWD/runs/deepseek-incoming"
python3 -m benchmark review-batch \
  --batch-dir "$PWD/runs/deepseek-incoming" --out "$PWD/runs/deepseek-reviews"
```

请真实评审者按 [review-protocol.md](review-protocol.md) 将每份匿名目录中的 `judgment-template.json` 填写后另存为 `judgment.json`，并填写 `review-settings.json`。这是必要的人工语义判断，生成模板并不等于完成评审。填写后继续：

```sh
python3 -m benchmark review-apply \
  --batch-dir "$PWD/runs/deepseek-incoming" --reviews "$PWD/runs/deepseek-reviews" \
  --out "$PWD/runs/deepseek-scored"
python3 -m benchmark results-export \
  --batch-dir "$PWD/runs/deepseek-scored" --out "$PWD/runs/deepseek-results.zip"
python3 -m benchmark submission-import \
  --package "$PWD/runs/deepseek-results.zip" --out "$PWD/runs/deepseek-recheck"
python3 -m benchmark results-verify --batch-dir "$PWD/runs/deepseek-recheck"
```

目录必须是未使用的新目录。所有入口和文件名均为仓库既有流程，不要求参测者编写模型调用脚本。完整状态说明、独立答题包和多配置实验见 [native-cli.md](native-cli.md) 与 [reproduction.md](reproduction.md)。

完整公开集使用 `cli-batch --selection config/selections/public-dev-75-v1.json`，每配置75题、89阶段；其余Agent、输出目录和显式执行参数相同。统一答卷目录交给 `judge-batch` 评分。上面的 `submission-export/import` 适用于单阶段批次；多阶段题的跨电脑作答见[完整题库跨电脑流程](native-cli.md#完整题库跨电脑答题与统一收卷)。
