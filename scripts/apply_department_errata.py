#!/usr/bin/env python3
"""Apply the approved XMU/BIT adjudications to the existing SYSU-corrected snapshot.

Original review evidence and previous reports remain read-only. All original and
inherited scores are replayed; the frozen scorer then computes 14 derived scores.
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
            if parent.parent not in checked_dirs:
                export.verify_hashes(parent.parent, export.read(parent.parent / 'checksums.json')['files'])
                checked_dirs.add(parent.parent)
            task, rubric = (export.read(parent.parent / name) for name in ('task.json', 'rubric.json'))
            judgment = export.read(parent / 'judgment.json')
            result = score(task, rubric, answer, judgment)
            export.require(result == export.read(parent / 'score.json'), 'Inherited adjudication replay differs')
            inherited_replays += 1
        export.require(all(row[k] == result[k] for k in ('score', 'score_interval', 'pending_nodes')), 'Base row differs')
        inherited[key] = (record, parent, task, rubric, answer, judgment, result)

    changes, outputs, task_versions = [], {}, {}
    agents = {r['agent'] for r in data['summary']}
    for tid, spec in decision['tasks'].items():
        export.require(set(spec['adjudications']) == agents, 'Every configuration must be adjudicated')
        task, rubric = (export.read(erratum / tid / name) for name in ('task.json', 'rubric.json'))
        export.require({'task': digest(task), 'rubric': digest(rubric)} == spec['corrected_fingerprints'], 'Wrong correction')
        export.require(input_hash(task) == spec['candidate_input_sha256'], 'Candidate input changed')
        task_versions[tid] = task, rubric
        ref = spec['reference_id']
        for agent, plan in spec['adjudications'].items():
            row = rows[agent, tid]
            record, parent, old_task, old_rubric, answer, old_j, old_score = inherited[agent, tid]
            export.require({'task': digest(old_task), 'rubric': digest(old_rubric)} == spec['base_fingerprints'], 'Wrong prior version')
            export.require(plan['packet'] == row['packet'] and
                           export.sha(parent / 'judgment.json') == plan['base_judgment_sha256'] and
                           export.sha(parent / 'score.json') == plan['base_score_sha256'], 'Adjudication input changed')
            export.require(input_hash(old_task) == input_hash(task) and
                           old_rubric['reference_denominator'] == rubric['reference_denominator'] and
                           old_rubric['coverage_points'] == rubric['coverage_points'], 'Input or weights changed')
            judgment = deepcopy(old_j)
            coverage = next(n for n in judgment['coverage'] if n['id'] == ref)
            before_coverage = deepcopy(coverage)
            candidates = {c['answer_item_id']: c for c in judgment['recommendation_review']}
            matches = []
            for match_plan in plan['matches']:
                candidate = candidates[match_plan['answer_item_id']]
                export.require(candidate['school_key'] == spec['school'] and candidate['validity'] == 'valid'
                               and candidate['treatment'] in ('direct', 'conditional'), 'Invalid positive match')
                matches.append(dict(match_plan, answer_quote=candidate['answer_quote'],
                                    relation_evidence=spec['sources']))
            coverage.clear()
            coverage.update(id=ref, status=plan['status'], matches=matches,
                            matched_answer_item_id=None, error_ids=[], reason=plan['reason'],
                            answer_quote=before_coverage['answer_quote'])
            judgment.update(task_sha256=digest(task), rubric_sha256=digest(rubric),
                            reviewer='Codex-assisted owner-approved department identity adjudication',
                            judge_version='department-identities-adjudication-v1')
            result = score(task, rubric, answer, judgment)
            export.require([n for n in result['nodes'] if n['id'] != ref] ==
                           [n for n in old_score['nodes'] if n['id'] != ref], 'Unrelated scoring node changed')
            export.require(result['error_impacts'] == old_score['error_impacts'] and
                           result['recommendation_review'] == old_score['recommendation_review'], 'Candidate or error judgment changed')
            export.require(result['pending_nodes'] == [n for n in old_score['pending_nodes'] if n != ref], 'Unrelated pending changed')
            after_node = next(n for n in result['nodes'] if n['id'] == ref)
            row.update(score=result['score'], score_interval=result['score_interval'],
                       pending_nodes=result['pending_nodes'], score_status=result['status'],
                       adjudication_path=(local / tid / row['packet']).relative_to(ROOT).as_posix())
            max_points = rubric['coverage_points'] / rubric['reference_denominator']
            row['deductions'] = [n for n in row['deductions'] if n['node'] != ref]
            if after_node['points'] < max_points - .01:
                row['deductions'].append({'node': ref, 'points': after_node['points'],
                                          'max_points': round(max_points, 4), 'reason': coverage['reason']})
            row['deductions'].sort(key=lambda n: n['node'])
            changes.append({'agent': agent, 'name': row['name'], 'task_id': tid, 'reference_id': ref,
                            'packet': row['packet'], 'prior_judgment_path': parent.relative_to(ROOT).as_posix(),
                            'prior_judgment_sha256': plan['base_judgment_sha256'],
                            'original_evidence_sha256': export.sha(source / record['execution_path'] / 'evidence.json'),
                            'before': {'score': old_score['score'], 'score_interval': old_score['score_interval'],
                                       'coverage': before_coverage},
                            'after': {'score': result['score'], 'score_interval': result['score_interval'],
                                      'coverage': coverage, 'allocated_node': after_node},
                            'judgment_sha256': digest(judgment), 'score_sha256': digest(result)})
            outputs[tid, row['packet']] = judgment, result

    affected = {(tid, spec['reference_id']) for tid, spec in decision['tasks'].items()}
    data['pending'] = [n for n in data['pending'] if (n['task_id'], n['node']) not in affected]
    for pending in data['pending']:
        pending['score_interval'] = rows[pending['agent'], pending['task_id']]['score_interval']
    tasks = {t['task_id']: t for t in data['tasks']}
    for summary in data['summary']:
        part = [r for r in data['rows'] if r['agent'] == summary['agent']]
        summary.update(export.aggregate(part, tasks, list(tasks)))
        summary['categories'] = {en: export.aggregate(part, tasks, [tid for tid, t in tasks.items() if t['category'] == zh])
                                 for zh, en in export.CATEGORIES.items()}
    export.require([r for r in data['rows'] if r['task_id'] not in decision['tasks']] ==
                   [r for r in original['rows'] if r['task_id'] not in decision['tasks']], 'Unrelated rows changed')
    now = datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
    metadata = {'id': decision['id'], 'date': now, 'kind': 'scoped_owner_approved_adjudication',
                'base_report': decision['base_report'], 'base_results_sha256': decision['base_results_sha256'],
                'decision_path': (erratum / 'decision.json').relative_to(ROOT).as_posix(),
                'decision_sha256': export.sha(erratum / 'decision.json'),
                'candidate_reruns': 0, 'new_independent_model_reviews': 0,
                'configurations_rechecked': len(agents), 'task_answers_recomputed': len(changes),
                'original_scores_replayed': len(inherited), 'inherited_scores_replayed': inherited_replays,
                'local_review_directory': local.relative_to(ROOT).as_posix(), 'changes': changes}
    data['adjudication_history'] = data.get('adjudication_history', []) + [data['adjudication']]
    data.update(generated_at=now, adjudication=metadata,
                extension_rule='New snapshot applying approved XMU/BIT corrections on top of the preserved SYSU correction.')
    audit['adjudication_history'] = audit.get('adjudication_history', []) + [audit['adjudication']]
    audit.update(adjudication=metadata, adjudicated_judgments=len(changes),
                 verification='140 original scores and 7 inherited SYSU corrections replayed; 14 derived judgments recomputed under XMU/BIT errata. Original records remain provenance. Other nodes, errors, candidates, answers and prompts unchanged.')
    out.parent.mkdir(parents=True, exist_ok=True)
    local.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.department-errata-', dir=out.parent) as tmp:
        stage = Path(tmp) / 'report'; stage.mkdir()
        export.write_tables(stage, data, audit)
        export.charts(stage, data, None)
        for zh in (False, True):
            export.report(stage, data, audit, False, zh=zh)
            path = stage / ('README.zh-CN.md' if zh else 'README.md')
            content = path.read_text()
            notice = ('**修订说明：** 保留此前中山大学勘误，新增厦大N06-14及北理工N14-L1-06统一裁决。七配置共14份相关评审重新计算，解决5个待核节点；DeepSeek北理工项由同院系60%修正为跨院系30%。其余判断继承原评审。未重跑答题模型，本次不是新一轮独立模型评审。原快照保留。'
                      if zh else '**Errata applied:** This snapshot retains the SYSU correction and adds XMU N06-14 and BIT N14-L1-06 adjudications across all seven configurations. Fourteen task scores were recomputed, resolving five pending nodes. DeepSeek’s BIT match changes from same-department 60% to cross-department 30%. Other judgments are inherited. No candidates were rerun; these are scoped adjudications, not new independent model reviews. Earlier snapshots remain preserved.')
            content = content.replace('\n\n', '\n\n' + notice + '\n\n', 1)
            start = content.index('```sh\n'); stop = content.index('```', start + 6)
            command = '\n'.join(['```sh', 'python3 scripts/apply_department_errata.py \\',
                                 '  --erratum ' + erratum.relative_to(ROOT).as_posix() + ' \\',
                                 '  --out experiments/subset20-results-departments-NEW \\',
                                 '  --adjudication-out reviews/subset20-departments-NEW', ''])
            content = content[:start] + command + content[stop:]
            content = content.replace('可添加 `--png --font /path/to/font.ttc` 生成PNG。', '')
            content = content.replace('Add `--png --font /path/to/font.ttc` to generate PNGs.', '')
            path.write_text(content)
        export.put(stage / 'adjudication.json', metadata)
        export.put(stage / 'checksums.json', {'exporter_sha256': export.sha(Path(export.__file__)),
                                             'adjudicator_sha256': export.sha(Path(__file__)), 'files': export.tree_hashes(stage)})
        local.mkdir()
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
