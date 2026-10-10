#!/usr/bin/env python3
"""English companion figures for the frozen dev20 selection; no model calls.

Uses the same source checks and drawing primitives as the Chinese figures.
Translations are for documentation only, never candidate execution inputs.
"""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.render_benchmark_figures import (
    Figure, load_data, file_hash, BLUE, GREEN, OCHRE, INK, MUTED, LINE, FILLS, LABELS,
)


class EnglishFigure(Figure):
    def header(self, number, title, subtitle):
        self.rect(64, 44, 8, 22, BLUE)
        self.text(88, 44, 'Baoyan Agent Benchmark', 20, INK, True)
        self.text(1536, 46, number + '  /  SUBSET 20', 17, MUTED, anchor='end')
        self.text(64, 108, title, 44, INK, True)
        self.text(64, 179, subtitle, 21, MUTED)

    def paragraph(self, x, y, value, max_width, size=21, color=MUTED, leading=1.6):
        lines = []
        for paragraph in value.split('\n'):
            line = ''
            for word in paragraph.split():
                candidate = (line + ' ' + word).strip()
                width = (self.draw.textlength(candidate, font=self.font(size)) if self.draw
                         else len(candidate) * size * .57)
                if width > max_width and line:
                    lines.append(line); line = word
                else:
                    line = candidate
            lines.append(line)
        for i, line in enumerate(lines):
            self.text(x, y + i * size * leading, line, size, color)
        return y + len(lines) * size * leading


def overview(out, data, font):
    from scripts.render_benchmark_figures import overview as render_overview
    render_overview(out, data, font, language='en')


def distribution(out, data, font):
    counts = data[2]
    f = EnglishFigure('Composition of the first 20 tasks',
        '6 recommendation, 10 planning, and 4 two-stage tasks; 20 cases and 24 stages.', 1000, font)
    f.header('02 / COMPOSITION', '20 tasks, three kinds of decisions',
        'One task per student case. Task categories are exclusive; stages are counted separately.')
    rows = [('Recommendations', 'Find programs under constraints'),
            ('Planning & decisions', 'Prioritize limited time and resources'),
            ('Two-stage tasks', 'Revise advice after new information')]
    for i, (title, note) in enumerate(rows):
        y = 279 + i * 171; color = (BLUE, GREEN, OCHRE)[i]; n = counts[LABELS[i]]
        f.text(64, y, title, 27, color, True); f.text(64, y + 45, note, 19, MUTED)
        for j in range(10):
            x = 467 + j * 74
            f.circle(x, y + 33, 22, color if j < n else '#F1F3F7')
            if j < n: f.text(x, y + 21, j + 1, 19, 'white', True, 'middle')
        f.text(1320, y - 7, n, 61, color, True, 'end')
        f.text(1341, y + 20, 'tasks', 23, INK)
        f.text(1536, y + 16, f'{n/20:.0%}', 32, MUTED, anchor='end')
        f.line(64, y + 121, 1536, y + 121, LINE, 1)
    f.text(64, 802, 'Why 24 stages?', 25, INK, True)
    f.circle(511, 824, 13, BLUE); f.text(547, 808, '16 × 1', 29, INK, True)
    f.text(711, 808, '+', 29, MUTED)
    f.circle(829, 824, 13, OCHRE); f.circle(877, 824, 13, OCHRE)
    f.line(843, 824, 863, 824, OCHRE, 2); f.text(914, 808, '4 × 2', 29, INK, True)
    f.text(1106, 808, '=', 29, MUTED); f.text(1222, 792, '24', 58, INK, True)
    f.text(1321, 820, 'stages', 23, INK)
    f.text(547, 866, 'Single-stage', 18, MUTED); f.text(914, 866, 'Two-stage', 18, MUTED)
    f.footer('Each filled dot is one task. Gray dots complete the common 10-task scale; they are not missing tasks.')
    f.save(out, 'dataset-distribution')


