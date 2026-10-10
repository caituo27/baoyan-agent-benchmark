#!/usr/bin/env python3
"""Apply the owner's half-credit language ruling as an explicit score overlay.

The frozen scorer and candidate-validity findings stay intact. This is not a
new native model review or a claim that unresolved admissions facts are known.
"""
import argparse
from copy import deepcopy
from datetime import datetime
from fractions import Fraction
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import export_review_results as export


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('base', 'out', 'local', 'erratum'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    base, out, local, erratum = (getattr(args, n).resolve() for n in ('base', 'out', 'local', 'erratum'))
    export.require(all(p.is_relative_to(ROOT) for p in (base, out, local, erratum)), 'Paths outside repository')
    export.require(all(not p.exists() for p in (out, local, erratum)), 'Use fresh outputs')
    export.require(all(not a.is_relative_to(b) for i, a in enumerate((out, local, erratum))
                       for j, b in enumerate((out, local, erratum)) if i != j), 'Separate outputs')
    export.verify_hashes(base, export.read(base / 'checksums.json')['files'])
    data, audit = (export.read(base / name) for name in ('results.json', 'verification.json'))
    original = deepcopy(data)
    agent, tid, nid = 'deepseek-v4-1-flash', 'BY-E-REPLAN', 'BY-E-REPLAN-R10-05'
    row = next(r for r in data['rows'] if (r['agent'], r['task_id']) == (agent, tid))
    export.require('score_adjudication_path' not in row, 'Score already overlaid')
    prior = export.safe_path(ROOT, row['adjudication_path'])
    boundary = next(p for p in prior.parents if p.is_relative_to(ROOT / 'reviews') and (p / 'checksums.json').is_file())
    export.verify_hashes(boundary, export.read(boundary / 'checksums.json')['files'])
    record = next(r for r in audit['records'] if (r['agent'], r['task_id']) == (agent, tid))
    source = export.safe_path(ROOT / 'reviews', record.get('review_source', data['review_source']))
    packet = source / 'packets' / row['packet']
    export.verify_hashes(packet, record['packet_hashes'])
    export.require(export.tree_hashes(source / 'frozen-code') == audit['scoring_code_sha256'], 'Frozen scorer changed')
    sys.path.insert(0, str(source / 'frozen-code'))
    from benchmark.scoring import score
    task, rubric = (export.read(prior.parent / name) for name in ('task.json', 'rubric.json'))
    judgment = export.read(prior / 'judgment.json')
    old = score(task, rubric, (packet / 'answer.md').read_text(), judgment)
    export.require(old == export.read(prior / 'score.json'), 'Prior frozen replay differs')
    export.require(all(row[k] == old[k] for k in ('score', 'score_interval', 'pending_nodes')), 'Base row differs')
    export.require(old['pending_nodes'] == [nid] and old['quantity_status'] == 'not_applicable', 'Unexpected pending scope')
    rule = next(n for n in rubric['nodes'] if n['id'] == nid)
    node = next(n for n in judgment['nodes'] if n['id'] == nid)
    error = next(e for e in judgment['errors'] if e['id'] == 'ERR-L1')
    export.require(rule['points'] == 10 and node['grade'] == 'pending' and node['error_ids'] == ['ERR-L1'], 'Known error binding changed')
    export.require(error['answer_quote'] in (packet / 'answer.md').read_text() and error['evidence'], 'Missing error evidence')
    pending_candidates = [c for c in judgment['recommendation_review'] if c['validity'] == 'pending']
    export.require({c['canonical_candidate_key'] for c in pending_candidates} == {'hkbu-msc-daai'}, 'Unresolved fact scope changed')
    reason = '按用户最终明确选择“未证实说法不给分，语言项保留5分”：已有具体语言考试、首考复考、出分与送分安排，保留这些正确内容的半分；NUS计算硕士托福门槛85的已确认错误（官方为90）使本项不能满分。HKBU DAAI在2026周期是否认可六级450仍未证实，该说法不取得分数，也不据此声称已证实错误；此未决事实不改变已有正确内容与确定错误并存的半分档位。R10-05为5/10分，其他项不变。'
    # Explicit owner score adjudication, after replaying the untouched frozen
    # result. Do not re-label pending candidates or weaken the frozen validator.
    result = deepcopy(old)
    scored_node = next(n for n in result['nodes'] if n['id'] == nid)
    scored_node.update(grade=0.5, points=5.0)
    total = sum(Fraction(str(n['points'])) for n in result['nodes'])
    export.require(total == Fraction(155, 2), 'Unexpected arithmetic')
    result.update(score=float(total), diagnostic_score=float(total), status='scored_owner_adjudicated',
                  confirmed_points=float(total), score_interval=[float(total), float(total)], pending_nodes=[],
                  adjudication_method='owner_node_score_overlay.1')
    result['error_impacts']['ERR-L1'] = [nid]
    result['confirmed_component_points']['quality'] = float(total)
    export.require(result['recommendation_review'] == old['recommendation_review'], 'Candidate facts changed')
    export.require(result['errors'] == old['errors'], 'Errors changed')
    export.require([n for n in result['nodes'] if n['id'] != nid] == [n for n in old['nodes'] if n['id'] != nid], 'Unrelated nodes changed')
    export.require(all(result['error_impacts'].get(k) == v for k, v in old['error_impacts'].items()), 'Existing error moved')
    now = datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
    fact = {'id': 'HKBU-DAAI-CET6-2026', 'agent': agent, 'task_id': tid,
            'status': 'unverified', 'claim': 'HKBU DAAI在2026入学申请周期接受六级450作为英语资格。',
            'score_blocking': False, 'reason': '当前官方页面只列IELTS6.0、TOEFL74或其他等效资格；AIDM的六级450条款不能移植到DAAI。未证明2026历史接受或拒绝。本项依据正确具体语言安排与独立确认的NUS门槛错误裁决为半分；未证实说法不给分，事实未决不改变档位。',
            'source': 'https://ar.hkbu.edu.hk/tpg-admissions/programmes/master-of-science-msc-in-data-analytics-and-artificial-intelligence',
            'candidate_records': [c['answer_item_id'] for c in pending_candidates]}
    metadata = {'id': 'deepseek-language-half-20261010', 'date': now, 'kind': 'owner_node_score_overlay.1',
                'authorization': ['可以，更新吧', '没有查到的不算分', '如果是错误的就是误导，不算分', '最终明确选择：未证实说法不给分，语言项保留5分'],
                'scope': 'DeepSeek BY-E-REPLAN-R10-05 only; half credit for concrete correct language preparation despite the confirmed threshold error; unverified claims earn no credit; other nodes and candidate facts unchanged.',
                'base_report': base.relative_to(ROOT).as_posix(), 'base_results_sha256': export.sha(base / 'results.json'),
                'base_verification_sha256': export.sha(base / 'verification.json'),
                'agent': agent, 'task_id': tid, 'packet': row['packet'], 'node': nid, 'grade': 0.5, 'points': 5, 'max_points': 10,
                'reason': reason, 'confirmed_error': error, 'unresolved_fact': fact,
                'prior_judgment_path': (prior / 'judgment.json').relative_to(ROOT).as_posix(),
                'prior_judgment_sha256': export.sha(prior / 'judgment.json'), 'prior_score_sha256': export.sha(prior / 'score.json'),
                'original_packet_hashes': record['packet_hashes'], 'before': {k: old[k] for k in ('score', 'score_interval', 'pending_nodes')},
                'after': {k: result[k] for k in ('score', 'score_interval', 'pending_nodes')},
                'frozen_scorer_replay': 'Prior result replayed unchanged. Final score is an explicit owner-approved overlay, not direct frozen-scorer output.',
                'candidate_reruns': 0, 'new_independent_model_reviews': 0, 'unchanged_answer_rows': len(data['rows']) - 1,
                'local_review_directory': local.relative_to(ROOT).as_posix(), 'report': out.relative_to(ROOT).as_posix(),
                'adjudicator_sha256': export.sha(Path(__file__))}
    result['score_adjudication'] = metadata
    row.update(score=result['score'], score_interval=result['score_interval'], pending_nodes=[], score_status=result['status'],
               score_adjudication_path=(local / tid / row['packet']).relative_to(ROOT).as_posix())
    row['deductions'] = [d for d in row['deductions'] if d['node'] != nid] + [{'node': nid, 'points': 5, 'max_points': 10, 'reason': reason}]
    row['deductions'].sort(key=lambda n: n['node'])
    data['pending'] = [p for p in data['pending'] if not (p['agent'] == agent and p['task_id'] == tid and p['node'] == nid)]
    data['unresolved_facts'] = data.get('unresolved_facts', []) + [fact]
    tasks = {t['task_id']: t for t in data['tasks']}
    for summary in data['summary']:
        rows = [r for r in data['rows'] if r['agent'] == summary['agent']]
        summary.update(export.aggregate(rows, tasks, list(tasks)))
        summary['categories'] = {en: export.aggregate(rows, tasks, [t for t, info in tasks.items() if info['category'] == zh])
                                 for zh, en in export.CATEGORIES.items()}
    export.require(len(original['rows']) == len(data['rows']) == 180 and sum(a != b for a, b in zip(original['rows'], data['rows'])) == 1, 'Unrelated answer changed')
    for obj in (data, audit):
        obj['adjudication_history'] = obj.get('adjudication_history', []) + [obj['adjudication']]
        obj['adjudication'] = metadata
    data.update(generated_at=now, extension_rule='Owner-approved half credit for concrete correct language preparation despite the confirmed threshold error; unverified claims earn no credit; 179 other answer rows unchanged. One factual uncertainty remains separately documented without blocking the adjudicated score.')
    audit.update(adjudicated_judgments=1, verification='Verified base and inherited evidence hashes; replayed the affected prior result using the unchanged frozen scorer. Applied the owner-approved 5/10 score overlay with exact arithmetic; candidate facts and 179 other answer rows unchanged. Final derived score is not direct frozen-scorer output.')
    for p in (out, local, erratum): p.mkdir(parents=True)
    export.put(local / tid / row['packet'] / 'score.json', result)
    export.put(local / tid / row['packet'] / 'decision.json', metadata)
    export.put(local / 'checksums.json', {'files': export.tree_hashes(local)})
    export.put(erratum / 'decision.json', metadata)
    (erratum / 'README.md').write_text('# DeepSeek语言项半分裁决\n\n' + reason + '\n\n本题77.5分，20题均分69.2335（显示69.23）。用户最终明确选择保留语言项5分，取代先前对整项零分的解释。冻结评分器、原始答卷及评审均保留；不将未查明事实伪造为已核实。结果采用显式裁决叠加，不能称为原冻结评分器直接输出。\n\n[裁决与证据](decision.json) · [当前报告](../../../' + out.relative_to(ROOT).as_posix() + '/README.zh-CN.md)\n')
    export.put(erratum / 'checksums.json', {'files': export.tree_hashes(erratum)})
    export.write_tables(out, data, audit)
    export.charts(out, data, None)
    for zh in (False, True):
        export.report(out, data, audit, False, zh=zh)
        p = out / ('README.zh-CN.md' if zh else 'README.md'); body = p.read_text()
        notice = ('**语言项裁决：** 按用户最终“未证实说法不给分，语言项保留5分”的指示，DeepSeek的BY-E-REPLAN-R10-05按已有正确安排及确定语言门槛错误记5/10分；整题77.5分、20题均分69.23。其他179份答卷成绩不变。九配置180题均已有数值评分，但DAAI六级资格仍未证实，单列为不阻塞成绩的事实问题。此次是显式负责人评分裁决，不是原冻结评分器直接输出；原始评审和评分规则保留。' if zh else '**Language-item adjudication:** Under the owner’s final clarification, unverified claims earn no credit while concrete correct language preparation retains half credit: DeepSeek BY-E-REPLAN-R10-05 receives 5/10 with the confirmed NUS threshold error preventing full credit. The task scores 77.5 and Dev20 mean is 69.23; 179 other answer rows are unchanged. All 180 answers now have numeric scores. HKBU DAAI CET-6 eligibility remains unverified and separately documented. This is an explicit owner score overlay, not direct frozen-scorer output; original reviews and rules are preserved.')
        body = body.replace('\n\n', '\n\n' + notice + '\n\n', 1)
        start = body.index('```sh\n'); end = body.index('```', start + 6)
        command = f'```sh\npython3 scripts/apply_language_score_adjudication.py --base {base.relative_to(ROOT)} --out experiments/subset20-results-language-NEW --local reviews/subset20-language-NEW --erratum release/errata/language-NEW\n'
        body = body[:start] + command + body[end:]
        body = body.replace('已校验并复算180份评审记录', '保留180份原评审复算记录；本次另应用一项负责人评分裁决').replace('Recomputed and verified 180 reviews;', 'Retained replay records for 180 original reviews; this snapshot additionally applies one owner score adjudication;')
        p.write_text(body.rstrip() + '\n')
    (out / 'pending-review.md').write_text('# 待核状态\n\n当前没有阻塞数值评分的待核项，180份答卷均有确定成绩。\n\n## 仍未证实的事实\n\n' + fact['claim'] + '\n\n' + fact['reason'] + '\n\n[官方页面](' + fact['source'] + ') · [评分裁决](adjudication.json)\n')
    export.put(out / 'unresolved-facts.json', [fact])
    export.put(out / 'adjudication.json', metadata)
    export.put(out / 'checksums.json', {'exporter_sha256': export.sha(Path(export.__file__)), 'adjudicator_sha256': export.sha(Path(__file__)), 'files': export.tree_hashes(out)})
    print({'report': str(out), 'task_score': result['score'], 'numeric': sum(s['scored'] for s in data['summary']), 'pending': len(data['pending'])})


if __name__ == '__main__':
    main()
