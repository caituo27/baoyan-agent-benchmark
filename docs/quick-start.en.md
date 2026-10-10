# Running and scoring the benchmark

Run these commands from the root of the downloaded or extracted repository. Check one real task first, then run the fixed 20-task selection, evaluate it separately, and open the report.

### 1. Prepare the environment and account

- Python 3.10+; Kimi subscription configuration requires Python 3.11+. The framework uses the Python standard library; no `pip install` is needed.
- Automated native CLI execution currently requires macOS with Seatbelt sandboxing. For manual App collection on Linux/Windows, see [reproduction](reproduction.md).
- Install and authenticate the official client you want to evaluate. These examples use the Codex configuration `gpt-6-1-sol`. Other products are described in the [native CLI guide](native-cli.md). Your own account must have access to the configured model.

```sh
python3 -m benchmark setup --agent gpt-6-1-sol
python3 -m benchmark cli-check --agent gpt-6-1-sol
```

`setup` pins the local executable, version, model, and authentication mode in `runs/config/agents.local.json`. Subscription and API access are distinct configurations and are never swapped automatically. Continue after `cli-check` returns `ready_for_trial`. This checks the environment; it does not prove account quota, model entitlement, or successful inference. Do not commit local configuration, credentials, or login files.

### 2. Execute one task

This uses your account and may incur usage charges. Omit `--execute` to preview without calling a model or creating a run directory.

```sh
python3 -m benchmark cli-batch --suite dev \
  --agent gpt-6-1-sol --task N02-01 \
  --out ./runs/codex-one-task --execute
```

Check completion in the terminal or with:

```sh
python3 -m benchmark status --batch-dir ./runs/codex-one-task
```

The answer is saved at `runs/codex-one-task/gpt-6-1-sol/N02-01/r1/workspace/answer.md`, alongside run records. This checks execution; it is not a 20-task result. The next step uses a new directory and fresh answers.

### 3. Run the fixed 20-task selection

`--selection` verifies the selection's source, task, and rubric fingerprints, embeds the complete selection in the batch plan, and uses the selected tasks as the reporting denominator. It automatically includes the selection's two-stage tasks.

```sh
# Preview: 20 tasks and 24 stages per configuration per repeat
python3 -m benchmark cli-batch \
  --selection config/selections/public-dev-20-v1.json \
  --agent gpt-6-1-sol --out ./runs/codex-dev20

# Execute the same plan
python3 -m benchmark cli-batch \
  --selection config/selections/public-dev-20-v1.json \
  --agent gpt-6-1-sol --out ./runs/codex-dev20 --execute
```

Use the same selection for every configuration. To add a configured product, repeat `--agent <configuration-id>` after completing its setup. Usage scales with configurations and registry repeats. Do not combine `--selection` with `--task` or derived-episode options. For a separate public75 experiment, use `config/selections/public-dev-75-v1.json` and a new output directory; keep its results separate from dev20.

Candidates receive only the current prompt. For two-stage tasks, S1 is released only after S0 completes in the same native session. Different tasks use isolated sessions. Rubrics stay on the reviewer side.

### 4. Inspect progress and resume

```sh
python3 -m benchmark status --batch-dir ./runs/codex-dev20

# Resume with the original arguments and directory
python3 -m benchmark cli-batch \
  --selection config/selections/public-dev-20-v1.json \
  --agent gpt-6-1-sol --out ./runs/codex-dev20 --resume --execute
```

Resume continues unattempted tasks and successful stage boundaries while preserving completed answers. Failed, timed-out, or uncertain stages are not automatically retried. Use a new directory after changing the selection, model configuration, execution code, or budget. Historical runs require their matching frozen code for verification.

| Artifact | Location relative to `runs/codex-dev20/` |
| --- | --- |
| Frozen selection, execution plan, and expected scope | `full-batch.json` |
| Frozen client configurations | `agents.frozen.json` |
| Snapshot after completed scheduling steps | `full-status.json`; use `status` above for current progress |
| Single-stage original answer | `single/<configuration-id>/<task-id>/r1/workspace/answer.md` |
| Two-stage records, stage answers, and tool events | `staged/<configuration-id>/<task-id>/r1/` |

### 5. Configure an independent judge and score

The candidate client and judge are configured separately. Copy the template, then set `provider`, `model`, `expected_response_model`, and `endpoint` in `config/judge.local.json`. Check that `parameters` are supported by your provider. `expected_response_model` must match the model identifier returned by the service; replace every placeholder. Supply the key through the template's `BENCHMARK_JUDGE_API_KEY` environment variable, not the configuration file.

```sh
cp config/judge.example.json config/judge.local.json
# Edit config/judge.local.json and securely set BENCHMARK_JUDGE_API_KEY in your shell.

# Prepare review requests without calling the judge
python3 -m benchmark judge-batch --batch-dir ./runs/codex-dev20 \
  --config config/judge.local.json --out ./runs/codex-dev20-judged

# Execute the prepared review using the independent judge's API allowance
python3 -m benchmark judge-batch --batch-dir ./runs/codex-dev20 \
  --config config/judge.local.json --out ./runs/codex-dev20-judged \
  --resume --execute
```

The judge applies each task's rubric; code validates answer quotations and calculates scores. Two-stage answers receive one combined task evaluation. The API judge has no external browsing tool: insufficient evidence remains pending. Preparing templates is not completed review. See the [review protocol](review-protocol.md) for human review, disputes, and verification. Stop candidate execution before reviewing, and do not keep writing to a batch once its review has begun.

### 6. Open and verify the report

The review workflow generates `runs/codex-dev20-judged/leaderboard/index.html` and `leaderboard.json`. Open the HTML in a browser; the JSON contains task statuses, scores, completion, and aggregates. To validate and recompute saved judgments into a new report without model calls:

```sh
python3 -m benchmark leaderboard-export \
  --batch-dir ./runs/codex-dev20-judged \
  --out ./runs/codex-dev20-report
```

Open `runs/codex-dev20-report/index.html`. **The denominator remains 20 tasks. A complete mean appears only when every expected repeat has a valid score.** Missing answers, failures, missing reviews, and pending judgments remain visible; successful tasks are not averaged alone. An incomplete report still writes HTML/JSON and returns exit code 1; validation errors return 2. This is a local experiment report, not automatic entry into an official leaderboard.

Report scope follows the selected task manifest. A single-task trial is not a dev20 result. See the [native CLI guide](native-cli.md) for other execution workflows.
