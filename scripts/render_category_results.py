#!/usr/bin/env python3
"""Render bilingual task-type score charts from an existing results snapshot."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.render_benchmark_figures import EditorialFigure

CATEGORIES = ('Recommendations', 'Planning & decisions', 'Two-stage tasks')
COUNTS = (6, 10, 4)
LABELS = ('择校推荐', '规划与决策', '两阶段任务')


def score(value):
    if value['mean'] is not None:
        return f"{value['mean']:.2f}"
    bounds = value['score_bounds']
    return '–'.join(f'{v:.2f}' for v in bounds) if bounds is not None else '—'


def rows_in_homepage_order(data, readme):
    names = [line.split('|')[1].strip() for line in readme.splitlines()
             if line.startswith('| ') and not line.startswith('| ---')]
    rows = data['summary']
    if any(row['name'] not in names for row in rows):
        raise ValueError('Every chart configuration must appear in the homepage')
    return sorted(rows, key=lambda row: names.index(row['name']))


def table(rows, zh):
    labels = LABELS if zh else CATEGORIES
    headings = ['模型' if zh else 'Model'] + [
        f'{label}（{n}题）' if zh else f'{label} ({n})'
        for label, n in zip(labels, COUNTS)]
    lines = ['| ' + ' | '.join(headings) + ' |', '| --- | ---: | ---: | ---: |']
    for row in rows:
        lines.append('| ' + row['name'] + ' | ' + ' | '.join(
            score(row['categories'][category]) for category in CATEGORIES) + ' |')
    return '\n'.join(lines)


def render(rows, out, source_digest, zh):
    ink, muted, paper, rule = '#30283F', '#746C7E', '#FAF7F1', '#E4D9CD'
    purple, gold, track = '#7854A6', '#E9B949', '#EDE5EF'
    pending = any(row['pending'] for row in rows)
    height = 390 + len(rows) * 68
    title = '不同题型，表现如何？' if zh else 'How do scores vary by task type?'
    f = EditorialFigure(title, 'Task-type means on shared 0–100 axes; gold marks unresolved score ranges, not confidence intervals. Source results.json SHA256: ' + source_digest, height)
    # The card touches both canvas edges, aligning with the README table.
    f.rect(0, 0, 1600, height, paper, radius=36)
    f.text(56, 34, 'DEV20 / TASK-TYPE RESULTS', 18, purple, True)
    f.text(56, 79, title, 42, ink, True)
    subtitle = ('每类题目等权计分 · 统一100分制' if zh
                else 'Equal task weights within each category · Common 100-point scale')
    f.text(56, 139, subtitle, 22, muted)
    f.rect(56, 189, 18, 18, purple, radius=3)
    f.text(84, 187, ('确定得分 / 下界' if zh else 'Score / lower bound') if pending else ('确定得分' if zh else 'Score'), 20, ink)
    if pending:
        f.rect(360, 189, 18, 18, gold, radius=3)
        f.text(388, 187, '待核项可增加的得分' if zh else 'Unresolved contribution', 20, ink)
    first_y, last_y = 306, 306 + (len(rows) - 1) * 68
    labels = LABELS if zh else CATEGORIES
    for column, (category, label, count) in enumerate(zip(CATEGORIES, labels, COUNTS)):
        x = 364 + column * 396
        f.text(x, 236, f'{label} · {count}' + ('题' if zh else ' tasks'), 22, ink, True)
        for tick in (0, 50, 100):
            tx = x + tick * 2.3
            f.text(tx, 273, str(tick), 16, muted, anchor='middle')
            f.line(tx, first_y - 8, tx, last_y + 34, rule, 1)
        for i, row in enumerate(rows):
            value = row['categories'][category]
            if value['expected'] != count:
                raise ValueError(f'Unexpected task count for {category}')
            bounds = value['score_bounds']
            y = first_y + i * 68
            if bounds is not None:
                lower, upper = bounds
                if not 0 <= lower <= upper <= 100:
                    raise ValueError('Score bounds outside the 100-point scale')
                f.rect(x, y, 230, 26, track, radius=4)
                f.rect(x, y, lower * 2.3, 26, purple, radius=4)
                if upper > lower:
                    f.rect(x + lower * 2.3, y, (upper - lower) * 2.3, 26, gold)
            f.text(x + 244, y + 3, score(value), 19, ink)
    for i, row in enumerate(rows):
        f.text(56, first_y + i * 68 + 2, row['name'], 24, ink, True)
    note = ('区间表示待核得分上下界，不是置信区间；不同题型的任务与评分标准不同。' if zh
            else 'Ranges show unresolved score bounds, not confidence intervals. Tasks and rubrics differ by category.')
    if not pending:
        note = ('按20题总均分排序；不同题型的任务与评分标准不同。' if zh
                else 'Ordered by overall Dev20 mean. Tasks and rubrics differ by category.')
    f.text(56, height - 42, note, 19, muted)
    f.save(out, 'category-scores.' + ('zh-CN' if zh else 'en'))


def render_overall(rows, out, source_digest, zh):
    """Render complete means in the homepage's score order, preserving reports."""
    ink, muted, paper, rule = '#30283F', '#746C7E', '#FAF7F1', '#E4D9CD'
    purple, track = '#7854A6', '#EDE5EF'
    height = 380 + len(rows) * 78
    title = '20题均分排名' if zh else 'Dev20 score ranking'
    f = EditorialFigure(title, 'Descending complete Dev20 means. Source results.json SHA256: ' + source_digest, height)
    f.rect(0, 0, 1600, height, paper, radius=36)
    f.text(56, 34, 'DEV20 / OVERALL RESULTS', 18, purple, True)
    f.text(56, 79, title, 42, ink, True)
    f.text(56, 139, f'{len(rows)}个配置 · 同一组20题 · 满分100分' if zh else f'{len(rows)} configurations · Same 20 tasks · 100-point scale', 22, muted)
    x0, width, first_y = 500, 880, 245
    axis_y = first_y + len(rows) * 78 - 34
    for tick in (0, 25, 50, 75, 100):
        x = x0 + width * tick / 100
        f.line(x, first_y - 24, x, axis_y, rule, 1)
        f.text(x, axis_y + 12, str(tick), 17, muted, anchor='middle')
    for i, row in enumerate(rows):
        value = row['mean']
        if value is None or not 0 <= value <= 100:
            raise ValueError('Complete means required for score ranking')
        y = first_y + i * 78
        f.text(56, y + 4, str(i + 1), 24, muted)
        f.text(110, y + 4, row['name'], 25, ink, True)
        f.rect(x0, y, width, 32, track, radius=5)
        f.rect(x0, y, width * value / 100, 32, purple, radius=5)
        f.text(1528, y + 3, f'{value:.2f}', 28, ink, True, anchor='end')
    f.text(56, height - 42, '开发集初评 · 按均分从高到低排列' if zh else 'Development-set initial evaluation · Highest mean first', 19, muted)
    f.save(out, 'overall-scores.' + ('zh-CN' if zh else 'en'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results', required=True, type=Path)
    parser.add_argument('--readme', default=Path('README.md'), type=Path,
                        help='Use the same model order as this homepage')
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    source = args.results.read_bytes()
    rows = rows_in_homepage_order(json.loads(source), args.readme.read_text())
    args.out.mkdir(parents=True, exist_ok=True)
    for zh in (False, True):
        render(rows, args.out, sha256(source).hexdigest(), zh)
        if all(row['mean'] is not None for row in rows):
            render_overall(sorted(rows, key=lambda row: -row['mean']), args.out, sha256(source).hexdigest(), zh)


if __name__ == '__main__':
    main()
