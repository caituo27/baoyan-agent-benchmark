#!/usr/bin/env python3
"""Apply hash-bound evidence adjudications using the original frozen scorer.

Replay all original and inherited scores before writing a new derived report.
"""
import argparse
from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path
import sys
import tempfile
from zoneinfo import ZoneInfo

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import export_review_results as export


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--erratum', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--adjudication-out', type=Path, required=True)
    parser.add_argument('--evidence-dir', type=Path, required=True)
    args = parser.parse_args()
    erratum, out, local = (p.resolve() for p in (args.erratum, args.out, args.adjudication_out))
    export.require(all(p.is_relative_to(ROOT) for p in (erratum, out, local)), 'Paths must be in repository')
    export.require(not out.exists() and not local.exists(), 'Use new output directories')
    export.require(not out.is_relative_to(local) and not local.is_relative_to(out), 'Separate outputs')
    export.verify_hashes(erratum, export.read(erratum / 'checksums.json')['files'])
    decision = export.read(erratum / 'decision.json')
    base = export.safe_path(ROOT, decision['base_report'])
    export.verify_hashes(base, export.read(base / 'checksums.json')['files'])
    export.require(export.sha(base / 'results.json') == decision['base_results_sha256'] and
                   export.sha(base / 'verification.json') == decision['base_verification_sha256'], 'Base changed')
    original = export.read(base / 'results.json')
    data = deepcopy(original)
    audit = export.read(base / 'verification.json')
    source = ROOT / 'reviews' / data['review_source']
    export.require(export.tree_hashes(source / 'frozen-code') == audit['scoring_code_sha256'], 'Scorer changed')
    export.verify_hashes(source, audit['scope_bindings'])
    sys.path.insert(0, str(source / 'frozen-code'))
    from benchmark.core import digest, input_hash
    from benchmark.scoring import score

    rows = {(r['agent'], r['task_id']): r for r in data['rows']}
    export.require(len(rows) == len(data['rows']) == len(audit['records']) == 140, 'Expected seven complete sets')
    inherited, checked_dirs = {}, set()
    inherited_replays = 0
    for record in audit['records']:
        key = record['agent'], record['task_id']
        packet = source / 'packets' / record['packet']
        execution = source / record['execution_path']
        export.verify_hashes(packet, record['packet_hashes'])
        export.verify_hashes(execution, record['review_files'])
        export.require(export.sha(execution / 'status.json') == record['status_sha256'], 'Status changed')
        task, rubric = (export.read(packet / name) for name in ('task.json', 'rubric.json'))
        answer = (packet / 'answer.md').read_text()
        judgment = export.read(execution / 'judgment.json')
        result = score(task, rubric, answer, judgment)
        export.require(result == export.read(execution / 'score.json'), 'Original replay differs')
        row = rows[key]
        parent = execution
        if row.get('adjudication_path'):
            parent = export.safe_path(ROOT, row['adjudication_path'])
            boundary = next((p for p in parent.parents if p.is_relative_to(ROOT / 'reviews') and (p / 'checksums.json').is_file()), None)
            export.require(boundary is not None, 'Missing inherited hash manifest')
            if boundary not in checked_dirs:
                export.verify_hashes(boundary, export.read(boundary / 'checksums.json')['files'])
                checked_dirs.add(boundary)
            task, rubric = (export.read(parent.parent / name) for name in ('task.json', 'rubric.json'))
            judgment = export.read(parent / 'judgment.json')
            result = score(task, rubric, answer, judgment)
            export.require(result == export.read(parent / 'score.json'), 'Inherited adjudication replay differs')
            inherited_replays += 1
        export.require(all(row[k] == result[k] for k in ('score', 'score_interval', 'pending_nodes')), 'Base row differs')
        inherited[key] = (record, parent, task, rubric, answer, judgment, result)

    changes, outputs, task_versions = [], {}, {}
    agents = {r['agent'] for r in data['summary']}
    changed_keys = set()
    for plan in decision['adjudications']:
        agent, tid = plan['agent'], plan['task_id']
        key = agent, tid
        export.require(key not in changed_keys, 'Duplicate adjudication')
        changed_keys.add(key)
        row = rows[key]
        record, parent, task, rubric, answer, old_j, old_score = inherited[key]
        export.require(plan['packet'] == row['packet'] and
                       export.sha(parent / 'judgment.json') == plan['base_judgment_sha256'] and
                       export.sha(parent / 'score.json') == plan['base_score_sha256'], 'Adjudication input changed')
        task_versions[tid] = task, rubric
        judgment = deepcopy(old_j)
        patches = plan['patches']
        export.require(set(patches) == {'nodes', 'coverage', 'recommendation_review', 'errors'}, 'Unsupported patch scope')
        for field, idkey in [('nodes', 'id'), ('coverage', 'id'), ('recommendation_review', 'answer_item_id')]:
            replacements = {n[idkey]: n for n in patches[field]}
            export.require(len(replacements) == len(patches[field]) and
                           set(replacements) <= {n[idkey] for n in old_j[field]}, 'Invalid patch ids')
            judgment[field] = [deepcopy(replacements.get(n[idkey], n)) for n in old_j[field]]
        export.require(not {e['id'] for e in patches['errors']} & {e['id'] for e in old_j['errors']}, 'Cannot replace existing errors')
        judgment['errors'] += deepcopy(patches['errors'])
        judgment.update(reviewer='Codex-assisted owner-requested evidence adjudication',
                        judge_version='pending-evidence-adjudication-v1')
        result = score(task, rubric, answer, judgment)
        affected = {n['id'] for n in patches['nodes'] + patches['coverage']}
        export.require([n for n in result['nodes'] if n['id'] not in affected] ==
                       [n for n in old_score['nodes'] if n['id'] not in affected], 'Unrelated score node changed')
        for error_id, impacts in old_score['error_impacts'].items():
            export.require(result['error_impacts'].get(error_id) == impacts, 'Existing error allocation changed')
        export.require(judgment['input_sha256'] == input_hash(task) and
                       judgment['task_sha256'] == digest(task) and judgment['rubric_sha256'] == digest(rubric),
                       'Task, rubric or candidate input changed')
        row.update(score=result['score'], score_interval=result['score_interval'],
                   pending_nodes=result['pending_nodes'], score_status=result['status'],
                   adjudication_path=(local / tid / row['packet']).relative_to(ROOT).as_posix())
        row['deductions'] = [n for n in row['deductions'] if n['node'] not in affected]
        reasons = {n['id']: n['reason'] for n in judgment['nodes'] + judgment['coverage']}
        quality_weights = {n['id']: n['points'] for n in rubric['nodes']}
        for node in result['nodes']:
            if node['id'] not in affected or node['points'] is None:
                continue
            maximum = quality_weights.get(node['id'])
            if maximum is None:
                maximum = node['weight']['numerator'] / node['weight']['denominator']
            if node['points'] < maximum - .01:
                row['deductions'].append({'node': node['id'], 'points': node['points'],
                                          'max_points': round(maximum, 4), 'reason': reasons[node['id']]})
        row['deductions'].sort(key=lambda n: n['node'])
        changes.append({'agent': agent, 'name': row['name'], 'task_id': tid,
                        'affected_nodes': sorted(affected), 'packet': row['packet'],
                        'prior_judgment_path': parent.relative_to(ROOT).as_posix(),
                        'prior_judgment_sha256': plan['base_judgment_sha256'],
                        'original_evidence_sha256': export.sha(source / record['execution_path'] / 'evidence.json'),
                        'source_ids': plan['source_ids'],
                        'before': {k: old_score[k] for k in ('score', 'score_interval', 'pending_nodes')},
                        'after': {k: result[k] for k in ('score', 'score_interval', 'pending_nodes')},
                        'judgment_sha256': digest(judgment), 'score_sha256': digest(result)})
        outputs[tid, row['packet']] = judgment, result
    remaining = []
    for pending in data['pending']:
        row = rows[pending['agent'], pending['task_id']]
        if pending['node'] not in row['pending_nodes']:
            continue
        pending['score_interval'] = row['score_interval']
        key = pending['task_id'], pending['packet']
        if key in outputs:
            judgment = outputs[key][0]
            pending['reason'] = next(n['reason'] for n in judgment['nodes'] + judgment['coverage'] if n['id'] == pending['node'])
        remaining.append(pending)
    data['pending'] = remaining
    tasks = {t['task_id']: t for t in data['tasks']}
    for summary in data['summary']:
        part = [r for r in data['rows'] if r['agent'] == summary['agent']]
        summary.update(export.aggregate(part, tasks, list(tasks)))
        summary['categories'] = {en: export.aggregate(part, tasks, [tid for tid, t in tasks.items() if t['category'] == zh])
                                 for zh, en in export.CATEGORIES.items()}
    export.require([r for r in data['rows'] if (r['agent'], r['task_id']) not in changed_keys] ==
                   [r for r in original['rows'] if (r['agent'], r['task_id']) not in changed_keys], 'Unrelated rows changed')
    now = datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
    metadata = {'id': decision['id'], 'date': now, 'kind': 'scoped_owner_requested_evidence_adjudication',
                'base_report': decision['base_report'], 'base_results_sha256': decision['base_results_sha256'],
                'decision_path': (erratum / 'decision.json').relative_to(ROOT).as_posix(),
                'decision_sha256': export.sha(erratum / 'decision.json'),
                'candidate_reruns': 0, 'new_independent_model_reviews': 0,
                'configurations_rechecked': len(agents), 'task_answers_recomputed': len(changes),
                'original_scores_replayed': len(inherited), 'inherited_scores_replayed': inherited_replays,
                'local_review_directory': local.relative_to(ROOT).as_posix(), 'changes': changes}
    data['adjudication_history'] = data.get('adjudication_history', []) + [data['adjudication']]
    data.update(generated_at=now, adjudication=metadata,
                extension_rule='New evidence adjudication retaining previous SYSU/XMU/BIT corrections; no rubric or candidate input changes.')
    audit['adjudication_history'] = audit.get('adjudication_history', []) + [audit['adjudication']]
    audit.update(adjudication=metadata, adjudicated_judgments=len(changes),
                 verification='140 original scores and 14 inherited corrections replayed; four evidence adjudications recomputed with the same task, rubric, answer and frozen scorer. 136 other rows and unrelated score nodes preserved.')
    out.parent.mkdir(parents=True, exist_ok=True)
    local.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.evidence-adjudication-', dir=out.parent) as tmp:
        stage = Path(tmp) / 'report'; stage.mkdir()
        export.write_tables(stage, data, audit)
        export.charts(stage, data, None)
        for zh in (False, True):
            export.report(stage, data, audit, False, zh=zh)
            path = stage / ('README.zh-CN.md' if zh else 'README.md')
            content = path.read_text()
            notice = ('**证据补查修订：** 保留中山、厦大、北理工修订；新增港科大项目、贸大审计推免、南理工规则与北科大单位及NUS门槛裁决。四份答卷重算，解决四个待核节点；138份数值评分、2份待核、2个待核节点。浸会DAAI六级等效资格和部分校内特殊通道仍待核。原题目、评分规则和答卷均不变，0次答题重跑、0份新增独立模型评审。区间沿用冻结整节点算法，上界不代表已确认错误可得满分。'
                      if zh else '**Evidence adjudication:** Prior SYSU/XMU/BIT corrections are retained. Four answers were recomputed using newly checked programme and admissions evidence, resolving four pending nodes: 138 numeric scores, two pending answers and two pending nodes. HKBU DAAI CET-6 equivalence and some internal recommendation pathways remain unresolved. Tasks, rubrics and answers are unchanged; zero candidate reruns and zero new independent model reviews. Conservative whole-node bounds retain the frozen algorithm; their upper endpoints do not imply confirmed errors can earn full credit.')
            content = content.replace('\n\n', '\n\n' + notice + '\n\n', 1)
            start = content.index('```sh\n'); stop = content.index('```', start + 6)
            command = '\n'.join(['```sh', 'python3 scripts/apply_evidence_adjudications.py \\',
                                 '  --erratum ' + erratum.relative_to(ROOT).as_posix() + ' \\',
                                 '  --evidence-dir ' + local.relative_to(ROOT).as_posix() + '/captured-evidence \\',
                                 '  --out experiments/subset20-results-evidence-NEW \\',
                                 '  --adjudication-out reviews/subset20-evidence-NEW', ''])
            content = content[:start] + command + content[stop:]
            content = content.replace('可添加 `--png --font /path/to/font.ttc` 生成PNG。', '')
            content = content.replace('Add `--png --font /path/to/font.ttc` to generate PNGs.', '')
            path.write_text(content)
        for artifact in list(stage.glob('*.md')) + list(stage.glob('*.csv')):
            artifact.write_text(artifact.read_text().rstrip() + '\n')
        export.put(stage / 'adjudication.json', metadata)
        export.put(stage / 'checksums.json', {'exporter_sha256': export.sha(Path(export.__file__)),
                                             'adjudicator_sha256': export.sha(Path(__file__)), 'files': export.tree_hashes(stage)})
        local.mkdir()
        import shutil
        (local / 'captured-evidence').mkdir()
        for filename, expected in decision['captured_evidence'].items():
            capture = args.evidence_dir / filename
            export.require(export.sha(capture) == expected, 'Evidence capture changed: ' + filename)
            shutil.copyfile(capture, local / 'captured-evidence' / filename)
        for tid, (task, rubric) in task_versions.items():
            export.put(local / tid / 'task.json', task); export.put(local / tid / 'rubric.json', rubric)
        for (tid, packet), (judgment, result) in outputs.items():
            export.put(local / tid / packet / 'judgment.json', judgment)
            export.put(local / tid / packet / 'score.json', result)
        export.put(local / 'receipt.json', metadata)
        export.put(local / 'checksums.json', {'files': export.tree_hashes(local)})
        stage.rename(out)
    print(json.dumps({'out': str(out), 'numeric': sum(r['scored'] for r in data['summary']),
          'pending_answers': sum(r['pending'] for r in data['summary']), 'pending_nodes': len(data['pending']),
          'summary': [{k: r[k] for k in ('name', 'mean', 'score_bounds', 'scored', 'pending')} for r in data['summary']]}, ensure_ascii=False))


if __name__ == '__main__':
    main()
