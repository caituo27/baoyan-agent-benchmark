#!/usr/bin/env python3
"""Package the fixed dev20 r2: preserve r1 evidence and add completed Qwen runs.

Local only; no model calls or uploads. Requires the original r1 ZIP, frozen runs,
and the separately generated seven-configuration review report. Refuses overwrite.
"""
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import shutil
import sys
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.prepare_publication import ROOT, clean, clean_text, export_capture, inside, jsonl, put, read, sha
from scripts.publication_evidence import ledger, scan, usage_events
from benchmark.longitudinal import review_state, review_units

AGENT = 'qwen3-8-max-0902'
EXP = 'experiments/subset20-20261009-r2'
REPORT = 'experiments/subset20-results-seven-complete-20261010'
RELEASE = ROOT / 'release/dev20-20261009/r2'
OUT = ROOT / 'dist/releases/dev20-20261009/r2'
ORIGINAL = ROOT / 'runs/subset20-reuse-four-models-20261009-174520'
CONT = ROOT / 'runs/qwen-progress-continuation6-20261009-212016'
STAGED = ROOT / 'runs/qwen-dev20-remaining4-20261009-225801'
RECOVERY = ROOT / 'runs/qwen-dev20-account-recovery-20261009-2318'


def tree_hashes(root):
    return {p.relative_to(root).as_posix(): sha(p.read_bytes())
            for p in sorted(root.rglob('*')) if p.is_file()}


def metadata(source, target, relative_to=None):
    """Explicit organizer metadata only; never exports credential/checkpoint files."""
    raw = source.read_bytes()
    if source.suffix == '.json':
        put(target, clean(json.loads(raw)))
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(clean_text(raw.decode('utf-8')))
    return {'source': source.relative_to(ROOT).as_posix(),
            'path': target.relative_to(relative_to or target.parent).as_posix(),
            'source_sha256': sha(raw), 'export_sha256': sha(target.read_bytes())}


def capture(source, destination, hashes=None):
    return export_capture(source, hashes if hashes is not None else tree_hashes(source), destination)


def merge_invocations(rows):
    """Deduplicate preserved stage boundaries without dropping evidence aliases."""
    merged = {}
    for row in rows:
        key = row['invocation_id']
        if key not in merged:
            merged[key] = dict(row, aliases=list(row['aliases']),
                               evidence_aliases=[row['evidence']])
            continue
        prior = merged[key]
        for field in ('agent', 'task_id', 'stage_id', 'started_at', 'finished_at',
                      'event_sha256', 'usage', 'elapsed_seconds', 'status'):
            if prior.get(field) != row.get(field):
                raise ValueError(f'Conflicting invocation {key}: {field}')
        for alias in row['aliases']:
            if alias not in prior['aliases']:
                prior['aliases'].append(alias)
        if row['evidence'] not in prior['evidence_aliases']:
            prior['evidence_aliases'].append(row['evidence'])
    return sorted(merged.values(), key=lambda r: (r['agent'], r['task_id'], r['started_at'], r['stage_id'] or ''))


