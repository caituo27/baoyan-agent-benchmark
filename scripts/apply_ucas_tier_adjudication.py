#!/usr/bin/env python3
"""Resolve the approved Claude UCAS tier item without changing frozen inputs."""
import argparse
from copy import deepcopy
from datetime import datetime
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
        parser.add_argument('--' + name, required=True, type=Path)
    args = parser.parse_args()
    base, out, local, erratum = (getattr(args, n).resolve() for n in ('base', 'out', 'local', 'erratum'))
    export.require(all(p.is_relative_to(ROOT) for p in (base, out, local, erratum)), 'Paths outside repository')
    export.require(all(not p.exists() for p in (out, local, erratum)), 'Use fresh outputs')
    export.require(all(a != b and not a.is_relative_to(b) for a in (out, local, erratum)
                       for b in (out, local, erratum) if a is not b), 'Separate outputs')
    export.verify_hashes(base, export.read(base / 'checksums.json')['files'])
    data, audit = (export.read(base / n) for n in ('results.json', 'verification.json'))
    original = deepcopy(data)
    agent, tid, nid = 'claude-opus-5-5', 'TRY-F-02', 'TRY-F-02-R10-08'
    row = next(r for r in data['rows'] if (r['agent'], r['task_id']) == (agent, tid))
    record = next(r for r in audit['records'] if (r['agent'], r['task_id']) == (agent, tid))
    export.require(not row.get('adjudication_path'), 'Affected answer already adjudicated')
    source = export.safe_path(ROOT / 'reviews', record['review_source'])
    packet, prior = source / 'packets' / row['packet'], export.safe_path(source, row['execution_path'])
    export.verify_hashes(packet, record['packet_hashes'])
    export.verify_hashes(prior, record['review_files'])
    export.require(export.sha(prior / 'status.json') == record['status_sha256'], 'Original status changed')
    export.require(export.tree_hashes(source / 'frozen-code') == audit['scoring_code_sha256'], 'Scorer changed')
    sys.path.insert(0, str(source / 'frozen-code'))
    from benchmark.scoring import score
    task, rubric = (export.read(packet / n) for n in ('task.json', 'rubric.json'))
    answer, old_j = (packet / 'answer.md').read_text(), export.read(prior / 'judgment.json')
    old = score(task, rubric, answer, old_j)
    export.require(old == export.read(prior / 'score.json'), 'Original score replay differs')
    export.require(all(row[k] == old[k] for k in ('score', 'score_interval', 'pending_nodes')), 'Base row differs')
    export.require(old['pending_nodes'] == [nid], 'Unexpected pending scope')
    policy = '科研院所、境外和联合培养按实际培养与授位主体判断，不因没有985/211标签自动降级。'
    export.require(policy in (packet / 'scoring.md').read_text(), 'Required frozen exception missing')

    # Record same-task comparisons as consistency evidence, not additional votes.
    comparisons = []
    for rec in audit['records']:
        if rec['task_id'] != tid or rec['agent'] == agent:
            continue
        other_source = export.safe_path(ROOT / 'reviews', rec.get('review_source', data['review_source']))
        other = export.safe_path(other_source, rec['execution_path'])
        export.verify_hashes(other, rec['review_files'])
        j = export.read(other / 'judgment.json')
        matches = [s for s in j.get('tier_review', {}).get('schools', [])
                   if any(term in s.get('answer_quote', '') for term in ('中科院', '计算所', '软件所', '国科大', '中国科学院'))]
        if matches:
            comparisons.append({'agent': rec['agent'], 'judgment_path': (other / 'judgment.json').relative_to(ROOT).as_posix(),
                                'judgment_sha256': export.sha(other / 'judgment.json'), 'schools': matches})
    export.require(len(comparisons) == 5 and all(not s['downgraded'] for c in comparisons for s in c['schools']),
                   'Unexpected same-task comparison findings')
    judgment = deepcopy(old_j)
    tier = judgment['tier_review']
    school = next(s for s in tier['schools'] if s['school_key'] == 'ucas')
    export.require(school['downgraded'] is True and school['answer_quote'] in answer, 'Original UCAS finding changed')
    school.update(downgraded=False, reason='计算所、软件所属于国科大科教融合科研培养体系。冻结通则明确科研院所不因缺少985/211标签自动降级；原评审只在确认授位主体后重新套用标签排序，未提供实际培养路径降低的独立依据。同题五个其他配置的相同体系推荐均按不降级处理，统一采用此口径；同一主体只核一次。将其称为保底是否过于乐观属于其他适配性判断，不在层次项替代扣分。')
    tier['reason'] = '逐校记录保留；仅将国科大科研院所路径由标签推定降级修正为不降级。全题没有已证实的降级对象。'
    tier.pop('gold_issue', None)
    node = next(n for n in judgment['nodes'] if n['id'] == nid)
    node.update(grade=1, error_ids=[], reason='本科基准为武汉大学985。具名985院校同档，港三按境外主体处理，计算所与软件所按冻结通则的科研院所培养授位规则审阅，不能仅因国科大缺少985/211标签判降级。未发现独立的培养路径降级依据，统一同题其他配置口径，降级院校数为0，本项5/5分。零降级时扣分公式与three_level满档一致；结构性模板冲突仍作为规则问题留档，不再阻塞本答卷。其他节点与错误分配不变。')
    judgment.update(reviewer='Codex-assisted owner-approved UCAS tier adjudication', judge_version='ucas-tier-adjudication-v1')
    result = score(task, rubric, answer, judgment)
    export.require(result['score'] == 72.5 and not result['pending_nodes'], 'Unexpected resolved score')
    export.require([n for n in result['nodes'] if n['id'] != nid] == [n for n in old['nodes'] if n['id'] != nid], 'Unrelated score changed')
    export.require(result['error_impacts'] == old['error_impacts'], 'Error allocation changed')
    export.require(all(judgment[k] == old_j[k] for k in old_j if k not in ('nodes', 'tier_review', 'reviewer', 'judge_version')), 'Unrelated judgment field changed')
    export.require([n for n in judgment['nodes'] if n['id'] != nid] == [n for n in old_j['nodes'] if n['id'] != nid], 'Unrelated node judgment changed')
    row.update(score=result['score'], score_interval=result['score_interval'], pending_nodes=[], score_status=result['status'],
               adjudication_path=(local / tid / row['packet']).relative_to(ROOT).as_posix())
    row['deductions'] = [n for n in row['deductions'] if n['node'] != nid]
    data['pending'] = [n for n in data['pending'] if not (n['agent'] == agent and n['task_id'] == tid and n['node'] == nid)]
    tasks = {t['task_id']: t for t in data['tasks']}
    for summary in data['summary']:
        rows = [r for r in data['rows'] if r['agent'] == summary['agent']]
        summary.update(export.aggregate(rows, tasks, list(tasks)))
        summary['categories'] = {en: export.aggregate(rows, tasks, [t for t, info in tasks.items() if info['category'] == zh])
                                 for zh, en in export.CATEGORIES.items()}
    export.require(sum(a != b for a, b in zip(original['rows'], data['rows'])) == 1, 'Unrelated row changed')
    now = datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
    metadata = {'id': 'ucas-tier-20261010', 'date': now, 'kind': 'scoped_owner_approved_tier_adjudication',
                'authorization': '用户在核对科研院所例外及同题口径后明确批准：可以，更新吧。',
                'base_report': base.relative_to(ROOT).as_posix(), 'base_results_sha256': export.sha(base / 'results.json'),
                'base_verification_sha256': export.sha(base / 'verification.json'), 'agent': agent, 'task_id': tid, 'node': nid,
                'packet': row['packet'], 'original_review_source': record['review_source'], 'original_packet_hashes': record['packet_hashes'],
                'prior_judgment_path': (prior / 'judgment.json').relative_to(ROOT).as_posix(),
                'prior_judgment_sha256': export.sha(prior / 'judgment.json'), 'prior_score_sha256': export.sha(prior / 'score.json'),
                'policy': policy, 'school_judgment': school, 'node_judgment': node, 'consistency_comparisons': comparisons,
                'official_source': {'url': 'https://scce.ucas.ac.cn/index.php/zh-CN/xygk/xyjj',
                                    'scope': '计算所主承办、软件所参与共建国科大计算机学院；确认科教融合身份，不用于推定未来招生或学校强弱排序。'},
                'before': {k: old[k] for k in ('score', 'score_interval', 'pending_nodes')},
                'after': {k: result[k] for k in ('score', 'score_interval', 'pending_nodes')},
                'remaining_rule_issue': 'rubric仍同时声明three_level与逐校扣1分公式；本题零降级得满分，两者结果一致。未修改冻结rubric。',
                'candidate_reruns': 0, 'new_independent_model_reviews': 0, 'unchanged_answer_rows': len(data['rows']) - 1,
                'local_review_directory': local.relative_to(ROOT).as_posix(), 'report': out.relative_to(ROOT).as_posix(),
                'adjudicator_sha256': export.sha(Path(__file__))}
    for obj in (data, audit):
        obj['adjudication_history'] = obj.get('adjudication_history', []) + [obj['adjudication']]
        obj['adjudication'] = metadata
    data.update(generated_at=now, extension_rule='Resolve Claude UCAS tier misclassification under the frozen research-institute exception; inherit all other 179 rows unchanged.')
    audit.update(adjudicated_judgments=1, verification='Verified base snapshot hashes, original affected packet and review hashes, frozen scorer replay, and five same-task comparison judgments. Recomputed one derived answer; 179 answer rows unchanged. Earlier complete replays retained in provenance.')
    for path in (out, local, erratum): path.mkdir(parents=True)
    for name, obj in [('task.json', task), ('rubric.json', rubric)]: export.put(local / tid / name, obj)
    for name, obj in [('judgment.json', judgment), ('score.json', result)]: export.put(local / tid / row['packet'] / name, obj)
    export.put(local / 'receipt.json', metadata)
    export.put(local / 'checksums.json', {'files': export.tree_hashes(local)})
    export.put(erratum / 'decision.json', metadata)
    (erratum / 'README.md').write_text('# 国科大科研院所层次裁决\n\n用户批准按冻结通则的科研院所规则统一口径：Claude在TRY-F-02推荐计算所、软件所不构成已证实的层次降级，R10-08改为5/5分。该题72.5分、20题均分73.1435；原始答卷、初评与旧快照保留。其他179份答卷成绩继承不变。\n\n本次只更正一项评审判断，不修改rubric、不重跑答卷、不计为新的独立模型评审。逐分公式与three_level的结构冲突仍留档，零降级时两者均为满分。\n\n[裁决与来源](decision.json) · [更新后的报告](../../../' + out.relative_to(ROOT).as_posix() + '/README.zh-CN.md)\n')
    export.put(erratum / 'checksums.json', {'files': export.tree_hashes(erratum)})
    export.write_tables(out, data, audit)
    export.charts(out, data, None)
    for zh in (False, True):
        export.report(out, data, audit, False, zh=zh)
        p = out / ('README.zh-CN.md' if zh else 'README.md')
        body = p.read_text()
        notice = ('**科研院所层次修正：** 经用户批准，Claude对计算所、软件所的推荐按冻结通则及同题一致口径判不降级；TRY-F-02-R10-08为5/5分，该题72.5分，20题均分73.14，Claude不再有待核项。继承此前南理工资格裁决及院系勘误，其余179份答卷成绩不变。原始初评保留；没有新增模型调用。' if zh else '**Research-institute tier correction:** Owner-approved application of the frozen research-institute exception removes the unsupported UCAS downgrade in Claude TRY-F-02. R10-08 receives 5/5; the task scores 72.5 and the Dev20 mean is 73.14, with no Claude items pending. Prior qualification and department adjudications are retained; all other 179 answer rows are unchanged. Original reviews remain preserved; no new model calls were made.')
        body = body.replace('\n\n', '\n\n' + notice + '\n\n', 1)
        start = body.index('```sh\n'); end = body.index('```', start + 6)
        command = f'```sh\npython3 scripts/apply_ucas_tier_adjudication.py --base {base.relative_to(ROOT)} --out experiments/subset20-results-ucas-NEW --local reviews/subset20-ucas-NEW --erratum release/errata/ucas-NEW\n'
        body = body[:start] + command + body[end:]
        p.write_text(body.rstrip() + '\n')
    export.put(out / 'adjudication.json', metadata)
    export.put(out / 'checksums.json', {'exporter_sha256': export.sha(Path(export.__file__)), 'adjudicator_sha256': export.sha(Path(__file__)), 'files': export.tree_hashes(out)})
    print({'report': str(out), 'score': result['score'], 'numeric': sum(s['scored'] for s in data['summary']), 'pending': len(data['pending'])})


if __name__ == '__main__':
    main()
