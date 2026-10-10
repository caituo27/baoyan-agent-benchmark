# Dev20 results

[简体中文](README.zh-CN.md)

Updated: 2026-10-09T22:06:50+08:00

6 configurations have completed all 20 reviews. These are local development-set results.

Bounds cover the fixed 20 tasks using the possible scores of pending items. They are not confidence intervals or finalized means. A complete mean requires scores for all tasks.

**Score verification scope:** This release includes answers, execution records, and preliminary results. The complete item-level judgments and offline score verification package are not currently public, so the public materials alone do not support independent recomputation of all scores. The verification records on this page document recomputation performed locally by the organizer.

| Model | Dev20 mean bounds | Scored | Pending tasks |
| --- | ---: | ---: | ---: |
| GPT-6 Astra | 80.72–80.94 | 19/20 | 1 |
| GPT-6.1 Sol | 80.20–80.42 | 19/20 | 1 |
| DeepSeek V4.1 Flash | 68.61–69.55 | 18/20 | 2 |
| Gemini 3.1 Pro | 55.71–56.81 | 18/20 | 2 |
| Gemini 3.8 Flash | 58.92–62.24 | 16/20 | 4 |
| Kimi K3 | 61.89–62.11 | 19/20 | 1 |

![Dev20 results](score-bounds.svg)

## Results by task type

| Model | Recommendations (6) | Planning & decisions (10) | Two-stage tasks (4) |
| --- | ---: | ---: | ---: |
| GPT-6 Astra | 47.90–48.63 | 95.00 | 94.25 |
| GPT-6.1 Sol | 47.43–48.16 | 94.00 | 94.88 |
| DeepSeek V4.1 Flash | 47.86–49.32 | 76.75–77.75 | 79.38 |
| Gemini 3.1 Pro | 39.29–42.96 | 59.85 | 70.00 |
| Gemini 3.8 Flash | 48.89–50.31 | 60.45–66.25 | 70.12 |
| Kimi K3 | 44.88–45.61 | 67.85 | 72.50 |

## Per-task scores

![Task results](task-scores.svg)

[View pending items](pending-review.md)

<details>
<summary>Review setup and reproduction</summary>

- Selection: public-dev-20-v1. All 20 tasks have equal weight; two-stage tasks receive one score.
- Reviewer: Codex CLI 0.162.0, ChatGPT subscription, gpt-6.1-sol / high / live web search. A single reviewer may introduce model-family bias.
- Recomputed and verified 120 reviews; see [verification.json](verification.json).
- Client, authentication, and tools are recorded in [results.json](results.json). Kimi includes archived answer-recovery and review-timeout recovery records.

Generate a new report (requires the unpublished local review materials):

```sh
python3 scripts/export_review_results.py \
  --review-dir reviews/subset20-preview-20261009-194705 \
  --cohort config/selections/public-dev20-cohort-20261009-kimi.json \
  --out experiments/subset20-results-YYYYMMDD-HHMMSS
```

Add `--png --font /path/to/font.ttc` to generate PNGs.

</details>

[Task data](scores.csv) · [Full results](results.json) · [Verification](verification.json) · [Checksums](checksums.json)
