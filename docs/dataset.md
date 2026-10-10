# 保研 Agent Benchmark 数据说明

本次发布75道公开dev：61道单阶段（23道完整择校、38道规划决策）和14道两阶段，共89阶段、24个匿名学生案例组。私有test为125题：4道保留题与121道新编题，题面和细则不随公开包分发。总计200题。

公开范围以[75题清单](public-subset-75.md)为准；历史选题与兼容入口见[历史版本说明](historical-workflows.md)。

题面不附姓名、联系方式、原始报告或内部来源。事实核查和全200题教师校准状态见[审核记录](../release/publication/review-status-200.json)；冻结字段用于版本追踪。

## 数据格式

每题目录包含 task.json 和 rubric.json，manifest.json 固定当前内容指纹。单阶段题在 data/dev；两阶段题在 data/staged-dev，使用 task_id、case_group_id 和按序排列的 stages（stage_id、visible_at、instruction）。连续案例在 data/longitudinal/episodes.json，以来源题号、阶段号和指纹关联原题。

| 字段 | 含义 | 被测 Agent 可见 |
| --- | --- | --- |
| prompt | 问题、已披露背景与作答要求 | 是 |
| context | 画像及当前阶段信息 | 是 |
| deliverables、execution | 交付和工具要求 | 是 |
| task_version | 数据版本 | 工作区元数据 |
| id | 匿名题号 | 结构化题的工作区元数据 |
| case_group_id、difficulty、review | 分组、初标难度和审核状态 | 否 |
| rubric、reference_candidates | 评分项与参考清单 | 否 |

用户消息由 `candidate_prompt` 生成。当前单阶段原题使用独立的输入格式版本 `candidate-input.2`，记录在 `execution.prompt_version`；题库与评分版本仍为 1.0.1，评分内容未因此改变。最终输入包含统一指令、一份完整题面及必要的交付要求。题面已包含的背景不再追加；仅保存在 context 中的已知事实（例如评测时间）补入一次。结构化 context 保留在组织者题库中，被测工作区的 task.json 使用自足题面和空 context，query.md 与实际发送消息一致。

无 `execution.prompt_version` 的旧任务继续使用原有组装方式，已有运行快照、答卷和成绩不改写。新格式的输入指纹覆盖格式版本及最终消息全文，不能将新旧输入视为同一实验条件。导出包仍保留任务与消息哈希用于核对。两阶段题按原轮次逐次披露；不得将后续背景并入第一轮。context.persona 为空不代表没有学生背景，不得从未披露档案补入事实。完整原始答卷以 answer.md 交付。

23 道择校题采用项目分层匹配：完整或等价 100%、同院系相近专业 60%、同校跨院系相关方向 30%、无有效项目 0%；程序做最高总分的一对一分配。项目匹配 70 分与质量 30 分分开计分，当前无核准项目级历史结果，基础权重均为 1。

参考清单不是唯一自然语言标准答案。合理替代、条件方案与证据争议按[评分规则](scoring.md)处理。历史冻结字段与当前负责人确认分开记录；实际答卷评分依相应评审证据计算。

N06-03 的中山大学参考项已于2026-10-10形成[负责人确认的独立勘误版本](../release/errata/N06-10-sysu-20261010/README.md)：广州、珠海两个中文系作为同一参考项的备选招生单位，最多命中一次。七个配置已统一复核并生成[修订成绩](../experiments/subset20-results-sysu-corrected-20261010/README.zh-CN.md)，解决5个待核节点；学硕按完整匹配、同系国际中文教育专硕按60%匹配，未明确申请路径的合并候选仍不计分。原始数据、答卷及旧成绩快照保留；此次未更新HF。

2026-10-10进一步按负责人确认口径修正[N06-14及N14-L1-06的招生单位](../release/errata/department-identities-20261010/README.md)：厦大为中国语言文学系050102学硕，北理工为经济学院020200学硕。七配置的两题共14份评审已统一重算，保留此前中山大学勘误；[该次报告](../experiments/subset20-results-departments-corrected-20261010/README.zh-CN.md)有136份确定分数、4份待核答卷和6个待核节点。原始题包、答卷及此前评分快照保留；本次Git仓库更正不自动更新已发布的HF数据。

## 划分与统计

同一学生及其衍生任务保留case_group_id。当前私有扩写沿用公开案例，因此仅是未公开问题，不构成独立学生holdout。统计按案例组聚类，阶段、重复与改写不增加独立案例数。