def flow(out, data, font):
    f = EnglishFigure('Staged execution and independent evaluation',
        'S0 to A0, then S1 to A1 in the candidate session. Both answers and organizer-held rubrics enter independent evaluation.', 1100, font)
    f.header('03 / PROTOCOL', 'Answer using only the facts available now',
        'Release prompts stage by stage. Separate candidates from reviewers and retain original records.')
    f.rect(64, 263, 1054, 463, '#F7F9FE', radius=12)
    f.rect(1150, 263, 386, 463, '#FCF8F3', radius=12)
    f.text(90, 286, 'CANDIDATE  /  One task, one session', 22, BLUE, True)
    f.text(1175, 286, 'ORGANIZER  /  Materials', 22, OCHRE, True)
    nodes = [(92, 'S0', 'Initial prompt', BLUE), (350, 'A0', 'First answer', BLUE),
             (608, 'S1', 'New facts', OCHRE), (866, 'A1', 'Revised answer', BLUE)]
    for x, code, title, color in nodes:
        f.document(x, 375, 221, 164, code, color)
        f.text(x + 110, 459, title, 24, INK, True, 'middle')
    for x in (313, 571, 829): f.arrow(x + 4, 462, x + 31, 462, BLUE)
    f.text(590, 333, 'Release S1 only after A0', 21, OCHRE, True, 'middle')
    f.line(590, 365, 590, 438, OCHRE, 1)
    f.text(590, 619, 'Keep both original answers, in sequence', 23, BLUE, True, 'middle')
    f.text(90, 685, 'New HOME, workspace, and session per task; preserve context within the same task.', 20, MUTED)
    for y, title, note in [(372, 'Task rubric', 'Criteria and reference material'),
                          (478, 'Future prompts', 'Release at their assigned stage'),
                          (584, 'Other tasks & answers', 'Keep outside this workspace')]:
        f.rect(1175, y, 4, 54, OCHRE); f.text(1192, y, title, 23, INK, True)
        f.text(1192, y + 36, note, 18, MUTED)
    f.line(460, 539, 460, 556, BLUE, 1); f.line(976, 539, 976, 556, BLUE, 1)
    f.line(460, 556, 1077, 556, BLUE, 1)
    f.route([(1077, 556), (1077, 751), (296, 751), (296, 784)], BLUE)
    f.route([(1485, 405), (1560, 405), (1560, 762), (818, 762), (818, 784)], OCHRE)
    for x, w, fill in [(64, 464, FILLS[0]), (584, 464, FILLS[1]), (1104, 432, '#F4F6F9')]:
        f.rect(x, 784, w, 150, fill, radius=8)
    for x, n, title, note, color in [(88, '1', 'Anonymous packet', 'A0 + A1 count as one task', BLUE),
                                   (608, '2', 'Independent review', 'Rubric judgments, quotes, reasons', GREEN),
                                   (1128, '3', 'Scoring code', 'Validate, archive, recompute', INK)]:
        f.text(x, 807, n, 18, color, True); f.text(x + 34, 802, title, 26, INK, True)
        f.text(x, 875, note, 20, MUTED)
    f.arrow(536, 860, 576, 860, BLUE); f.arrow(1056, 860, 1096, 860, GREEN)
    f.text(64, 979, 'Keep failures and pending items visible. Report a complete mean only for a fully scored selection.', 22, INK)
    f.footer('Method illustration. Disclose sandbox, authentication, and network conditions with each experiment.')
    f.save(out, 'evaluation-flow')


