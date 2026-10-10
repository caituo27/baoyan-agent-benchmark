# Dev20 results

**Erratum applied:** All seven configurations were rechecked for SYSU N06-10, resolving five pending nodes. All 140 original scores were replayed, and seven derived judgments recomputed. Other judgments are inherited. This scoped adjudication follows the owner-approved correction; it is neither a candidate rerun nor a new independent model review. The original snapshot is preserved.

[简体中文](README.zh-CN.md)

Updated: 2026-10-10T00:19:38+08:00

This report includes 7 configurations; 7 have completed all 20 reviews. These are preliminary local development-set results.

Bounds cover the fixed 20 tasks using the possible scores of pending items. They are not confidence intervals or finalized means. A complete mean requires scores for all tasks.

**Score verification scope:** This release includes answers, execution records, and preliminary results. The complete item-level judgments and offline score verification package are not currently public, so the public materials alone do not support independent recomputation of all scores. The verification records on this page document recomputation performed locally by the organizer.

| Model | Dev20 mean bounds | Reviewed | Scored | Pending tasks |
| --- | ---: | ---: | ---: | ---: |
| GPT-6 Astra | 80.85 | 20/20 | 20/20 | 0 |
| GPT-6.1 Sol | 80.42 | 20/20 | 20/20 | 0 |
| DeepSeek V4.1 Flash | 68.83–69.55 | 20/20 | 18/20 | 2 |
| Gemini 3.1 Pro | 55.84–56.72 | 20/20 | 18/20 | 2 |
| Gemini 3.8 Flash | 58.92–62.24 | 20/20 | 16/20 | 4 |
| Qwen 3.8 Max | 65.97 | 20/20 | 20/20 | 0 |
| Kimi K3 | 62.11 | 20/20 | 20/20 | 0 |

Execution snapshot: Qwen 3.8 Max has 20/20 completed answers and 20/20 reviews. 6 answers used new sessions with prior records and an extended budget after timeouts; these are supplemental executions, not native session resumes. 6 of those answers have been reviewed. 4 were verified as delivered without restorable session checkpoints. Per-task execution modes, original failures, and recovery provenance are recorded below.

[Execution records and answer fingerprints](execution-progress.json)

![Dev20 results](score-bounds.svg)

## Results by task type

| Model | Recommendations (6) | Planning & decisions (10) | Two-stage tasks (4) |
| --- | ---: | ---: | ---: |
| GPT-6 Astra | 48.34 | 95.00 | 94.25 |
| GPT-6.1 Sol | 48.16 | 94.00 | 94.88 |
| DeepSeek V4.1 Flash | 48.59–49.32 | 76.75–77.75 | 79.38 |
| Gemini 3.1 Pro | 39.73–42.66 | 59.85 | 70.00 |
| Gemini 3.8 Flash | 48.89–50.31 | 60.45–66.25 | 70.12 |
| Qwen 3.8 Max | 48.16 | 74.95 | 70.25 |
| Kimi K3 | 45.61 | 67.85 | 72.50 |

## Per-task scores

![Task results](task-scores.svg)

[View pending items](pending-review.md)

<details>
<summary>Review setup and reproduction</summary>

- Selection: public-dev-20-v1. All 20 tasks have equal weight; two-stage tasks receive one score.
- Reviewer: Codex CLI 0.162.0, ChatGPT subscription, gpt-6.1-sol / high / live web search. A single reviewer may introduce model-family bias.
- Recomputed and verified 140 reviews; see [verification.json](verification.json).
- Client, authentication, and tools are recorded in [results.json](results.json). Kimi includes archived answer-recovery and review-timeout recovery records; Qwen BY-H-APPLY also required a separate review after timeout using the same inputs and configuration.

Generate a new report (requires the unpublished local review materials):

```sh
python3 scripts/apply_sysu_erratum.py \
  --base-report experiments/subset20-results-seven-complete-20261010 \
  --out experiments/subset20-results-sysu-NEW \
  --adjudication-out reviews/subset20-sysu-NEW
```



</details>

[Task data](scores.csv) · [Full results](results.json) · [Verification](verification.json) · [Checksums](checksums.json)
