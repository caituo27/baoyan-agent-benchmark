---
language:
- zh
license: cc-by-4.0
pretty_name: Baoyan Agent Benchmark — Public Development Set
size_categories:
- n<1K
task_categories:
- text-generation
tags:
- agent-evaluation
- chinese
- education
- admissions
configs:
- config_name: single-stage
  default: true
  data_files:
  - split: dev
    path: single-stage.jsonl
- config_name: staged
  data_files:
  - split: dev
    path: staged.jsonl
- config_name: rubrics
  data_files:
  - split: dev
    path: rubrics.jsonl
---

# Baoyan Agent Benchmark

**Evaluating native AI agents on Chinese postgraduate recommendation and admissions advising.**

[中文说明](README.zh-CN.md) · [Scoring rules](../scoring.md) · [Task selection](../../config/selections/public-dev-75-v1.json)

## Update — 2026-10-10

This release applies the SYSU, XMU and BIT reference corrections to N06-03 and N14-03, including canonical rubrics, JSONL rows and selection fingerprints. Candidate-visible inputs for all 75 tasks are unchanged. Previous versions remain available in the Hugging Face commit history.

Nine agent configurations completed the same 20 development-set tasks. All 180 answers have been initially reviewed and assigned numeric scores. Results are sorted by the 20-task mean, highest first; see the [full report](results/subset20-results-nine-final-20261010/README.md) for scoring details and revision history.

| Configuration | Dev20 mean |
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

[Full report](results/subset20-results-nine-final-20261010/README.md) · [Unverified facts](results/subset20-results-nine-final-20261010/pending-review.md) · [Evidence adjudication](errata/deepseek-language-half-20261010/decision.json)

Complete item-level judgments and execution traces are not public in this dataset, so its contents alone cannot independently reproduce every score.

## Dataset Summary

Baoyan Agent Benchmark evaluates whether an AI agent can turn a student's academic background, research experience, preferences, and application constraints into accurate, feasible advice. *Baoyan* (保研) refers to recommendation-based admission to postgraduate programs in China, without the national postgraduate entrance examination.

Tasks cover program recommendations, preparation plans, eligibility checks, research and degree choices, offer comparisons, and revisions after new information arrives. They require more than fluent writing: the agent must preserve the student's stated facts, distinguish application requirements from preferences, and reason about the correct admissions cycle.

The unit under evaluation is a **native agent product together with its model and execution configuration**. Comparisons therefore record the client version, requested model, authentication mode, tools, permissions, attempts, and captured answers. A model name alone does not identify a reproducible result.

**This public development set contains 75 tasks across 24 anonymized student case groups.** It includes 61 single-stage tasks and 14 two-stage tasks, for 89 answer stages. Task prompts and scoring materials are in Chinese. Documentation is available in English and Chinese.

## Dataset Structure

| Configuration | Split | Rows | Contents |
| --- | --- | ---: | --- |
| `single-stage` (default) | `dev` | 61 | 23 program-recommendation tasks and 38 planning or decision tasks |
| `staged` | `dev` | 14 | Two-stage tasks that disclose additional information after the first answer |
| `rubrics` | `dev` | 75 | One scoring rubric per task, joined by `task_id` |

The default `single-stage` configuration contains **61 rows**. Select `staged` to inspect the remaining 14 tasks. The 75 rubric rows are annotations for the same tasks, not 75 additional questions. Both task configurations use the `dev` split.

The full collection has **75 public development tasks and 125 private test tasks**. Private questions and rubrics are excluded from this repository. The private set shares underlying student cases with the public set; it is not an independent holdout of unseen students. The 20-task and 40-task experiment selections are subsets of the public 75, not additional data or separate train/test splits.

```text
README.md / README.zh-CN.md       English and Chinese dataset cards
single-stage.jsonl               61 single-stage rows
staged.jsonl                     14 two-stage rows
rubrics.jsonl                    75 corresponding scoring rubrics
tasks/<task_id>/task.json        Readable canonical task records
tasks/<task_id>/rubric.json      Readable canonical scoring records
selection-20.json                Initial experiment selection
selection-40.json                Expanded experiment selection
selection-75.json                Public release scope
scoring.md                       Authoritative scoring policy (Chinese)
manifest.json / checksums.json   Scope, status, and file integrity
```

## Quick Start

After downloading and extracting the data files, run this from the dataset directory. It uses only Python's standard library:

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
print(single[0]["input"])  # Candidate-visible message for this single-stage task

# Organizer inspection only: later stages must remain hidden until their turn.
stages = json.loads(staged[0]["stages_json"])
print(stages[0]["instruction"])
```

If you already use the Hugging Face `datasets` library, the local files can also be loaded with:

```python
from datasets import load_dataset

