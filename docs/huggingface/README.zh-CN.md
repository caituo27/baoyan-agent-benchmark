# 保研 Agent Benchmark

**面向中国保研咨询任务的原生 AI Agent 评测集。**

[English](README.md) · [评分规则](../scoring.md) · [题目清单](../../config/selections/public-dev-75-v1.json)

## 数据集简介

本基准考察 Agent 能否根据学生的学业背景、科研经历、个人偏好和申请限制，给出准确、可行的保研建议。任务覆盖择校推荐、准备规划、资格核验、研究与培养方向选择、Offer 比较，以及补充信息后的方案修订。

被评测对象是**原生 Agent 产品及其模型和执行配置**。复现时需记录客户端版本、请求模型、订阅或 API 认证方式、工具、权限、尝试历史和完整答卷；仅有模型名称不能完整描述实验条件。

公开开发集包含 **75 道题、24 个匿名学生案例组、89 个作答阶段**。题面与评分细则使用中文，说明文档提供英文和中文两个版本。

## 数据结构与数量

| HF 配置 | 划分 | 行数 | 内容 |
| --- | --- | ---: | --- |
| `single-stage`（默认） | `dev` | 61 | 23 道择校推荐题、38 道规划决策题 |
| `staged` | `dev` | 14 | 每题两阶段，第二阶段补充新信息 |
| `rubrics` | `dev` | 75 | 与上述 75 题对应的评分细则 |

**默认的 `single-stage` 配置包含 61 行，切换到 `staged` 可查看另外 14 题。** 75 行 rubric 是同一批题目的标注，不是额外的 75 道题。两个题目配置均属于公开 `dev`。

总题库为 **75 道公开 dev＋125 道私有 test＝200 题**。私有题面与细则不随本包分发。私有题与公开题共享底层学生案例，因此不是独立学生留出集；20 题和 40 题清单是公开 75 题内部的评测子集，不是额外的数据划分。

```text
README.md / README.zh-CN.md       英文主数据卡与中文版
single-stage.jsonl               61 道单阶段题
staged.jsonl                     14 道两阶段题
rubrics.jsonl                    75 份对应评分细则
tasks/<task_id>/task.json        可读的规范题目记录
tasks/<task_id>/rubric.json      可读的规范评分记录
selection-20.json                首批实验清单
selection-40.json                扩展实验清单
selection-75.json                公开发布范围
scoring.md                       权威评分通则
manifest.json / checksums.json   范围、状态和文件校验信息
```

## 快速读取

下载并解压数据包后，在数据目录中运行。以下代码仅需 Python 标准库：

```python
import json
from pathlib import Path

def read_jsonl(name):
    return [json.loads(line) for line in Path(name).read_text(encoding="utf-8").splitlines() if line.strip()]

single = read_jsonl("single-stage.jsonl")
staged = read_jsonl("staged.jsonl")
assert (len(single), len(staged)) == (61, 14)
assert len({row["task_id"] for row in single + staged}) == 75
print(single[0]["task_id"])
print(single[0]["input"])

# 仅供组织者检查；后续阶段必须等到对应轮次才能释放。
stages = json.loads(staged[0]["stages_json"])
print(stages[0]["instruction"])
```

如已安装 Hugging Face `datasets` 库，也可以读取本地文件：

```python
from datasets import load_dataset

single = load_dataset("json", data_files={"dev": "single-stage.jsonl"}, split="dev")
staged = load_dataset("json", data_files={"dev": "staged.jsonl"}, split="dev")
```

## 2026-10-10 更新

本版已同步中山大学、厦门大学、北京理工大学参考项修订，更新N06-03及N14-03的rubric、JSONL和选择清单指纹；75题的候选可见输入保持不变。此前版本可通过Hugging Face提交历史恢复。

9个Agent配置在同一组20道开发集题目上完成评测，共180份答卷，均已完成初评并获得确定分数。以下按20题平均分从高到低排列，评分细节与修订记录见[完整报告](results/subset20-results-nine-final-20261010/README.zh-CN.md)。

| 配置 | 20题均分 |
| --- | ---: |
| GPT-6 Astra | 80.85 |
| GPT-6.1 Sol | 80.42 |
| Claude Code (Opus 5.5) | 73.14 |
| DeepSeek V4.1 Flash | 69.23 |
| GLM 5.3 Flash (Ark) | 68.91 |
| Qwen 3.8 Max | 65.97 |
| Kimi K3 | 62.11 |
| Gemini 3.8 Flash | 60.56 |
| Gemini 3.1 Pro | 56.25 |

[完整报告](results/subset20-results-nine-final-20261010/README.zh-CN.md) · [未证实事实说明](results/subset20-results-nine-final-20261010/pending-review.md) · [证据裁决](errata/deepseek-language-half-20261010/decision.json)

完整逐项评审与执行轨迹未在本数据集公开，当前材料不能独立复算全部成绩。

## 真实题目示例与字段

题目 `BY-A-PLAN` 的原始问题是：

