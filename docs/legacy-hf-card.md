---
license: cc-by-4.0
language:
- zh
task_categories:
- text-generation
tags:
- agent
- benchmark
- admissions
configs:
- config_name: default
  data_files:
  - split: dev
    path: dev.jsonl
- config_name: staged
  data_files:
  - split: dev
    path: staged-dev.jsonl
---

# 保研 Agent Benchmark：旧版导出格式

此数据卡用于兼容 `export-hf` 的固定版本导出。`dev.jsonl` 保存单阶段任务，`staged-dev.jsonl` 保存两阶段任务；每行包含题面、元数据和评分资料。实际题数、范围与内容指纹见本目录的 `manifest.json` 及下方导出统计。

评分资料仅供开发与评审，不能整体交给被测Agent。两阶段任务按顺序释放；连续案例复用原题，不增加独立题量。评分方法见[评分通则](scoring.md)。

数据采用CC BY 4.0；第三方材料保留原有权利。当前75题发布使用独立的数据卡和发布入口，本模板不声明当前公开范围。