single = load_dataset("json", data_files={"dev": "single-stage.jsonl"}, split="dev")
staged = load_dataset("json", data_files={"dev": "staged.jsonl"}, split="dev")
```

## Data Instances and Fields

For example, task `BY-A-PLAN` contains this original Chinese question:

> 现在是2024年10月，我在苏州大学能源学院读大二上，专业是新能源材料与器件（中外合作办学），希望以后争取本校推免资格。我应该从哪些事情开始准备，怎么安排接下来两年的学习和实践？

It asks for a two-year preparation plan from the student's stated point in time. The exported `input` also includes the shared response and `answer.md` delivery instructions. Use that full field for execution; the excerpt above illustrates the task content only.

| Field | Meaning | Candidate input? |
| --- | --- | --- |
| `task_id` | Stable task identifier; joins questions and rubrics | Record with the run |
| `input` | Complete message for a single-stage task | Yes, single-stage only |
| `stages_json` | JSON-encoded ordered stage records with `stage_id`, `visible_at`, and `instruction` | Release only the current stage through the runner |
| `task_json` | JSON-encoded canonical task, including organizer metadata | No; do not pass the whole record |
| `track` | Original source track: `dev` or `staged-dev` | Organizer metadata |
| `category` | Task category used in the public selection | Organizer metadata |
| `case_group_id` | Groups related tasks from the same student case | Organizer metadata |
| `stage_count` | Number of answer stages, either 1 or 2 | Organizer metadata |
| `in_first_experiment` | Whether the task belongs to the initial 20-task selection | Organizer metadata |
| `task_sha256`, `rubric_sha256` | Canonical content fingerprints | Integrity metadata |
| `effective_review` | Current review status and its recorded basis | Organizer metadata |
| `rubric_json` | JSON-encoded scoring rubric, in the `rubrics` configuration | Reviewer only |

Decode the `*_json` fields with `json.loads`. Canonical content fingerprints and file-byte hashes in `checksums.json` serve different purposes and are not interchangeable.

## Running an Evaluation

Use the companion code package with a matching data version. Its `docs/reproduction.md` describes the evaluation workflow, and `docs/native-cli.md` documents supported native clients and execution settings.

1. Freeze the selected task IDs, client and model configuration, authentication mode, tool access, timeout, and retry policy.
2. Start an independent candidate session for each task. Give single-stage tasks their `input`; for staged tasks, use the runner to disclose each stage in order and retain the same task session across stages.
3. Capture the complete answer and execution evidence. Keep rubrics, reference candidates, other answers, and future-stage information outside the candidate's accessible input.
4. Review the answer against the matching rubric and recompute scores with the versioned scoring code. Retain the evidence supporting each judgment.

Reading the JSONL files is not itself an evaluation. The full task records are organizer materials and should not be mounted wholesale into a candidate workspace.

## Evaluation and Scoring

Each task is scored out of **100**, using its own rubric. Two-stage tasks count once in the task-level aggregate. Independent review assesses meaning, student fit, and supporting evidence; the scoring program validates records and computes the result.

For the 23 single-stage program-recommendation tasks, project matching contributes 70 points and recommendation quality contributes 30. Valid matches receive 100% for equivalent projects, 60% for closely related programs within the same department, or 30% for substantively related programs in a different department of the same institution. The scorer uses a maximum-score one-to-one assignment so repeated recommendations cannot collect duplicate coverage credit. Other tasks follow their task-specific rubrics.

A reference list is not the only valid prose answer. An omitted citation or a recommendation outside the reference list is not automatically a factual error; matching credit and factual validity are separate judgments. Substantive unresolved evidence disputes remain pending. Do not present a mean over only the scored answers as a complete benchmark result; report completion, failures, and pending reviews alongside scores. See the [scoring rules](../scoring.md) for the governing policy.

## Data Construction and Review Status

The public tasks are curated from anonymized advising cases and organized into related questions and staged updates. The selection files record the task IDs and content fingerprints. The private collection contains supplementary questions authored from existing cases and evaluation findings; it shares case backgrounds with the public collection.

The maintainer's review record dated 2026-10-09 marks factual review of the existing tasks and teacher calibration of all 200 tasks as complete. The `effective_review` field records this status and its basis in maintainer confirmation. Historical `review` fields in frozen task records are retained for version tracking; use `effective_review` for the current status.

The current aggregate result snapshot is included under `results/`; raw answers and trajectories remain separately distributed. Teacher calibration and agent-answer evaluation are separate procedures; answer-review status and evaluation scope are recorded with each experiment.

## Intended Use and Limitations

- Intended for evaluating and developing agents that perform Chinese admissions advising, retrieval, constraint reasoning, and plan revision. Scores do not estimate an individual student's admission probability.
- Tasks within a case group are related. Use case-group-aware analysis; 75 tasks do not represent 75 independent students. Public/private case overlap limits claims about unseen-case generalization.
- The 20/40 selections are curated, not random or preregistered samples. An earlier parent selection considered the availability of run records. Do not choose tasks or attempts based on favorable scores.
- Admissions requirements are time-sensitive. Preserve each task's stated date and cycle; do not substitute the execution date or later outcomes for information available in the scenario.
- The documentation is bilingual; the evaluated prompts remain Chinese. Comparisons using translated prompts are a different experimental condition.
- Preserve anonymization and do not attempt to identify the students. External sources retain their own licenses. Results depend on the native product, its model, tools, access conditions, and review procedure.

## License and Citation

Dataset materials are licensed under **CC BY 4.0**; companion code is licensed under **MIT**. See the [data license](../../LICENSE-DATA) and [CITATION.cff](CITATION.cff). Cite the exact task version and release manifest fingerprint used in an experiment.

```bibtex
@misc{baoyan_agent_benchmark_2026,
  title = {Baoyan Agent Benchmark: Public Development Set},
  author = {{Baoyan Agent Benchmark contributors}},
  year = {2026},
  version = {1.0.1}
}
```

Correction reports should identify the task ID, affected version, supporting evidence, and proposed change. Exclude private student information and private test questions.
