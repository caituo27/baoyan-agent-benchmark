#!/usr/bin/env python3
"""Resolve the NJUST qualification item with the original rubric and scorer."""
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
    parser.add_argument('--base', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--local', type=Path, required=True)
    args = parser.parse_args()
    base, out, local = (p.resolve() for p in (args.base, args.out, args.local))
    export.require(all(p.is_relative_to(ROOT) for p in (base,out,local)), 'Paths outside repository')
    export.require(not out.exists() and not local.exists(), 'Use fresh output directories')
    export.verify_hashes(base, export.read(base/'checksums.json')['files'])
    data, audit = export.read(base/'results.json'), export.read(base/'verification.json')
    original = deepcopy(data)
    row = next(r for r in data['rows'] if r['agent']=='antigravity-gemini-3-8-flash-high' and r['task_id']=='N10-01')
    prior = export.safe_path(ROOT, row['adjudication_path'])
    boundary = next(p for p in prior.parents if p.is_relative_to(ROOT/'reviews') and (p/'checksums.json').is_file())
    export.verify_hashes(boundary, export.read(boundary/'checksums.json')['files'])
    source = ROOT/'reviews'/data['review_source']
    export.require(export.tree_hashes(source/'frozen-code')==audit['scoring_code_sha256'], 'Frozen scorer changed')
    sys.path.insert(0,str(source/'frozen-code'))
    from benchmark.core import digest
    from benchmark.scoring import score
    task, rubric = (export.read(prior.parent/n) for n in ('task.json','rubric.json'))
    packet = source/'packets'/row['packet']
    answer = (packet/'answer.md').read_text()
    judgment = export.read(prior/'judgment.json')
    old = score(task,rubric,answer,judgment)
    export.require(old==export.read(prior/'score.json'), 'Prior score does not replay')
    export.require(all(row[k]==old[k] for k in ('score','score_interval','pending_nodes')), 'Base row mismatch')
    quote='除了常规的普通学术/专业推免指标外，南理工拥有众多特殊的专项推免通道，对排名要求通常放宽至前 30%～50%：'
    export.require(quote in answer,'Exact error quote missing')
    evidence=export.read(ROOT/'release/errata/pending-evidence-20261010/decision.json')['sources']['NJUST']
    error={'id':'E6','answer_quote':quote,'reason':'将具有限定对象、成果审核及单独实施条件的特殊推荐计划，概括为排名通常放宽至前30%～50%的政策性兜底通道，错误地泛化适用范围。2027校规普通推荐前40%；特殊学术专长前50%另须特定成果与审核答辩，其他专项单独组织。不是因未附来源扣分，也不声称全部计划不存在；只计入T1。','evidence':[evidence]}
    judgment['errors'].append(error)
    for candidate in judgment['recommendation_review']:
        if candidate['answer_item_id'] in ('A001','A002','A004'):
            candidate.update(validity='invalid',error_ids=['E6'],reason='作为答卷所称普遍排名放宽、可供该学生兜底的资格路径不成立。错误在于将部分真实专项泛化为本人的可用推荐资格，而非断言相关机构或所有专项不存在；未落实限定对象与必要条件。其余名称是否正式等价不会改变这条建议的错误或T1半分档位。',affected_node_ids=['N10-01-T1'])
    node=next(n for n in judgment['nodes'] if n['id']=='N10-01-T1')
    node.update(grade=.5,error_ids=['E4','E6'],reason='正确把校内资格列为首务，并安排核对院系细则、综合分、成果位次及截止时间，已有实质正确内容，保留半分。将特殊通道概括为排名通常放宽至前30%～50%的兜底路径，是适用条件的错误泛化（E6）；另有不符合当届校规的权重概括（E4）及无依据名额/分差判断，不能满分。特殊学术专长前50%另需特定成果及审核答辩，其他计划单独组织；个别名称未确认不改变已有正确内容与明确错误并存的半分结论，因此解除pending。错误只在T1计分，不追加处罚其他节点。')
    node5=next(n for n in judgment['nodes'] if n['id']=='N10-01-T5')
    node5['reason']=node5['reason'].replace('特殊通道资格仍仅在T1待核；即使该资格争议解决，本项已有正确方案及独立缺项仍固定为半分，不把同一争议重复悬挂。','专项资格泛化错误已在T1处理；本项基于独立缺项保留半分，不重复扣分。')
    judgment.update(reviewer='Codex-assisted owner-requested qualification adjudication',judge_version='njust-qualification-adjudication-v1')
    result=score(task,rubric,answer,judgment)
    export.require(result['score']==64.5 and not result['pending_nodes'],'Unexpected resolved score')
    export.require([n for n in result['nodes'] if n['id']!='N10-01-T1']==[n for n in old['nodes'] if n['id']!='N10-01-T1'],'Unrelated node changed')
    export.require(all(result['error_impacts'].get(k)==v for k,v in old['error_impacts'].items()),'Existing error moved')
    row.update(score=result['score'],score_interval=result['score_interval'],pending_nodes=[],score_status=result['status'],adjudication_path=local.relative_to(ROOT).as_posix()+'/N10-01/'+row['packet'])
    row['deductions'].append({'node':'N10-01-T1','points':12.5,'max_points':25,'reason':node['reason']})
    for deduction in row['deductions']:
        if deduction['node']=='N10-01-T5':deduction['reason']=node5['reason']
    row['deductions'].sort(key=lambda n:n['node'])
    data['pending']=[n for n in data['pending'] if not(n['agent']==row['agent'] and n['task_id']=='N10-01')]
    tasks={t['task_id']:t for t in data['tasks']}
    for summary in data['summary']:
        part=[r for r in data['rows'] if r['agent']==summary['agent']]
        summary.update(export.aggregate(part,tasks,list(tasks)))
        summary['categories']={en:export.aggregate(part,tasks,[tid for tid,t in tasks.items() if t['category']==zh]) for zh,en in export.CATEGORIES.items()}
    changes=[(a,b) for a,b in zip(original['rows'],data['rows']) if a!=b]
    export.require(len(changes)==1,'Unrelated answer changed')
    now=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
    metadata={'id':'njust-qualification-20261010','date':now,'kind':'scoped_owner_requested_evidence_adjudication',
              'base_report':base.relative_to(ROOT).as_posix(),'base_results_sha256':export.sha(base/'results.json'),
              'authorization':'用户指出普遍排名放宽属于错误，并要求重新修改。',
              'agent':row['agent'],'task_id':'N10-01','packet':row['packet'],'node':'N10-01-T1',
              'prior_judgment_path':prior.relative_to(ROOT).as_posix(),'prior_judgment_sha256':export.sha(prior/'judgment.json'),
              'task_sha256':digest(task),'rubric_sha256':digest(rubric),'answer_sha256':export.sha(packet/'answer.md'),
              'judgment_sha256':digest(judgment),'score_sha256':digest(result),'evidence':[evidence],
              'new_error':error,'node_judgment':node,'candidate_applicability_correction':'Only invalid as the asserted broad eligibility/backup route; no claim that all underlying schemes are nonexistent.',
              'before':{k:old[k] for k in ('score','score_interval','pending_nodes')},
              'after':{k:result[k] for k in ('score','score_interval','pending_nodes')},
              'candidate_reruns':0,'new_independent_model_reviews':0,'unchanged_answer_rows':len(data['rows'])-1,
              'local_review_directory':local.relative_to(ROOT).as_posix()}
    data['adjudication_history']=data.get('adjudication_history',[])+[data['adjudication']]
    data.update(adjudication=metadata,generated_at=now,extension_rule='Resolve NJUST generalized eligibility claim as an error; all other answer rows inherited unchanged.')
    audit['adjudication_history']=audit.get('adjudication_history',[])+[audit['adjudication']]
    audit.update(adjudication=metadata,adjudicated_judgments=1,verification=f"Base report hashes and affected prior judgment replay verified; one derived answer rescored with the frozen scorer, {len(data['rows'])-1} rows inherited unchanged. Earlier full replays retained in provenance.")
    out.mkdir(parents=True);local.mkdir(parents=True)
    for name,obj in [('task.json',task),('rubric.json',rubric)]:export.put(local/'N10-01'/name,obj)
    for name,obj in [('judgment.json',judgment),('score.json',result)]:export.put(local/'N10-01'/row['packet']/name,obj)
    export.put(local/'receipt.json',metadata);export.put(local/'checksums.json',{'files':export.tree_hashes(local)})
    export.write_tables(out,data,audit);export.charts(out,data,None)
    for zh in (False,True):
        export.report(out,data,audit,False,zh=zh)
        p=out/('README.zh-CN.md' if zh else 'README.md');body=p.read_text()
        notice=('**资格判断修正：** Gemini 3.8 Flash把特殊通道概括为排名普遍放宽的兜底渠道，按已确认适用性错误处理。N10-01-T1由待核改为半分12.5/25，该题64.5分、20题均分60.56。其余答卷成绩不变；个别专项名称不确定不再挂起已有明确错误的评分项。' if zh else '**Qualification adjudication:** Gemini 3.8 Flash generalized restricted recommendation schemes into broadly relaxed rank-based backup routes. N10-01-T1 is now half credit (12.5/25), resolving the task to 64.5 and the Dev20 mean to 60.56. Other answer scores are unchanged; naming uncertainty no longer suspends a grade already determined by substantive correct advice and confirmed applicability errors.')
        body=body.replace('\n\n','\n\n'+notice+'\n\n',1)
        start=body.index('```sh\n');end=body.index('```',start+6)
        command=f"```sh\npython3 scripts/apply_qualification_adjudication.py --base {base.relative_to(ROOT)} --out experiments/subset20-results-qualification-NEW --local reviews/subset20-qualification-NEW\n"
        body=body[:start]+command+body[end:];p.write_text(body)
    for p in list(out.glob('*.md'))+list(out.glob('*.csv')):p.write_text(p.read_text().rstrip()+'\n')
    export.put(out/'adjudication.json',metadata)
    export.put(out/'checksums.json',{'exporter_sha256':export.sha(Path(export.__file__)),'adjudicator_sha256':export.sha(Path(__file__)),'files':export.tree_hashes(out)})
    print({'out':str(out),'score':result['score'],'numeric':sum(r['scored'] for r in data['summary']),'pending':len(data['pending'])})


if __name__=='__main__':main()
