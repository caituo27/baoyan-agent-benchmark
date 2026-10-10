# 发布准备：75题公开数据与125题私有测试

当前题库为 **75道公开dev＋125道私有test＝200题**。20/40题是公开集内的评测子集；当前评分报告包含固定20题、9个配置（含Claude Code / Opus 5.5和GLM 5.3 Flash），共180份初评、180份确定分数、无阻塞评分的待核答卷，见[九配置报告](../experiments/subset20-results-nine-final-20261010/README.zh-CN.md)；r2运行包仍为七配置。

| 位置 | 内容 |
|---|---|
| Hugging Face | 75题题面、任务类型、89阶段结构、逐题rubric和评分通则、20/40/75清单与哈希 |
| GitHub | 执行代码、配置示例、协议、说明、75题公开数据副本和逐次实验目录 |
| GitHub Release附件 | 实验对应的脱敏答卷、轨迹、失败尝试、来源与用量；大文件不直接堆入Git历史 |
| 仓库外私有目录 | 125题题面和细则、作者稿、来源记录及后续私有答卷 |

运行记录属于公开交付内容。第一次公开实验是一个包含20道题的子集，其结果与运行记录在GitHub对应发布；详见[数据集与实验记录的公开分工](experiment-publication.md)。带待核项的初评快照可如实公开，不能称为已终审的完整排名。

[75题范围与4题移出理由](public-subset-75.md)。新编私有题沿用既有案例，不能当作独立学生的隐藏测试集。阶段数、衍生链与重复运行不增加原题或独立案例数。

## 按实验发布

[75题执行记录](../experiments/dev75-20261010/README.md)统一收录Astra 43题、Sol 23题、Kimi 75题及DeepSeek 75题的脱敏答卷与轨迹。参与者按[运行与提交说明](community-runs.md)补齐GPT缺题，并把新记录提交到同一目录。这里记录执行状态，新增题目评分尚未完成；原20题评分报告与历史附件保留。

Release 按“实验批次＋发布修订”组织。当前为 **dev20-20261009 / r2**：20题、24阶段、七配置、140份任务记录，包含千问全部20题的答卷、执行轨迹和失败补跑历史。该运行包保留勘误前129份确定分数、11份待核的初评版本。统一应用院系勘误后的[当前九配置报告](../experiments/subset20-results-nine-final-20261010/README.zh-CN.md)为180份确定分数、无阻塞评分的待核节点；原附件不回填分数。六配置r1继续作为历史版本保留。

```text
release/dev20-20261009/r2/
  manifest.json / checksums.json / cohort.json
dist/releases/dev20-20261009/r2/
  dev20-20261009-r2-seven-results-and-records.zip
```

[当前修订清单](../release/dev20-20261009/r2/manifest.json) · [执行记录入口](../experiments/subset20-20261009-r2/README.md) · [历史r1](../release/dev20-20261009/r1/manifest.json)。当前仍是本地附件，尚未上传。Claude与GLM已各完成20题初评，但两者原始记录不在r2包范围；九配置成绩见上方报告。

`release/publication/` 中的全库审核、代码发布来源清单和历史执行进度是共享或历史输入，不是本次实验发布版本。每个修订有独立的范围与校验清单；完整75题审核材料不装入这个20题运行记录包。

## 本地生成

本次r2沿用已有六配置附件，按冻结哈希补入千问完成记录。生成器仅使用Python标准库，不调用模型或上传；目标目录必须不存在。

```sh
python3 scripts/export_review_results.py \
  --review-dir reviews/subset20-preview-20261009-194705 \
  --cohort release/dev20-20261009/r2/cohort.json \
  --execution-progress release/publication/dev20-qwen-execution-complete-20261009.json \
  --out experiments/subset20-results-seven-complete-20261010
python3 scripts/package_dev20_r2.py
```

以上命令需要组织者本地冻结记录及r1附件，已存在的报告或运行包不会被覆盖。公开附件中包含脱敏证据及补充执行配置；不导出凭据和原生会话checkpoint，不宣称已完成异机重放。以下是历史全量发布工具 `prepare_publication.py` 的目录结构；它仍用于原有批次导出，不能替代r2补充记录合并。

```text
huggingface/
  single-stage.jsonl                 61题
  staged.jsonl                       14题
  rubrics.jsonl                      75份细则
  tasks/<id>/{task,rubric}.json
  selection-{20,40,75}.json
  README.md / manifest.json / checksums.json
github/
  benchmark/ config/ docs/ scripts/ schemas/ data/
  README.md / README.zh-CN.md        项目介绍、公开范围、贡献与引用
  release/publication/
    publication-source-manifest.json 原始/导出指纹与移除文件
    checksums.json                   文件校验值（路径相对于 github/ 根目录）
  experiments/subset20-20261009/
    results.jsonl                   6配置×20题；未评分为null
    configurations.json / manifest.json
    records/                        完成及失败尝试的脱敏副本
    sources/                        已过滤4题的历史执行器副本
    evidence/                       去重调用、已知用量和缺口
    reproduce.py                    离线校验和准备，不调用模型
COMPLETE.json
```

导出保留入选题目和rubric字节，记录原始与导出指纹，并重新绑定集合依赖。源码副本的历史兼容边界见[历史版本说明](historical-workflows.md)。

## 数据与复现状态

| 项目 | 当前状态与边界 |
|---|---|
| 既有题事实核查与全200题教师校准 | 负责人已确认完成；`review-status-200.json`保留当前校准结论，不重写冻结题目 |
| 公开75题 | 清单、HF数据卡、评分资料与发布投影已准备；旧审核绑定与当前内容指纹分别保留 |
| 私有125题 | 4道保留题＋121道新编题；结构、哈希和分值已校验，全200题教师校准已由负责人确认完成；新编题与公开案例仍有关联 |
| 首批20题 | 答卷及独立评审分别保存为带时间的快照，见[9配置评审结果](../experiments/subset20-results-nine-final-20261010/README.zh-CN.md)；各配置完成20份初评，共180份；180份确定分数、无阻塞评分的待核项；不将未完成或待核项填零 |
| 轨迹和用量 | 保存脱敏副本、失败与复用来源；未报告用量和账单保持null，自动扫描不代替全文公开审查 |
| 复现 | 离线检查可证明文件和任务准备；异机真实模型复现仍未验证 |

## 实验报告规则

- 比较原生Agent产品及模型、认证和工具配置。参评范围由各实验的配置清单确定。
- 首个完整答卷规则、原重试预算、账号恢复和各批执行器差异按实际披露，不追溯声称统一预注册。
- 原始答卷用于评分；公开脱敏副本保存原始/导出双哈希。失败、配额、超时保留，复用不算新调用。
- 完成全部20题评分和复核后才计算该子集总分；40题另列实验。无分数为null，不把成功题平均分冒充全集成绩。
- 当前评分报告纳入Qwen、Claude Code和GLM，九配置各完成20题初评；r2运行包仍保留七配置范围，分别注明执行、评审与附件覆盖数量；保留原始失败和续作方式，不补造缺失分数。没有费用记录不填0元；两阶段两次CLI启动不等于两道题。
- 按学生案例组分析相关性。新私有题与公开题共享案例，不声称独立holdout；新题尚未参与本轮旧答卷评分。