def complete_ledger(exp, progress):
    evidence = exp / 'evidence'
    rows, summaries, failures = [], [], {}
    for folder in (evidence, evidence / 'qwen-original', evidence / 'qwen-stopped-retry'):
        summary = read(folder / 'cost-summary.json')
        summaries.append(summary)
        prefix = folder.relative_to(evidence)
        for line in (folder / 'invocations.jsonl').read_text().splitlines():
            row = json.loads(line)
            row['evidence'] = (prefix / row['evidence']).as_posix()
            rows.append(row)
        for line in (folder / 'controller-failures.jsonl').read_text().splitlines():
            row = json.loads(line)
            row['evidence'] = (prefix / row['evidence']).as_posix()
            if row['id'] in failures:
                prior = failures[row['id']]
                assert prior['result'] == row['result']
                prior['origins'] += [x for x in row['origins'] if x not in prior['origins']]
            else:
                failures[row['id']] = row

    def add(source, tid, meta, stage_id, events, details):
        usage, basis, _ = usage_events(events, 'qwen')
        session = meta.get('new_session_id', meta.get('native_session_id'))
        identity = dict(agent=AGENT, task_id=tid, stage_id=stage_id,
                        started_at=meta['started_at'], session=session)
        key = sha(json.dumps(identity, sort_keys=True).encode())[:24]
        dest = evidence / 'qwen-supplement/history' / sha(str(source).encode())[:24]
        if not dest.exists():
            capture(source, dest)
        rows.append({'invocation_id': key, 'agent': AGENT, 'task_id': tid, 'stage_id': stage_id,
            'cli': 'qwen', 'model': details.get('requested_model'), 'auth_mode': details.get('auth_mode'),
            'started_at': meta['started_at'], 'finished_at': meta['finished_at'], 'status': meta['status'],
            'raw_capture_status': details.get('status'),
            'elapsed_seconds': meta.get('additional_elapsed_seconds', meta.get('elapsed_seconds')),
            'usage': usage, 'usage_basis': basis, 'billed_cost_usd': None,
            'event_sha256': sha(events.read_bytes()), 'evidence': dest.relative_to(evidence).as_posix(),
            'aliases': [{'source': source.relative_to(ROOT).as_posix(), 'origin': source.parent.name}]})

    for record in progress['records']:
        tid = record['task_id']
        if record['mode'] == 'record_assisted_continuation_not_native_session_resume':
            source = CONT / 'executions' / tid
            add(source, tid, read(source / 'status.json'), None,
                source / 'trajectory.jsonl', read(source / 'execution.json'))
        elif record['kind'] == 'staged':
            sources = [ROOT / record['source_campaign'] / 'answers' / tid]
            if record.get('prior_account_failure'):
                sources.append(STAGED / 'answers' / tid)
            for source in sources:
                for attempt in read(source / 'native-episode.json')['attempts']:
                    assert attempt.get('finished_at'), 'Cannot aggregate active stage'
                    sid = attempt['stage_id']
                    events = source / 'stages' / sid / 'events.jsonl'
                    assert sha(events.read_bytes()) == attempt['files']['events.jsonl']
                    add(source, tid, attempt, sid, events,
                        read(source / 'stages' / sid / 'execution.json'))
    calls = merge_invocations(rows)
    agents = sorted({r['agent'] for r in calls})
    assert len(agents) == 7 and AGENT in agents
    per_agent = []
    for agent in agents:
        records = [r for r in calls if r['agent'] == agent]
        summary = {'agent': agent, 'unique_invocations': len(records),
                   'status_counts': dict(Counter(r['status'] for r in records)),
                   'deduplicated_aliases': sum(len(r['aliases']) - 1 for r in records), 'billed_cost_usd': None}
        for metric in ('input_tokens', 'output_tokens', 'cost_usd'):
            known = [r['usage'][metric] for r in records if r['usage'][metric] is not None]
            summary[metric] = {'reported_sum': sum(known) if known else None,
                              'known_invocations': len(known), 'unknown_invocations': len(records) - len(known)}
        durations = [r['elapsed_seconds'] for r in records if r['elapsed_seconds'] is not None]
        summary['invocation_seconds'] = {'reported_sum': sum(durations) if durations else None,
                                        'unknown_invocations': len(records) - len(durations)}
        per_agent.append(summary)
    jsonl(evidence / 'invocations.jsonl', calls)
    jsonl(evidence / 'controller-failures.jsonl', list(failures.values()))
    put(evidence / 'cost-summary.json', {'schema': 'historical-cost-ledger.1',
        'scope': 'dev20_r2_seven_agents_including_qwen_continuation_and_account_recovery',
        'snapshot_finished_at': datetime.now(timezone.utc).isoformat(),
        'call_unit': summaries[0]['call_unit'], 'unique_invocations': len(calls),
        'call_references': sum(len(r['aliases']) for r in calls),
        'duplicate_references_removed': sum(len(r['aliases']) - 1 for r in calls),
        'per_agent': per_agent, 'actual_billing_known': False,
        'controller_failures_without_cli_capture': len(failures),
        'gaps': [g for s in summaries for g in s['gaps']],
        'lineage': [x for s in summaries for x in s['lineage']] + [
            {'campaign': p.name, 'kind': 'qwen_supplement'} for p in (CONT, STAGED, RECOVERY)],
        'limitations': summaries[0]['limitations'] + [
            'Restored S0 copies are deduplicated by session, stage and start time; continuation elapsed time excludes the original timed-out call.',
            'Nested qwen-original and qwen-stopped-retry ledgers are source snapshots, not additional calls to sum on top of this merged ledger.']})


