#!/usr/bin/env python3
"""Replay the frozen dev20 snapshot and apply the owner-approved N06-10 erratum.

This is a scoped adjudication, not a new independent model review. Original
answers, judgments, and reports are read-only. Both output directories must be new.
"""
import argparse
from copy import deepcopy
from datetime import datetime
from pathlib import Path
import sys
import tempfile
from zoneinfo import ZoneInfo

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import export_review_results as export

ERRATUM = ROOT / 'release/errata/N06-10-sysu-20261010'
REFERENCE = 'N06-10'
TASK = 'N06-03'
# One representative per canonical candidate; repeated mentions do not add credit.
MATCHES = {
    'gpt-6-astra': [('A03', 'same_department')],
    'gpt-6-1-sol': [('A03', 'exact')],
    'deepseek-v4-1-flash': [('C08', 'exact'), ('C02', 'same_department')],
    'antigravity-gemini-3-1-pro-high': [('A01', 'same_department')],
    'antigravity-gemini-3-8-flash-high': [],
    'qwen3-8-max-0902': [('A004', 'exact'), ('A003', 'same_department')],
    'kimi-k3': [('A09', 'exact')],
}
REASONS = {
    'exact': '负责人已确认广州、珠海中文系为同一参考项的备选单位。此候选明确给出其中一个中文系的中国语言文学学硕或所属方向，继承原评审已核实的有效性和条件路径，按完整匹配计分。',
    'same_department': '此候选为广州中国语言文学系国际中文教育专硕；同系中文学术培养与国际中文教育培养关系成立，且原评审已确认具体项目和条件路径有效。按同院系相近专业60%匹配，不等同中国语言文学学硕。',
}
MISS_REASON = ('复核后保留缺项：勘误允许广州或珠海中文系的明确学硕项目命中一次，'
               '但未取消原有具体申请路径要求。该答卷把两个独立院系和多个方向合并在一栏，'
               '全文未明确院系与专业的对应申报路径；不能替答卷拆出未明确的候选。'
               '因此N06-10仍为miss；原因是路径不明确，已不再依据旧称“文学院”判断。')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-report', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--adjudication-out', type=Path, required=True)
    args = parser.parse_args()
    base, out, local = (p.resolve() for p in (args.base_report, args.out, args.adjudication_out))
    export.require(not out.exists() and not local.exists(), 'Use new output directories')
    export.require(all(p.is_relative_to(ROOT) for p in (base, out, local)), 'Outputs must be in repository')
    export.require(not out.is_relative_to(local) and not local.is_relative_to(out), 'Separate outputs')
    export.verify_hashes(base, export.read(base / 'checksums.json')['files'])
    original = export.read(base / 'results.json')
    data = deepcopy(original)
    audit = export.read(base / 'verification.json')
    source = ROOT / 'reviews' / data['review_source']
    export.require(export.tree_hashes(source / 'frozen-code') == audit['scoring_code_sha256'], 'Scorer changed')
    export.verify_hashes(source, audit['scope_bindings'])
    sys.path.insert(0, str(source / 'frozen-code'))
    from benchmark.core import digest, input_hash
    from benchmark.scoring import score

    # Replay every original score, not just the seven amended tasks.
    originals = {}
    for record in audit['records']:
        packet = source / 'packets' / record['packet']
        execution = source / record['execution_path']
        export.verify_hashes(packet, record['packet_hashes'])
        export.verify_hashes(execution, record['review_files'])
        export.require(export.sha(execution / 'status.json') == record['status_sha256'], 'Status changed')
        task, rubric = (export.read(packet / name) for name in ('task.json', 'rubric.json'))
        answer = (packet / 'answer.md').read_text()
        judgment = export.read(execution / 'judgment.json')
        result = score(task, rubric, answer, judgment)
        export.require(result == export.read(execution / 'score.json'), 'Original scorer replay differs')
        row = next(r for r in data['rows'] if (r['agent'], r['task_id']) == (record['agent'], record['task_id']))
        export.require(all(row[k] == result[k] for k in ('score', 'score_interval', 'pending_nodes')), 'Report differs from score')
        originals[record['agent'], record['task_id']] = (record, task, rubric, answer, judgment, result)
    export.require(len(originals) == len(data['rows']) == 140, 'Expected seven complete 20-task reviews')

    decision = export.read(ERRATUM / 'decision.json')
    task, rubric = (export.read(ERRATUM / name) for name in ('task.json', 'rubric.json'))
    export.require(digest(task) == decision['corrected_fingerprints']['task'] and
                   digest(rubric) == decision['corrected_fingerprints']['rubric'], 'Erratum changed')
    export.require(input_hash(task) == decision['candidate_input_sha256'], 'Candidate input changed')
    export.require(set(MATCHES) == {r['agent'] for r in data['summary']}, 'Apply to every configuration')
    now = datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
    changes, files = [], {}
    for row in data['rows']:
        if row['task_id'] != TASK:
            continue
        agent = row['agent']
        record, old_task, old_rubric, answer, old_judgment, old_score = originals[agent, TASK]
        export.require(digest(old_task) == decision['original_fingerprints']['task'] and
                       digest(old_rubric) == decision['original_fingerprints']['rubric'], 'Wrong baseline')
        judgment = deepcopy(old_judgment)
        coverage = next(n for n in judgment['coverage'] if n['id'] == REFERENCE)
        old_coverage = deepcopy(coverage)
        candidates = {c['answer_item_id']: c for c in judgment['recommendation_review']}
        matches = []
        for candidate_id, level in MATCHES[agent]:
            candidate = candidates[candidate_id]
            export.require(candidate['school_key'] == '中山大学' and candidate['validity'] == 'valid'
                           and candidate['treatment'] in ('direct', 'conditional'), 'Invalid candidate')
            matches.append({'answer_item_id': candidate_id, 'match_level': level,
                            'answer_quote': candidate['answer_quote'], 'reason': REASONS[level],
                            'relation_evidence': [
                                {'source': 'release/errata/N06-10-sysu-20261010/decision.json',
                                 'applicable_cycle': '2026年推免申请季；2026-10-10负责人批准勘误',
                                 'scope': '两个招生单位是本参考项的备选；参考项总计一次。'},
                                {'source': 'https://www.sysu.edu.cn/xq/xsyg/xkda2.htm',
                                 'applicable_cycle': '2026年申请季院系与学科身份；非实时名额证明',
                                 'scope': '两个中文系均有中国语言文学学科；本次不重新审计全部招生事实。'},
                                {'source': 'https://chinese.sysu.edu.cn/node/71',
                                 'applicable_cycle': '2026年申请季招生单位和专业关系',
                                 'scope': '广州中文系的中国语言文学学位培养及国际中文教育硕士点。'},
                                {'source': (source / record['execution_path'] / 'evidence.json').relative_to(ROOT).as_posix(),
                                 'applicable_cycle': '原评审适用的2026年推免申请季',
                                 'scope': '继承原候选有效性及申请条件核验；本次仅重判参考匹配关系。'}]})
        coverage.clear()
        coverage.update(id=REFERENCE, status='hit' if matches else 'miss', matches=matches,
                        matched_answer_item_id=None, error_ids=[],
                        answer_quote=old_coverage['answer_quote'],
                        reason=('统一勘误复核：' + ' '.join(dict.fromkeys(m['reason'] for m in matches))
                                + '同一候选重复提及去重，本项按最佳关系最多计一次。') if matches else MISS_REASON)
        judgment.update(task_sha256=digest(task), rubric_sha256=digest(rubric),
                        reviewer='Codex-assisted owner-approved N06-10 erratum adjudication',
                        judge_version='N06-10-sysu-adjudication-v1')
        result = score(task, rubric, answer, judgment)
        # The correction must not alter any other scoring node or error impact.
        export.require([n for n in result['nodes'] if n['id'] != REFERENCE] ==
                       [n for n in old_score['nodes'] if n['id'] != REFERENCE], 'Unrelated score changed')
        export.require(result['error_impacts'] == old_score['error_impacts'], 'Error impacts changed')
        export.require(result['pending_nodes'] == [n for n in old_score['pending_nodes'] if n != REFERENCE],
                       'Unrelated pending changed')
        after_node = next(n for n in result['nodes'] if n['id'] == REFERENCE)
        row.update(score=result['score'], score_interval=result['score_interval'],
                   pending_nodes=result['pending_nodes'], score_status=result['status'],
                   adjudication_path=(local / record['packet']).relative_to(ROOT).as_posix())
        row['deductions'] = [n for n in row['deductions'] if n['node'] != REFERENCE]
        if after_node['points'] < 4.375 - .001:
            row['deductions'].append({'node': REFERENCE, 'points': after_node['points'],
                                      'max_points': 4.375, 'reason': coverage['reason']})
        row['deductions'].sort(key=lambda n: n['node'])
        changes.append({'agent': agent, 'name': row['name'], 'packet': record['packet'],
                        'original_judgment_sha256': record['review_files']['judgment.json'],
                        'original_evidence_sha256': export.sha(source / record['execution_path'] / 'evidence.json'),
                        'original_reviewer': old_judgment['reviewer'], 'original_judge_version': old_judgment['judge_version'],
                        'before': {'score': old_score['score'], 'score_interval': old_score['score_interval'],
                                   'coverage': old_coverage},
                        'after': {'score': result['score'], 'score_interval': result['score_interval'],
                                  'coverage': coverage, 'allocated_node': after_node},
                        'judgment_sha256': digest(judgment), 'score_sha256': digest(result)})
        files[record['packet']] = (judgment, result)

    data['pending'] = [n for n in data['pending'] if not (n['task_id'] == TASK and n['node'] == REFERENCE)]
    for pending in data['pending']:
        pending['score_interval'] = next(r['score_interval'] for r in data['rows']
                                        if (r['agent'], r['task_id']) == (pending['agent'], pending['task_id']))
    tasks = {t['task_id']: t for t in data['tasks']}
    for summary in data['summary']:
        part = [r for r in data['rows'] if r['agent'] == summary['agent']]
        summary.update(export.aggregate(part, tasks, list(tasks)))
        summary['categories'] = {en: export.aggregate(part, tasks, [tid for tid, t in tasks.items() if t['category'] == zh])
                                 for zh, en in export.CATEGORIES.items()}
    metadata = {'id': decision['id'], 'date': now, 'kind': 'scoped_owner_approved_adjudication',
                'base_report': base.relative_to(ROOT).as_posix(), 'base_results_sha256': export.sha(base / 'results.json'),
                'decision_sha256': export.sha(ERRATUM / 'decision.json'),
                'scoring_revision': rubric['scoring_revision'], 'candidate_reruns': 0,
                'new_independent_model_reviews': 0, 'configurations_rechecked': 7,
                'local_review_directory': local.relative_to(ROOT).as_posix(), 'changes': changes}
    data.update(generated_at=now, adjudication=metadata,
                extension_rule='Original snapshot retained; this derived snapshot applies only the documented N06-10 erratum.')
    audit.update(adjudication=metadata, adjudicated_judgments=7,
                 verification='All 140 original scores replayed with the frozen scorer; original records below remain provenance. Seven derived judgments recomputed under the owner-approved N06-10 erratum; other nodes and candidate inputs unchanged.')
    out.parent.mkdir(parents=True, exist_ok=True)
    local.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.sysu-report-', dir=out.parent) as tmp:
        stage = Path(tmp) / 'report'; stage.mkdir()
        export.write_tables(stage, data, audit)
        export.charts(stage, data, None)
        for zh in (False, True):
            export.report(stage, data, audit, False, zh=zh)
            path = stage / ('README.zh-CN.md' if zh else 'README.md')
            content = path.read_text()
            notice = ('**修订说明：** 已对七个配置统一应用中山大学N06-10勘误，解决5个待核节点。140份原评分均经冻结评分器复算，7份派生评审重算；其余判断继承原评审。这是负责人批准口径后的局部裁决，未重新运行答题模型，也不是新一轮独立模型评审。原快照保留。'
                      if zh else '**Erratum applied:** All seven configurations were rechecked for SYSU N06-10, resolving five pending nodes. All 140 original scores were replayed, and seven derived judgments recomputed. Other judgments are inherited. This scoped adjudication follows the owner-approved correction; it is neither a candidate rerun nor a new independent model review. The original snapshot is preserved.')
            content = content.replace('\n\n', '\n\n' + notice + '\n\n', 1)
            start = content.index('```sh\n')
            stop = content.index('```', start + 6)
            command = (f'```sh\npython3 scripts/apply_sysu_erratum.py \\\n  --base-report {base.relative_to(ROOT).as_posix()} \\\n  --out experiments/subset20-results-sysu-NEW \\\n  --adjudication-out reviews/subset20-sysu-NEW\n')
            content = content[:start] + command + content[stop:]
            content = content.replace('可添加 `--png --font /path/to/font.ttc` 生成PNG。', '')
            content = content.replace('Add `--png --font /path/to/font.ttc` to generate PNGs.', '')
            path.write_text(content)
        export.put(stage / 'adjudication.json', metadata)
        export.put(stage / 'checksums.json', {'exporter_sha256': export.sha(Path(export.__file__)),
                                             'adjudicator_sha256': export.sha(Path(__file__)), 'files': export.tree_hashes(stage)})
        local.mkdir()
        export.put(local / 'task.json', task); export.put(local / 'rubric.json', rubric)
        for packet, (judgment, result) in files.items():
            export.put(local / packet / 'judgment.json', judgment)
            export.put(local / packet / 'score.json', result)
        export.put(local / 'receipt.json', metadata)
        export.put(local / 'checksums.json', {'files': export.tree_hashes(local)})
        stage.rename(out)
    print(__import__('json').dumps({'out': str(out), 'numeric': sum(r['scored'] for r in data['summary']),
          'pending_answers': sum(r['pending'] for r in data['summary']), 'pending_nodes': len(data['pending']),
          'summary': [{k: r[k] for k in ('name', 'mean', 'score_bounds', 'scored', 'pending')} for r in data['summary']]}, ensure_ascii=False))


if __name__ == '__main__':
    main()