def case_figure(out, data, font):
    rubric = data[5]
    f = EnglishFigure('N16-02: new experience, unchanged degree constraints',
        'New engineering projects add evidence of fit, but do not establish a formally declared major. Task rubric weights total 100.', 1100, font)
    f.header('04 / CASE STUDY', 'Do more projects remove a degree constraint?',
        'N16-02  /  Translated excerpts from a two-stage task: new evidence and an unchanged constraint.')
    f.document(64, 273, 413, 421, 'S0  /  INITIAL BACKGROUND', BLUE)
    f.text(92, 354, 'General engineering', 31, INK, True)
    f.text(92, 410, 'No declared major yet', 24, OCHRE, True)
    f.line(92, 462, 448, 462, LINE, 1)
    for y, key, value in [(491, 'Rank', '19/123'), (541, 'CET-6', '458')]:
        f.text(92, y, key, 21, MUTED); f.text(218, y, value, 24, INK, True)
    f.text(92, 591, 'Target', 21, MUTED)
    f.text(92, 627, 'Mechanical / smart manufacturing', 20, INK, True)
    f.text(585, 282, 'S1  /  ADDITIONAL FACTS', 21, OCHRE, True)
    f.rect(581, 330, 955, 109, FILLS[2], radius=8); f.badge(616, 366, '+', OCHRE)
    f.text(650, 351, 'Mechanical innovation, student research, smart lock project', 25, INK, True)
    f.text(650, 395, 'The prompt reiterates: general engineering, with no formally declared major.', 19, MUTED)
    f.arrow(493, 385, 561, 385, BLUE)
    f.route([(1048, 439), (1048, 481), (820, 481), (820, 510)], GREEN)
    f.route([(1048, 481), (1318, 481), (1318, 510)], OCHRE)
    f.text(583, 548, 'What changed', 28, GREEN, True); f.rect(583, 592, 6, 96, GREEN)
    f.text(610, 590, 'Evidence of skills and research fit', 24, INK, True)
    f.text(610, 639, 'Verify personal role and project outcomes', 20, MUTED)
    f.text(1109, 548, 'What did not', 28, OCHRE, True); f.rect(1109, 592, 6, 96, OCHRE)
    f.text(1136, 590, 'Formal major designation', 24, INK, True)
    f.text(1136, 639, 'Check target program eligibility', 20, MUTED)
    f.line(64, 741, 1536, 741, LINE, 1)
    f.text(64, 776, 'REVIEW FOCUS', 20, MUTED)
    f.text(267, 765, 'Reassess fit without dropping eligibility constraints.', 31, INK, True)
    f.text(267, 820, 'Advice may change or stay the same. Either way, give reasons and next steps.', 22, MUTED)
    f.text(64, 891, '100 pts', 34, INK, True); f.text(64, 940, 'Rubric weights', 18, MUTED)
    short = ['Major risk', 'Rank / English', 'Contributions', 'Degree fit',
             'Timing / backup', 'Evidence limits', 'Route tradeoffs', 'Advice revision']
    for i, node in enumerate(rubric['nodes']):
        x = 282 + i * 157
        f.text(x, 889, node['points'], 26, BLUE, True)
        f.rect(x, 929, 132, 5, '#ECF0F7'); f.rect(x, 929, 132 * node['points'] / 24, 5, BLUE)
        f.text(x, 951, short[i], 16, MUTED)
    f.footer('Judge each answer using facts available then. Score both stages as one task; do not double-penalize errors.')
    f.save(out, 'case-n16-02')