> 现在是2024年10月，我在苏州大学能源学院读大二上，专业是新能源材料与器件（中外合作办学），希望以后争取本校推免资格。我应该从哪些事情开始准备，怎么安排接下来两年的学习和实践？

导出的 `input` 还包含统一答题要求和写入 `answer.md` 的交付指令。正式执行使用完整 `input`；上面的引文仅用于展示题目内容。

| 字段 | 含义与用途 |
| --- | --- |
| `task_id` | 稳定题号，用于关联题目、细则与运行记录 |
| `input` | 单阶段任务的完整候选输入 |
| `stages_json` | JSON 字符串，包含按序排列的 `stage_id`、`visible_at`、`instruction`；仅释放当前阶段 |
| `task_json` | 规范题目 JSON 字符串，含组织者元数据，不能整条交给被测 Agent |
| `track`、`category` | 原始轨道（`dev` 或 `staged-dev`）及任务类别 |
| `case_group_id` | 同一学生案例的分组标识，用于处理题目间相关性 |
| `stage_count` | 1 或 2 个作答阶段 |
| `in_first_experiment` | 是否属于首批 20 题 |
| `task_sha256`、`rubric_sha256` | 规范内容指纹，与文件字节哈希用途不同 |
| `effective_review` | 当前审核状态与确认依据 |
| `rubric_json` | `rubrics` 配置中的评分细则 JSON 字符串，仅供评审 |

`*_json` 字段使用 `json.loads` 解码。除实际题面和当前阶段信息外，其余组织者字段不应默认提供给被测 Agent。

## 如何进行评测

使用与数据版本匹配的配套代码包。其中 `docs/reproduction.md` 说明评测流程，`docs/native-cli.md` 说明支持的原生客户端与执行设置。

1. 冻结题目清单、客户端与模型、认证方式、工具权限、超时及重试规则。
2. 每题启动独立候选会话。单阶段使用 `input`；两阶段通过执行器按序释放信息，同一题内续接会话。
3. 保存完整答卷和执行证据；评分细则、参考候选、其他答卷和未来阶段信息不进入候选环境。
4. 依据对应 rubric 独立评审，由版本化评分代码计算分数，并保留判断依据。

读取 JSONL 并不等于完成评测。整个数据包包含组织者材料，不能整体挂载到候选工作区。

## 评分方法

每题满分 **100 分**，按本题 rubric 评分；两阶段任务在汇总时只计一道。独立评审核验语义、学生适配与证据，程序校验记录并计算分数。

23 道单阶段择校题按项目匹配 70 分、推荐质量 30 分评分。有效的完整或等价项目匹配系数为 100%；同院系相近专业为 60%；同校跨院系且实质相关的方向为 30%。程序采用最高总分的一对一分配，避免重复推荐重复得分。其他题按各自细则计算。

参考清单不是唯一自然语言答案。未附链接或未列入参考清单不自动等于事实错误；匹配得分与内容有效性分别判断。实质证据争议保留待核。应同时报告完成、失败、待核情况，不能把仅已评分题目的均分冒充完整集合成绩。详细规则以[评分通则](../scoring.md)为准。

## 数据构建与审核状态

公开题由匿名咨询案例整理为关联问题和阶段更新，选题清单记录题号与内容指纹。私有题库包含根据现有案例和评测发现编写的补充问题，与公开题库共享案例背景。

维护者于 2026-10-09 确认既有题目的事实核查及全 200 题教师校准完成。`effective_review` 记录当前状态及维护者确认依据；冻结题目中的历史 `review` 字段用于版本追踪，当前状态以 `effective_review` 为准。

当前汇总结果包含在`results/`；原始实验答卷和轨迹仍单独分发。教师校准与 Agent 答卷评审是两个独立环节；具体评审状态和评测范围随各批实验记录提供。

## 适用范围与限制

- 用于保研咨询、检索、约束推理与规划修订能力的评测和开发；分数不表示学生的录取概率。
- 同案例题目相关，统计应考虑案例分组；75 题不等于 75 名独立学生。公开与私有案例重叠限制了对全新案例泛化的结论。
- 20/40 清单是人工精选，不是随机抽样或预注册。更早的上游清单曾考虑运行记录可得性，不应按有利成绩选择题目或尝试。
- 招生事实有时效性，必须保留题内时点和申请周期，不能把执行当天或后续结果当成情景中已知事实。
- 文档中英双语，评测题目保持中文；使用翻译题面会形成不同实验条件。
- 保持匿名，不追查学生身份。外部资料遵循其自身许可。结果依赖 Agent 产品、模型、工具、访问条件和评审流程。

## 许可与引用

数据采用 **CC BY 4.0**，配套代码采用 **MIT**。参见[数据许可](../../LICENSE-DATA)与 [CITATION.cff](CITATION.cff)。引用时请注明实际使用的题目版本和发布清单指纹。

```bibtex
@misc{baoyan_agent_benchmark_2026,
  title = {Baoyan Agent Benchmark: Public Development Set},
  author = {{Baoyan Agent Benchmark contributors}},
  year = {2026},
  version = {1.0.1}
}
```

更正报告应说明题号、版本、证据和建议修改，不附私有学生资料或私有测试题。