def attach_scores(rows, scores):
    for row in rows:
        score = scores[row['agent'], row['task_id']]
        for field in ('score', 'score_status', 'review_status', 'score_interval', 'pending_nodes'):
            row[field] = score[field]


def main():
    assert not OUT.exists(), 'Use an unused revision; never overwrite a package'
    old = read(ROOT / 'release/dev20-20261009/r1/manifest.json')
    archive = ROOT / old['local_artifact_directory'] / old['assets'][0]['file']
    assert sha(archive.read_bytes()) == old['assets'][0]['sha256']
    progress = read(ROOT / 'release/publication/dev20-qwen-execution-complete-20261009.json')
    for name, expected in progress['source_files_sha256'].items():
        assert sha(inside(ROOT, name).read_bytes()) == expected, name
    report = read(ROOT / REPORT / 'results.json')
    assert len(report['rows']) == 140
    scores = {(r['agent'], r['task_id']): r for r in report['rows']}
    OUT.mkdir(parents=True)
    package = OUT / 'package'
    package.mkdir()
    # Verify the old archive in full; keep original answers and traces byte-identical.
    with zipfile.ZipFile(archive) as z:
        checks = json.loads(z.read('checksums.json'))
        assert all(sha(z.read(n)) == h for n, h in checks.items())
        previous_results = json.loads(z.read(old['result_snapshot'] + '/results.json'))
        for row in previous_results['rows']:
            current = scores[row['agent'], row['task_id']]
            assert (current['score'], current['pending_nodes']) == (row['score'], row['pending_nodes'])
        for name in z.namelist():
            if name.endswith('/'):
                continue
            if name.startswith('experiments/subset20-20261009/'):
                dest = inside(package, name.replace('experiments/subset20-20261009/', EXP + '/', 1))
            elif name in ('LICENSE', 'LICENSE-DATA'):
                dest = package / name
            else:
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(z.read(name))
    exp = package / EXP
    six_records = {n: h for n, h in tree_hashes(exp / 'records').items()
                   if Path(n).name != 'record.json'}
    first = read(ORIGINAL / 'selection.json')
    assert first['task_ids'] == read(exp / 'selection.json')['task_ids']
    batch, state = read(ORIGINAL / 'parallel-batch.json'), read(ORIGINAL / 'parallel-state.json')
    config = next(a for a in batch['registry']['agents'] if a['id'] == AGENT)
    jobs = {j['id']: j for j in batch['jobs'] if j['agent'] == AGENT}
    rows = [json.loads(s) for s in (exp / 'results.jsonl').read_text().splitlines()]
    linkage = []
    for current in progress['records']:
        tid = current['task_id']; job = jobs[tid]; prior = state['jobs'][job['index']]
        dest = exp / 'records' / AGENT / tid
        history = []
        for attempt in prior['attempts']:
            assert attempt.get('finished_at'), 'Do not package active attempts'
            source = ORIGINAL / 'attempts' / str(job['index']) / ('a' + str(attempt['number']))
            target = dest / ('original-a' + str(attempt['number']))
            capture(source, target, attempt['files'])
            history.append({'kind': 'original_attempt', 'number': attempt['number'],
                            'result': clean(attempt.get('result')), 'artifacts': target.relative_to(exp).as_posix()})
        selected = dest / 'selected'
        if current['kind'] == 'single':
            source = ROOT / current['answer_path']
            assert sha(source.read_bytes()) == current['answer_sha256']
            capture(source.parent, selected)
            if current['mode'] != 'original_campaign':
                # The actual continuation prompt contains the prior trace/draft supplied to the model.
                receipt = metadata(source.parent / 'actual-query.md', selected / 'actual-query.md')
                put(selected / 'actual-query-provenance.json', receipt)
                repair = CONT / 'status-repairs' / tid / 'correction.json'
                if repair.exists():
                    metadata(repair, selected / 'status-correction.json')
            else:
                capture(source.parent.parent, dest / 'selected-run-metadata')
            answer_hashes = [current['answer_sha256']]
        else:
            source = ROOT / current['source_campaign'] / 'answers' / tid
            staged_state = review_state(source)
            assert len(staged_state['records']) == 2
            _, _, merged = next(iter(review_units(staged_state).values()))
            assert sha(merged.encode()) == current['answer_sha256']
            capture(source, selected)
            metadata(source / 'native-episode.json', selected / 'native-episode.json')
            answer_hashes = [sha((source / 'stages' / stage / 'answer.md').read_bytes()) for stage in ('S0', 'S1')]
            if current.get('prior_account_failure'):
                failed = STAGED / 'answers' / tid
                capture(failed, dest / 'account-failure')
                metadata(failed / 'native-episode.json', dest / 'account-failure/native-episode.json')
                history.append({'kind': 'account_failure', 'artifacts': (dest / 'account-failure').relative_to(exp).as_posix(),
                                'status': 'failed', 'preserved_S0': current['preserved_S0']})
        row = scores[AGENT, tid]
        assert row['answer_sha256'] == current['answer_sha256']
        actual = [a for f in selected.rglob('artifacts.json') for a in read(f) if Path(a['path']).name == 'answer.md']
        assert sorted(a['source_sha256'] for a in actual) == sorted(answer_hashes), tid
        record = {'agent': AGENT, 'task_id': tid, 'case_group_id': job['case_group_id'],
                  'kind': current['kind'], 'repeat': 1, 'status': 'completed',
                  'selected_artifacts': selected.relative_to(exp).as_posix(), 'attempts': history,
                  'execution_mode': current['mode'], 'score': row['score'], 'score_status': row['score_status'],
                  'review_answer_sha256': current['answer_sha256'], 'official': False}
        put(dest / 'record.json', record)
        rows.append({k: v for k, v in record.items() if k != 'attempts'})
        linkage.append({'agent': AGENT, 'task_id': tid, 'selected_artifacts': record['selected_artifacts'],
                        'original_answer_sha256': answer_hashes, 'review_answer_sha256': current['answer_sha256']})
    # Trace all reachable original calls, including failed and superseded batches.
    ledger({'campaign_by_agent': {AGENT: str(ORIGINAL)}}, first, exp / 'evidence/qwen-original')
    retry = ROOT / 'runs/subset20-qwen-timeout-retry6-20261009-211644'
    ledger({'campaign_by_agent': {AGENT: str(retry)}}, first, exp / 'evidence/qwen-stopped-retry')
    receipts = []
    for source, names in (
        (CONT, ('agents.frozen.json', 'registration-v2.json', 'continuation-plan.json', 'continuation-status.json',
                'run_continuations.py', 'run_continuations_v2.py', 'repair_answer_status.py')),
        (STAGED, ('agents.frozen.json', 'run-manifest.json', 'progress.json', 'run_remaining.py')),
        (RECOVERY, ('agents.frozen.json', 'run-manifest.json', 'recovery-manifest.json', 'progress.json', 'run_remaining.py')),
    ):
        for name in names:
            receipts.append(metadata(source / name, exp / 'evidence/qwen-supplement' / source.name / name,
                                     relative_to=exp / 'evidence/qwen-supplement'))
    assert len({r['path'] for r in receipts}) == len(receipts)
    for receipt in receipts:
        assert sha(inside(exp / 'evidence/qwen-supplement', receipt['path']).read_bytes()) == receipt['export_sha256']
    put(exp / 'evidence/qwen-supplement/provenance.json', receipts)
    complete_ledger(exp, progress)
    put(exp / 'qwen-execution.json', clean(progress))
    configs = read(exp / 'configurations.json')
    configs.append({'agent': AGENT, 'configuration': clean(config), 'campaign': ORIGINAL.name,
                    'policy': clean(batch['policy']), 'engine': 'sources/' + ORIGINAL.name,
                    'status_counts': {'completed': 20}, 'repeats': 1, 'official': False,
                    'supplement': 'evidence/qwen-supplement',
                    'note': progress['note'], 'cost_usd': None})
    registry_path = exp / 'sources' / ORIGINAL.name / 'registry.json'
    registry = read(registry_path)
    if not any(a['id'] == AGENT for a in registry['agents']):
        registry['agents'].append(clean(config))
    put(registry_path, registry)
    put(exp / 'configurations.json', configs)
    attach_scores(rows, scores)
    for row in rows:
        path = exp / 'records' / row['agent'] / row['task_id'] / 'record.json'
        record = read(path)
        attach_scores([record], scores)
        put(path, record)
    jsonl(exp / 'results.jsonl', rows)
    # r1's record paths are relative to the experiment root and remain valid in r2.
    for rel, expected in six_records.items():
        assert sha((exp / 'records' / rel).read_bytes()) == expected
    for row in rows:
        selected = exp / row['selected_artifacts']
        assert selected.is_dir()
        if row['agent'] != AGENT:
            old_link = read(exp / 'review-linkage.json')['answers']
            link = next(x for x in old_link if x['agent'] == row['agent'] and x['task_id'] == row['task_id'])
            exported = [a for f in selected.rglob('artifacts.json') for a in read(f)
                        if Path(a['path']).name == 'answer.md']
            assert set(link['original_answer_sha256']) <= {a['source_sha256'] for a in exported}
            linkage.append(link)
    assert len(rows) == len(linkage) == 140
    put(exp / 'review-linkage.json', {'official': False, 'answers': linkage,
        'reviewed_answers': 140, 'scorable_answers': 129, 'pending_answers': 11,
        'result_snapshot': '../' + Path(REPORT).name, 'result_json_sha256': sha((ROOT / REPORT / 'results.json').read_bytes())})
    put(exp / 'cohort.json', read(RELEASE / 'cohort.json'))
    manifest = {'schema': 'subset-experiment-snapshot.2', 'release_id': 'dev20-20261009-r2',
        'task_count_per_agent': 20, 'stage_count_per_agent': 24, 'agent_count': 7,
        'expected_results': 140, 'completed': 140, 'reviewed': 140, 'scored': 129, 'pending': 11,
        'official': False, 'uploaded': False, 'previous_revision': 'r1',
        'qwen_execution': 'qwen-execution.json', 'result_snapshot': '../' + Path(REPORT).name,
        'reproduction_note': 'Frozen original engine and supplemental scripts/configuration are included. Supplemental scripts retain historical paths; no fresh seven-agent replay or checkpoint export is claimed.'}
    put(exp / 'manifest.json', manifest)
    text = ('# 首批20题运行记录：r2（含千问）\n\n'
        '七个配置各20题、24阶段，共140份已完成及已初评答卷；129份确定分数、11份待核。'
        '新增千问 Qwen 3.8 Max 的20份完整记录，均分65.9725。六配置原有答卷和轨迹逐文件保持不变。\n\n'
        '千问6题在超时后携带既有记录开启新会话，并延长时限；4道两阶段题单独执行，'
        '其中3题遇到账号错误后恢复（2题接续第一阶段，1题重新开始）。原失败、停止的重跑及恢复来源均保留。'
        '这些执行不构成统一的一次运行；checkpoint与凭据不导出。\n\n'
        f'[七配置逐题评分](../{Path(REPORT).name}/README.zh-CN.md) · '
        '[答卷哈希关联](review-linkage.json) · [执行方式](qwen-execution.json) · '
        '[发布清单](../../release/dev20-20261009/r2/manifest.json)\n\n'
        'records/保存脱敏答卷、轨迹和本轮尝试；evidence/保存历史调用及补充执行配置。'
        'results.jsonl与逐题record.json统一关联评分，待核项保留空分及分数区间。'
        'evidence/invocations.jsonl及cost-summary.json汇总七配置调用，已去重恢复时复用的第一阶段。'
        '公开文件保存原始/导出双哈希，费用未知保留为空。仅附20题范围。'
        '原六配置r1仍保留；GLM未完成的运行不在本包范围。当前仅本地生成，尚未上传。\n')
    (exp / 'README.md').write_text(text)
    shutil.copytree(ROOT / REPORT, package / REPORT)
    privacy = scan(package)
    put(exp / 'privacy-scan.json', privacy)
    assert not privacy['findings'], 'Inspect sanitized export before packaging'
    (package / 'FIRST-EXPERIMENT.md').write_text(text.replace('../' + Path(REPORT).name, REPORT)
        .replace('(review-linkage.json)', '(' + EXP + '/review-linkage.json)')
        .replace('(qwen-execution.json)', '(' + EXP + '/qwen-execution.json)')
        .replace('../../release/', 'release/'))
    release = {'schema': 'experiment-release.1', 'experiment_id': 'dev20-20261009', 'revision': 'r2',
        'release_id': 'dev20-20261009-r2', 'title': '首批20题：七配置完整结果与运行记录（含千问）',
        'status': 'local_draft_pending_artifact_review', 'uploaded': False, 'official': False,
        'configurations': sorted(c['agent'] for c in configs), 'scope': manifest,
        'experiment_records': EXP, 'result_snapshot': REPORT,
        'previous_revision_sha256': sha((ROOT / 'release/dev20-20261009/r1/manifest.json').read_bytes()),
        'six_agent_evidence_files_preserved': len(six_records), 'score_metadata_records_refreshed': 140,
        'local_artifact_directory': OUT.relative_to(ROOT).as_posix(),
        'privacy_scan': privacy['status'], 'qwen_review_answer_hash_matches': len(progress['records']),
        'generator_sha256': sha(Path(__file__).read_bytes())}
    put(package / 'EXPERIMENT-RELEASE.json', release)
    # Inside the ZIP, link to the non-circular release scope; outer manifest binds the ZIP hash.
    put(package / 'release/dev20-20261009/r2/manifest.json', release)
    checks = tree_hashes(package)
    put(package / 'checksums.json', checks)
    zip_path = OUT / 'dev20-20261009-r2-seven-results-and-records.zip'
    with zipfile.ZipFile(zip_path, 'x', compression=zipfile.ZIP_DEFLATED) as z:
        for path in sorted(package.rglob('*')):
            if path.is_file():
                z.write(path, path.relative_to(package).as_posix())
    with zipfile.ZipFile(zip_path) as z:
        assert z.testzip() is None
        assert all(sha(z.read(n)) == h for n, h in checks.items())
    release['assets'] = [{'file': zip_path.name, 'sha256': sha(zip_path.read_bytes()),
                          'bytes': zip_path.stat().st_size, 'files': len(checks) + 1}]
    put(RELEASE / 'manifest.json', release)
    put(RELEASE / 'checksums.json', {'manifest.json': sha((RELEASE / 'manifest.json').read_bytes()),
        'cohort.json': sha((RELEASE / 'cohort.json').read_bytes()), zip_path.name: release['assets'][0]['sha256']})
    for name in ('manifest.json', 'checksums.json', 'cohort.json'):
        shutil.copy2(RELEASE / name, OUT / name)
    # Keep only lightweight record indexes in Git; full evidence stays in the ZIP.
    repo_exp = ROOT / EXP
    assert not repo_exp.exists()
    repo_exp.mkdir()
    for name in ('README.md', 'manifest.json', 'configurations.json', 'selection.json', 'cohort.json',
                 'results.jsonl', 'review-linkage.json', 'qwen-execution.json', 'privacy-scan.json'):
        shutil.copy2(exp / name, repo_exp / name)
    print(json.dumps({'archive': str(zip_path), 'records': len(rows), 'qwen': len(progress['records']),
                      'preserved_files': len(six_records), 'privacy': privacy['status']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
