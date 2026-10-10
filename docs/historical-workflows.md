# 历史版本与兼容入口

本页供维护者核对历史运行。新实验使用[当前CLI流程](native-cli.md#固定选题清单20题与75题)，公开数据范围以[75题清单](public-subset-75.md)为准。

## 79题历史源池

历史源池含65道单阶段题和14道两阶段题。当前公开集移出4道单阶段准备题，保留61道单阶段题和14道两阶段题；移出理由见[范围说明](public-subset-75.md#从79题历史池中移出的4题)。

组织者的历史源树与运行快照保留原始字节，用于核对已有答卷的题面、rubric和执行器指纹。它们不是75题公开发布目录，不能整体上传。发布脚本按当前清单过滤，并记录原始与导出指纹；公开副本不等于历史源树的逐字节复制。

旧全库批次的原题分母为65或79；加入4条连续案例后，79题版本包含83个执行单元、108个阶段。连续案例不增加独立原题数。复核旧成绩须使用其冻结版本，不能直接改分母或把旧批次改标为当前20题、75题实验。

## 旧版登记与打包

- `formal-prepare` / `formal-run`固定历史79题及4条连续案例，详见[历史登记接口](formal-public.md)。旧记录的`official`标记与协议指纹保留，不据此宣称当前实验已完成正式登记。
- `release-package` / `release-verify`保留用于匹配历史版本。`--scope preview`生成内部检查包，不声明公开授权。
- 当前79题工作区上的`--scope public`导出会被75题范围检查拒绝。新发布统一使用`python3 scripts/prepare_publication.py --out dist/<新目录>`。
- `release/public-review.json`与`release/hf-review.json`保存历史内容绑定，不扩大当前75题范围，也不能替代新内容的审核。

## 旧版HF导出

`export-hf`保留`dev.jsonl`、`staged-dev.jsonl`和可选`episodes.json`格式，使用独立的[旧版数据卡模板](legacy-hf-card.md)。题数由导出源的manifest决定，输出数据卡另附实际统计。

当前75题发布使用`single-stage.jsonl`、`staged.jsonl`、`rubrics.jsonl`和[当前HF数据卡](huggingface/README.zh-CN.md)。两套格式分别维护，当前[数据说明](dataset.md)不再充当旧接口的模板。

## 历史选题清单

`config/selections/public-test-50-v1.json`保留选题时的原始记录，其中“公开50题＋私有150题”是已停用的拟议方案，`selected_pending_release`是当时状态。当前范围为公开75题、私有125题；50题仅是公开开发集中的历史评测选择，不是额外test分区。

该文件的原始字节SHA-256被40题清单的`selection_provenance_sha256`引用，因此不覆盖其`purpose`、状态或标识。当前解释见[50题选题说明](public-subset-50.md)。20/40/50题清单、题目内容与历史运行的绑定保持不变；需要改选题时创建新版本。