数量为75道公开dev、125道私有test。难度配额20%／50%／30%为规划目标，全200题教师校准已由负责人确认完成，实际难度分布仍按可核验记录报告；不能据数量到位宣称正式隐藏评测已就绪。

## HuggingFace

面向外部读者的数据卡以[英文版](huggingface/README.md)为主，附[中文版](huggingface/README.zh-CN.md)。导出器将两份文档复制为HF包根目录的 `README.md` 与 `README.zh-CN.md`；题面和评分细则仍保持中文。

使用`python3 scripts/prepare_publication.py --out dist/<新版本目录>`生成75题HF草稿：single-stage.jsonl为61行，staged.jsonl为14行，rubrics.jsonl为75行，另附20/40/75清单和评分通则。三个HF配置均属dev。完整行含组织者评分资料，不是候选输入；逐阶段释放规则不变。

旧版数据格式及导出接口见[历史版本说明](historical-workflows.md#旧版hf导出)。

## 许可

数据采用 CC BY 4.0，代码采用 MIT。引用注明“保研 Agent Benchmark contributors”、版本及修改情况；第三方材料仍遵循其原有权利。版本与引用信息见仓库 CITATION.cff。

同日完成[招生证据补查裁决](../release/errata/pending-evidence-20261010/README.md)，不改题目及评分规则，重算4份相关答卷；[当次七配置报告](../experiments/subset20-results-evidence-corrected-20261010/README.zh-CN.md)为138份确定分数、2份待核答卷、2个待核节点。浸会DAAI六级等效资格与部分校内特殊通道仍待核。

上述参考项修订及最新成绩已同步到[Hugging Face](https://huggingface.co/datasets/yuxin7778/baoyan-agent-benchmark/commit/f39e0261cb038eed32839577c9defd1765e33948)，提交`f39e026`；发布后重新克隆，192个文件逐一与本地发布包核对一致。75题候选输入不变，125道私有题未上传。

资格修正前的[九配置20题报告](../experiments/subset20-results-nine-complete-20261010/README.zh-CN.md)进一步纳入Claude Code（Opus 5.5）和GLM 5.3 Flash的40份初评，统一应用上述勘误；共180份评审、177份确定分数和3份待核。上方HF提交为此前七配置版本，不代表九配置结果已上传。

随后按负责人纠正，南理工“专项普遍放宽至前30%～50%”不再待核，而按已确认适用范围错误处理；T1半分12.5/25，Gemini 3.8 Flash该题64.5、Dev20均分60.56。九配置[当次报告](../experiments/subset20-results-nine-qualification-20261010/README.zh-CN.md)为178份确定分数、2份待核；[限定范围裁决](../release/errata/njust-qualification-20261010/README.md)保留原判断和更正依据。

Claude的科研院所层次项已按负责人批准的[国科大裁决](../release/errata/ucas-tier-20261010/README.md)解除待核，20题均分73.14。[当次九配置报告](../experiments/subset20-results-nine-ucas-20261010/README.zh-CN.md)为179份确定分数、1份待核，已同步到[Hugging Face提交2426cdd](https://huggingface.co/datasets/yuxin7778/baoyan-agent-benchmark/commit/2426cdd67c9716d954fe1aca819f98d48df8c5fe)。发布后重新克隆，245个文件与本地发布包逐字节一致；题面、rubric与候选输入保持原公开版本，私有题未上传。

DeepSeek语言项已按负责人最终批准的[5/10分裁决](../release/errata/deepseek-language-half-20261010/README.md)确定为半分，整题77.5分、20题均分69.23。[当前九配置报告](../experiments/subset20-results-nine-final-20261010/README.zh-CN.md)的180份答卷均有确定分数；DAAI六级资格仍单独记为未证实，不改变裁决分数。中英文首页移除全部为零的待核列，已同步到[Hugging Face提交aabdfa5](https://huggingface.co/datasets/yuxin7778/baoyan-agent-benchmark/commit/aabdfa5f7d8b33c986d3720672491d56c5b57263)，重新克隆核对262个发布文件逐字节一致。其余179份成绩及75题数据保持不变。

随后按负责人要求将中英文首页按完整20题均分降序排列，分类表与图表保持相同顺序；HF对应[排序提交b3d868e](https://huggingface.co/datasets/yuxin7778/baoyan-agent-benchmark/commit/b3d868e937e5232c6f35ea17326954aaa83dbdc9)。262个发布文件再次逐字节校验一致，分数与历史报告未改写。