def guide(path, out, png):
    import os
    prefix = Path(os.path.relpath(out, path.parent)).as_posix()
    ext = 'png' if png else 'svg'
    path.write_text(f'''# Baoyan Agent Benchmark: illustrated guide

[简体中文](benchmark-guide.md) · [Execution instructions](../README.md#quick-start)

Four figures introduce the task set, evaluation process, and a two-stage example. Version: **1.0.1 / public-dev-20-v1**. Evaluation uses the original Chinese prompts and rubrics; English excerpts are translations.

## 1. What is evaluated?

![Task overview]({prefix}/benchmark-overview.{ext})

We compare complete native agent products, including their models, tools, and authentication configurations. Tasks ask agents to interpret backgrounds, assess program fit, and propose concrete actions. Two-stage tasks test whether advice responds to newly released facts while retaining constraints that still apply.

## 2. What is in the first selection?

![Task composition]({prefix}/dataset-distribution.{ext})

| Task type | Tasks | Stages |
| --- | ---: | ---: |
| Recommendations | 6 | 6 |
| Planning and decisions | 10 | 10 |
| Two-stage tasks | 4 | 8 |
| Total | 20 | 24 |

The first experiment includes 20 tasks from 20 student cases. Each filled dot represents one task. See the [selection notes](public-subset-20.md) for how the tasks were chosen.

## 3. How are tasks run and scored?

![Execution and evaluation]({prefix}/evaluation-flow.{ext})

Freeze the selection, task and rubric versions, configuration, and budget. Release only the current prompt to the candidate. Keep original answers and tool records. Review each task independently with its rubric, then validate quotations and recompute scores in code. A two-stage task receives one task score. Missing, failed, and pending items are marked in the results.

Native execution currently uses a macOS process sandbox. Report authentication, tools, network restrictions, execution differences, and retries with each experiment. See the [six-step execution guide](../README.md#quick-start).

## 4. Example: N16-02

![New projects and an unchanged major constraint]({prefix}/case-n16-02.{ext})

**Task time: the 2026 recommendation admission cycle.** 

**S0 — initial background**

> I am in the general engineering program at Xi'an Jiaotong University, ranked 19/123, with a CET-6 score of 458. I have not formally declared a major. I have done mechanical engineering projects and want to apply for mechanical engineering or smart manufacturing, but I do not know whether my undergraduate major designation will limit my options. Can you help me assess this?

Save the first answer before releasing the second stage.

**S1 — additional experience**

> I have also worked on mechanical innovation, a provincial student research project, and a smart lock system. But my registered program is still general engineering; I have not formally entered smart manufacturing. Given this information, how would you identify suitable programs for me?

New projects add evidence of capability and research fit. They do not change the student's formal major designation. Review checks whether the agent uses the new evidence while retaining program eligibility constraints. Advice may change or stay the same, but it needs reasons and actionable next steps. The figure's abbreviated rubric labels are explanatory; the [original rubric](../data/staged-dev/N16-02/rubric.json) governs scoring.

## Sources and regeneration

- Data: [first 20 tasks](../config/selections/public-dev-20-v1.json).
- [Figure manifest]({prefix}/manifest.json): sources and file checksums.
- Each figure is supplied as SVG and PNG; the bundled images need no rendering dependencies to read.


Generate SVG files with the standard library:

```sh
python3 scripts/render_benchmark_figures_en.py
```

With an existing Pillow installation and font, add `--png --font /path/to/font.ttc`. Each experiment keeps its own selection and source versions; a different task set needs its own figures and report.
''', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=ROOT / 'docs/figures/subset20-en-v1')
    parser.add_argument('--png', action='store_true')
    parser.add_argument('--font', type=Path)
    args = parser.parse_args()
    if args.png and not (args.font and args.font.is_file()):
        parser.error('--png needs an existing font supplied with --font')
    data = load_data(); args.out.mkdir(parents=True, exist_ok=True)
    font = args.font if args.png else None
    for render in (overview, distribution, flow, case_figure): render(args.out, data, font)
    guide_path = ROOT / 'docs/benchmark-guide.en.md'
    guide(guide_path, args.out, args.png)
    sources = sorted(set(data[-1] + ['scripts/render_benchmark_figures.py', 'scripts/render_benchmark_figures_en.py']))
    files = [args.out / (name + ext) for name in ('benchmark-overview', 'dataset-distribution', 'evaluation-flow', 'case-n16-02')
             for ext in (('.svg', '.png') if args.png else ('.svg',))]
    manifest = {'schema': 'benchmark-figures.1', 'language': 'en', 'translation_only': True,
                'selection_id': data[0]['id'], 'task_count': len(data[0]['tasks']),
                'case_group_count': len(data[3]), 'stage_count': sum(t['stage_count'] for t in data[0]['tasks']),
                'visual_revision': '1', 'contains_model_scores': False,
                'source_files_sha256': {n: file_hash(ROOT / n) for n in sources},
                'files': {p.name: file_hash(p) for p in files},
                'guide_path': guide_path.relative_to(ROOT).as_posix(), 'guide_sha256': file_hash(guide_path),
                'png_font': args.font.name if font else None,
                'note': 'Documentation translations only; original Chinese execution inputs and rubric weights are unchanged.'}
    (args.out / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'figures': len(files), 'language': 'en', 'output': str(args.out)}))


if __name__ == '__main__':
    main()
