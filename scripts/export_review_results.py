#!/usr/bin/env python3
"""Export an immutable dev20 analysis from completed independent review records.

Read-only on the review directory: never runs reviewers or modifies their files.
Each invocation needs a new output directory. SVG charts need only the standard
library; optional PNG charts use an existing Pillow installation and font.
"""
import argparse
from collections import Counter
import csv
from datetime import datetime
from hashlib import sha256
from html import escape
import json
from pathlib import Path
import sys
import tempfile
from zoneinfo import ZoneInfo

sys.dont_write_bytecode = True

REPO = Path(__file__).resolve().parents[1]
NAMES = {
    'gpt-6-astra': 'GPT-6 Astra', 'gpt-6-1-sol': 'GPT-6.1 Sol',
    'deepseek-v4-1-flash': 'DeepSeek V4.1 Flash',
    'antigravity-gemini-3-1-pro-high': 'Gemini 3.1 Pro',
    'antigravity-gemini-3-8-flash-high': 'Gemini 3.8 Flash',
    'qwen3-8-max-0902': 'Qwen 3.8 Max', 'kimi-k3': 'Kimi K3',
    'ark-glm-5-3-flash-260828': 'GLM 5.3 Flash (Ark)',
    'claude-opus-5-5': 'Claude Opus 5.5',
}
CATEGORIES = {'择校推荐': 'Recommendations', '规划与决策': 'Planning & decisions', '两阶段任务': 'Two-stage tasks'}


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def sha(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def safe_path(base, relative):
    rel = Path(relative)
    require(not rel.is_absolute() and '..' not in rel.parts, 'Unsafe relative evidence path')
    path = base / rel
    require(not any(p.is_symlink() for p in (path, *path.parents)) and
            path.resolve().is_relative_to(base.resolve()), 'Linked or escaping evidence')
    return path


def verify_hashes(base, hashes):
    for name, expected in hashes.items():
        require(sha(safe_path(base, name)) == expected, 'Evidence changed: ' + name)


def tree_hashes(base):
    return {p.relative_to(base).as_posix(): sha(p) for p in sorted(base.rglob('*'))
            if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc'}


def load_scope(source):
    manifest = read(source / 'review-manifest.json')
    verify_hashes(source, read(source / 'input-freeze.json')['files'])
    refs = {'review-manifest.json': sha(source / 'review-manifest.json'),
            'input-freeze.json': sha(source / 'input-freeze.json')}
    staged = [p.name.removesuffix('-supplement-manifest.json')
              for p in sorted(source.glob('qwen-staged-*-supplement-manifest.json'))]
    for name in ['kimi', 'qwen', 'qwen-continuation', *staged]:
        path = source / (name + '-supplement-manifest.json')
        if not path.exists():
            continue
        extra = read(path)
        freeze = source / (name + '-supplement-freeze.json')
        verify_hashes(source, read(freeze)['files'])
        require(extra['parent_manifest_sha256'] == refs['review-manifest.json'], 'Supplement parent changed')
        prior = {(r['agent'], r['task_id']) for r in manifest['packets']}
        added = {(r['agent'], r['task_id']) for r in extra['packets']}
        missing = {(r['agent'], r['task_id']) for r in manifest['missing']}
        require(not prior & added and added <= missing, 'Supplement duplicates or extends the declared scope')
        manifest['packets'] += extra['packets']
        manifest['missing'] = [r for r in manifest['missing'] if (r['agent'], r['task_id']) not in added]
        refs[path.name] = sha(path); refs[freeze.name] = sha(freeze)
    for path in sorted((source / 'rolling').glob('*-manifest.json')):
        freeze = path.with_name(path.name.replace('-manifest.json', '-freeze.json'))
        if not freeze.exists():
            continue  # The organizer has not finished freezing this input yet.
        verify_hashes(source, read(freeze)['files'])
        extra = read(path)
        require(extra['parent_manifest_sha256'] == refs['review-manifest.json'], 'Rolling input parent changed')
        prior = {(r['agent'], r['task_id']) for r in manifest['packets']}
        added = {(r['agent'], r['task_id']) for r in extra['packets']}
        missing = {(r['agent'], r['task_id']) for r in manifest['missing']}
        require(not prior & added and added <= missing, 'Rolling input duplicates or extends declared scope')
        manifest['packets'] += extra['packets']
        manifest['missing'] = [r for r in manifest['missing'] if (r['agent'], r['task_id']) not in added]
        refs[path.relative_to(source).as_posix()] = sha(path)
        refs[freeze.relative_to(source).as_posix()] = sha(freeze)
    require(tree_hashes(source / 'frozen-code') == manifest['source_code_sha256'], 'Frozen scoring source changed')
    return manifest, refs


def aggregate(rows, tasks, ids):
    part = [r for r in rows if r['task_id'] in ids]
    require(bool(ids) and len(ids) == len(set(ids)) and len(part) == len(ids)
            and {r['task_id'] for r in part} == set(ids), 'Missing or duplicate reporting rows')
    done = [r for r in part if r['review_status'] == 'completed']
    numeric = [r for r in done if r['score'] is not None]
    fully_reviewed = len(done) == len(part)
    complete = len(numeric) == len(part)
    intervals = [r['score_interval'] for r in done]
    bounds = [round(sum(v[i] for v in intervals) / len(part), 4) for i in (0, 1)] if fully_reviewed else None
    return {'expected': len(part), 'reviewed': len(done), 'scored': len(numeric),
            'pending': sum(bool(r['pending_nodes']) for r in done),
            'mean': round(sum(r['score'] for r in numeric) / len(part), 4) if complete else None,
            'score_bounds': bounds, 'complete': complete, 'review_complete': fully_reviewed}


def execution_paths(source, manifest, bindings):
    records = {r['packet']: r for r in manifest['packets']}
    paths = {packet: safe_path(source, 'executions/' + packet) for packet in records}
    recovery_file = source / 'timeout-recovery-manifest.json'
    if not recovery_file.exists():
        return service_recovery_paths(source, manifest, records, paths, bindings)
    recovery = read(recovery_file)
    require(recovery.get('same_model_prompt_effort_inputs') is True
            and recovery.get('score_selection') is False, 'Unverified recovery selection')
    bindings[recovery_file.name] = sha(recovery_file)
    for packet, item in recovery['packets'].items():
        require(packet in records and item['original_execution'] == 'executions/' + packet,
                'Recovery outside frozen scope')
        original = paths[packet]
        status = read(original / 'status.json')
        require(status.get('status') == 'failed' and status.get('error_type') == 'TimeoutExpired'
                and not (original / 'judgment.json').exists(), 'Recovery would replace an existing judgment')
        bindings[(original / 'status.json').relative_to(source).as_posix()] = sha(original / 'status.json')
        recovered = safe_path(source, item['new_execution'])
        require(recovered != original and recovered.name == packet
                and recovered.parent.name == 'executions', 'Invalid recovery execution path')
        root = recovered.parent.parent
        recovery_manifest = root / 'review-manifest.json'
        matched = [r for r in read(recovery_manifest)['packets'] if r['packet'] == packet]
        require(matched == [records[packet]], 'Recovery input or configuration changed')
        verify_hashes(root / 'packets' / packet, records[packet]['packet_hashes'])
        require(tree_hashes(root / 'frozen-code') == manifest['source_code_sha256'],
                'Recovery scoring source changed')
        original_settings = read(source / 'judge-settings.json')
        recovered_settings = read(root / 'judge-settings.json')
        require(original_settings['timeout_per_answer_seconds'] == item['original_timeout_seconds']
                and recovered_settings['timeout_per_answer_seconds'] == item['recovery_timeout_seconds'],
                'Recovery timeout differs from declared attempt')
        for settings in (original_settings, recovered_settings):
            settings.pop('selection', None)
            settings.pop('timeout_per_answer_seconds', None)
        require(recovered_settings == original_settings, 'Recovery reviewer settings changed')
        for file in (recovery_manifest, root / 'judge-settings.json'):
            bindings[file.relative_to(source).as_posix()] = sha(file)
        paths[packet] = recovered
    return service_recovery_paths(source, manifest, records, paths, bindings)


def service_recovery_paths(source, manifest, records, paths, bindings):
    recovery_file = source / 'service-recovery-manifest.json'
    if not recovery_file.exists():
        return paths
    recovery = read(recovery_file)
    require(recovery.get('schema') == 'review-service-recovery.1'
            and recovery.get('same_model_prompt_effort_inputs') is True
            and recovery.get('score_selection') is False, 'Unverified service recovery')
    bindings[recovery_file.name] = sha(recovery_file)
    for packet, item in recovery['packets'].items():
        require(packet in records and item['original_execution'] == 'executions/' + packet
                and paths[packet] == source / item['original_execution'],
                'Service recovery outside original scope or overlaps timeout recovery')
        original = paths[packet]
        require(tree_hashes(original) == item['original_files'], 'Original service failure changed')
        status = read(original / 'status.json')
        require(status.get('status') == 'failed' and status.get('issue') == 'CLI exit 1'
                and not (original / 'score.json').exists(), 'Service recovery would replace an accepted review')
        events = [json.loads(line) for line in (original / 'events.jsonl').read_text().splitlines() if line.strip()]
        require(bool(events) and events[-1].get('type') == 'turn.failed'
                and '503 Service Unavailable' in events[-1].get('error', {}).get('message', ''),
                'Missing native service-failure evidence')
        recovered = safe_path(source, item['new_execution'])
        require(recovered != original and recovered.name == packet and recovered.parent.name == 'executions',
                'Invalid service recovery path')
        root = recovered.parent.parent
        recovery_manifest = root / 'review-manifest.json'
        require([r for r in read(recovery_manifest)['packets'] if r['packet'] == packet] == [records[packet]],
                'Service recovery input or configuration changed')
        verify_hashes(root / 'packets' / packet, records[packet]['packet_hashes'])
        require(tree_hashes(root / 'frozen-code') == manifest['source_code_sha256']
                and sha(root / 'run_reviews.py') == sha(source / 'run_reviews.py')
                and read(root / 'judge-settings.json') == read(source / 'judge-settings.json'),
                'Service recovery reviewer protocol changed')
        if (recovered / 'request.json').exists():
            before, after = read(original / 'request.json'), read(recovered / 'request.json')
            require(all(before.get(k) == after.get(k) for k in ('model', 'prompt', 'packet_hashes', 'auth')),
                    'Service recovery native request changed')
        for file in (recovery_manifest, root / 'judge-settings.json', root / 'run_reviews.py'):
            bindings[file.relative_to(source).as_posix()] = sha(file)
        paths[packet] = recovered
    return paths


def collect(source):
    # Import only the already-verified frozen scorer, not the live review/report script.
    manifest, bindings = load_scope(source)
    selection = manifest['selection']
    ids = selection['task_ids']; tasks = {r['task_id']: r for r in selection['tasks']}
    require(selection['id'] == 'public-dev-20-v1' and len(ids) == len(set(ids)) == 20,
            'This report is for the fixed dev20 selection')
    require(set(tasks) == set(ids), 'Selection entries differ from task IDs')
    sys.path.insert(0, str(source / 'frozen-code'))
    from benchmark.scoring import score
    from benchmark.submissions import check_review_settings
    from benchmark.core import digest
    agent_index = read(source / 'snapshot/subset20-active-campaigns.json')['campaign_by_agent']
    agents = [a for a in NAMES if a in agent_index]
    require(set(agents) == set(agent_index), 'Unknown candidate configuration')
    packets = {(r['agent'], r['task_id']): r for r in manifest['packets']}
    require(len(packets) == len(manifest['packets']), 'Duplicate answer selection')
    expected = {(a, t) for a in agents for t in ids}
    require(set(packets) <= expected, 'Answer outside dev20 scope')
    missing = {(r['agent'], r['task_id']): r for r in manifest['missing']}
    errors = {(r['agent'], r['task_id']): r for r in manifest.get('input_errors', [])}
    require(not set(packets) & (set(missing) | set(errors)) and
            set(packets) | set(missing) | set(errors) == expected, 'Incomplete or overlapping source scope')
    generated = datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
    executions = execution_paths(source, manifest, bindings)
    # Capture statuses once. Reviews finishing later belong to the next report.
    statuses = {}
    for key, r in packets.items():
        p = executions[r['packet']] / 'status.json'
        statuses[key] = (read(p), sha(p)) if p.exists() else ({'status': 'not_started'}, None)
    rows, evidence, issues, sessions = [], [], [], set()
    configs = {}
    for a in agents:
        for tid in ids:
            key = a, tid
            row = {'agent': a, 'name': NAMES[a], 'task_id': tid, 'category': tasks[tid]['category'],
                   'case_group_id': tasks[tid]['case_group_id'], 'stage_count': tasks[tid]['stage_count'],
                   'review_status': 'not_completed_at_review_snapshot', 'score': None,
                   'score_interval': None, 'pending_nodes': [], 'deductions': []}
            if key not in packets:
                if key in errors: row['review_status'] = 'input_error'
                rows.append(row); continue
            record = packets[key]; packet = record['packet']
            p = source / 'packets' / packet; out = executions[packet]
            st, st_hash = statuses[key]
            row.update(packet=packet, review_status=st['status'],
                       execution_path=out.relative_to(source).as_posix())
            config = {k: record['configuration'][k] for k in ('id', 'cli', 'cli_version', 'model', 'auth', 'reasoning_effort', 'web_search', 'product')
                      if k in record['configuration']}
            require(a not in configs or configs[a] == config, 'Mixed candidate configuration')
            configs[a] = config
            verify_hashes(p, record['packet_hashes'])
            for original in record['provenance']:
                require(sha(safe_path(source / 'sources' / packet, original['snapshot_file'])) == original['sha256'],
                        'Frozen candidate source changed')
            require(record['source_task_fingerprint'] == tasks[tid]['fingerprints'], 'Task/rubric version mismatch')
            if st['status'] != 'completed':
                rows.append(row); continue
            j = read(out / 'judgment.json')
            require(sha(out / 'judgment.json') == st['judgment_sha256'], 'Completed judgment changed')
            check_review_settings(read(p / 'review-settings.json'), j)
            rubric = read(p / 'rubric.json')
            result = score(read(p / 'task.json'), rubric, (p / 'answer.md').read_text(), j)
            require(result == read(out / 'score.json'), 'Stored score differs from frozen recomputation')
            require(result['id'] == tid and digest(rubric) == tasks[tid]['fingerprints']['rubric'], 'Scored task identity changed')
            req = read(out / 'request.json'); model = req['model']
            require(model['model'] == 'gpt-6.1-sol' and model['reasoning_effort'] == 'high'
                    and model['auth'] == 'subscription' and req['packet_hashes'] == record['packet_hashes'],
                    'Reviewer configuration or input changed')
            events = []
            for line in (out / 'events.jsonl').read_text().splitlines():
                try: events.append(json.loads(line))
                except ValueError: continue
            session_ids = [e['thread_id'] for e in events if e.get('type') == 'thread.started']
            require(len(session_ids) == 1 and session_ids[0] not in sessions
                    and any(e.get('type') == 'turn.completed' for e in events), 'Missing or reused completed review session')
            sessions.add(session_ids[0])
            require(read(out / 'isolation.json')['status'] == 'passed', 'Missing review boundary evidence')
            row.update(score=result['score'], score_interval=result['score_interval'],
                       pending_nodes=result['pending_nodes'], score_status=result['status'])
            numeric = result['score']
            require(len(result['score_interval']) == 2 and
                    0 <= result['score_interval'][0] <= result['score_interval'][1] <= 100,
                    'Invalid score bounds')
            require(numeric is None or result['score_interval'] == [numeric, numeric], 'Point score differs from its bounds')
            nodes = {n['id']: n for n in rubric['nodes']}
            judgments = {n['id']: n for n in j['nodes'] + j['coverage']}
            for n in result['nodes']:
                max_points = nodes[n['id']]['points'] if n['id'] in nodes else rubric['coverage_points'] / rubric['reference_denominator']
                if n['points'] is None or n['points'] < max_points - .001:
                    item = {'node': n['id'], 'points': n['points'], 'max_points': round(max_points, 4),
                            'reason': judgments.get(n['id'], {}).get('reason', 'See the saved rubric judgment and matching allocation.')}
                    row['deductions'].append(item)
                if n['id'] in result['pending_nodes']:
                    issues.append({'agent': a, 'name': NAMES[a], 'task_id': tid, 'node': n['id'],
                                   'max_points': round(max_points, 4), 'packet': packet,
                                   'reason': judgments.get(n['id'], {}).get('reason', ''),
                                   'score_interval': result['score_interval']})
            evidence.append({'agent': a, 'task_id': tid, 'packet': packet, 'status_sha256': st_hash,
                             'execution_path': out.relative_to(source).as_posix(),
                             'packet_hashes': record['packet_hashes'],
                             'review_files': {n: sha(out / n) for n in ('judgment.json', 'score.json', 'request.json', 'events.jsonl', 'isolation.json')},
                             'session_id': session_ids[0], 'recomputed': True})
            # Completed evidence is immutable; reject a concurrent revision.
            require(read(out / 'status.json') == st and sha(out / 'judgment.json') == st['judgment_sha256'],
                    'Review was modified during capture; export again to a new directory')
            rows.append(row)
    for name, expected_hash in bindings.items():
        require(sha(source / name) == expected_hash, 'Review scope changed during capture')
    summary = []
    for a in agents:
        part = [r for r in rows if r['agent'] == a]
        value = aggregate(part, tasks, ids)
        value.update(agent=a, name=NAMES[a], snapshot_answers=sum((a, tid) in packets for tid in ids),
                     configuration=configs[a], statuses=dict(Counter(r['review_status'] for r in part)),
                     categories={en: aggregate(part, tasks, [t for t in ids if tasks[t]['category'] == zh])
                                 for zh, en in CATEGORIES.items()})
        summary.append(value)
    calibration = read(REPO / 'release/publication/review-status-200.json')
    data = {'schema': 'benchmark-review-analysis.1', 'official': False,
            'generated_at': generated, 'selection_id': selection['id'], 'selection_sha256': digest(selection),
            'task_count': 20, 'case_group_count': selection['case_group_count'], 'stage_count': selection['stage_count'],
            'tasks': [{k: t[k] for k in ('task_id', 'title', 'category', 'case_group_id', 'stage_count')} for t in selection['tasks']],
            'review_source': source.name, 'reviewer': read(source / 'judge-settings.json'),
            'teacher_calibration': {'status': calibration['teacher_calibration'], 'recorded_at': calibration['recorded_at'],
                                    'scope': calibration['scope'], 'note': 'Dataset teacher calibration; separate from unresolved answer judgments.'},
            'aggregation': 'Equal task weights. Full means require all 20 numeric scores. Evidence bounds are not confidence intervals or ranks.',
            'extension_rule': 'Create a new report from the same review scope; do not replace this snapshot or rerun completed reviews.',
            'summary': summary, 'rows': rows, 'pending': issues}
    audit = {'schema': 'benchmark-review-analysis-audit.1', 'verified_judgments': len(evidence),
             'scope_bindings': bindings, 'scoring_code_sha256': manifest['source_code_sha256'],
             'calibration_record_sha256': sha(REPO / 'release/publication/review-status-200.json'),
             'records': evidence, 'verification': 'Frozen input hashes, scorer replay, judge settings, unique completed sessions, boundary evidence; no new semantic review.'}
    execution_snapshot = source / 'candidate-execution-snapshot.json'
    if execution_snapshot.exists():
        snapshot = read(execution_snapshot)
        require(snapshot.get('schema') == 'managed-agent-execution-snapshot.1', 'Unknown execution snapshot')
        verify_hashes(safe_path(source, snapshot['source_snapshot_dir']), snapshot['source_snapshot_hashes'])
        states = {r['task_id']: r for r in snapshot['records']}
        require(len(states) == len(snapshot['records']) == 20 and set(states) == set(ids),
                'Execution snapshot tasks differ')
        require(snapshot['agent'] in agents, 'Execution snapshot agent differs')
        for row in data['rows']:
            if row['agent'] == snapshot['agent']:
                row['execution_status'] = states[row['task_id']]['status']
                require(row['review_status'] != 'completed' or row['execution_status'] == 'completed',
                        'Reviewed task conflicts with execution snapshot')
        config = next(r for r in data['summary'] if r['agent'] == snapshot['agent'])
        config['current_answers'] = sum(r['status'] == 'completed' for r in states.values())
        config['execution_status_counts'] = dict(Counter(r['status'] for r in states.values()))
        data['execution_snapshots'] = [snapshot]
        audit['candidate_execution_snapshot_sha256'] = sha(execution_snapshot)
    return data, audit


def merge_review_collections(data, audit, extra, extra_audit):
    """Combine disjoint model configurations with identical task and scorer versions."""
    for field in ('selection_id', 'selection_sha256', 'tasks', 'task_count'):
        require(data[field] == extra[field], 'Additional reviews use another task selection')
    require(audit['scoring_code_sha256'] == extra_audit['scoring_code_sha256'],
            'Additional reviews use another scorer')
    require(data['reviewer']['native'] == extra['reviewer']['native'],
            'Additional reviews use another reviewer configuration')
    prior = {r['agent'] for r in data['summary']}
    added = {r['agent'] for r in extra['summary']}
    require(not prior & added, 'Additional reviews overlap existing configurations')
    prior_sessions = {r['session_id'] for r in audit['records'] if r.get('session_id')}
    added_sessions = {r['session_id'] for r in extra_audit['records'] if r.get('session_id')}
    require(not prior_sessions & added_sessions, 'Additional reviews reuse an existing review session')
    data = dict(data); audit = dict(audit)
    for field in ('summary', 'rows', 'pending'):
        data[field] = data[field] + extra[field]
    data['execution_snapshots'] = data.get('execution_snapshots', []) + extra.get('execution_snapshots', [])
    data['additional_review_sources'] = data.get('additional_review_sources', []) + [extra['review_source']]
    data['generated_at'] = max(data['generated_at'], extra['generated_at'])
    audit['records'] = [dict(r, review_source=r.get('review_source', data['review_source'])) for r in audit['records']] + [dict(r, review_source=extra['review_source']) for r in extra_audit['records']]
    audit['verified_judgments'] += extra_audit['verified_judgments']
    audit['additional_sources'] = audit.get('additional_sources', []) + [dict(extra_audit, review_source=extra['review_source'])]
    return data, audit


def select_cohort(data, audit, agents):
    allowed = set(agents)
    available = {r['agent'] for r in data['summary']}
    require(bool(allowed) and allowed <= available, 'Unknown or empty publication cohort')
    data = dict(data); audit = dict(audit)
    for name in ('summary', 'rows', 'pending'):
        data[name] = [r for r in data[name] if r['agent'] in allowed]
    audit['records'] = [r for r in audit['records'] if r['agent'] in allowed]
    audit['verified_judgments'] = len(audit['records'])
    cohort = {'agents': sorted(allowed), 'excluded_agents': sorted(available - allowed),
              'policy': 'Publication scope only; original reviews and scores are preserved.'}
    data['publication_cohort'] = cohort
    audit['publication_cohort'] = cohort
    return data, audit


def apply_execution_progress(data, audit, progress):
    """Attach a later execution snapshot without changing any frozen review."""
    require(progress.get('schema') == 'review-execution-progress.1'
            and progress.get('selection_id') == data['selection_id']
            and progress.get('selection_sha256') == data['selection_sha256'],
            'Execution progress uses another selection')
    agent = progress['agent']
    selected = [r for r in data['summary'] if r['agent'] == agent]
    require(len(selected) == 1, 'Execution progress agent outside report')
    records = {r['task_id']: r for r in progress['records']}
    require(len(records) == len(progress['records']) == data['task_count']
            and set(records) == {t['task_id'] for t in data['tasks']},
            'Missing or duplicate execution progress tasks')
    reviewed = {r['task_id']: r for r in audit['records'] if r['agent'] == agent}
    for tid, record in records.items():
        require(record['status'] in ('completed', 'failed', 'queued', 'running'),
                'Unknown execution progress status')
        if record['status'] == 'completed':
            require(isinstance(record.get('answer_sha256'), str)
                    and len(record['answer_sha256']) == 64, 'Missing answer fingerprint')
        if tid in reviewed:
            require(record['status'] == 'completed'
                    and record['answer_sha256'] == reviewed[tid]['packet_hashes']['answer.md'],
                    'Execution progress would replace a reviewed answer')
    selected[0]['current_answers'] = sum(r['status'] == 'completed' for r in records.values())
    selected[0]['execution_status_counts'] = dict(Counter(r['status'] for r in records.values()))
    for row in data['rows']:
        if row['agent'] == agent:
            record = records[row['task_id']]
            row.update(execution_status=record['status'], answer_sha256=record.get('answer_sha256'),
                       execution_mode=record['mode'])
    data['execution_progress'] = progress


def number(value):
    return '—' if value is None else f'{value:.2f}'


def cell(value):
    if value['mean'] is not None: return number(value['mean'])
    if value['score_bounds'] is not None: return '–'.join(number(x) for x in value['score_bounds'])
    return '—'


def write_tables(out, data, audit):
    put(out / 'results.json', data); put(out / 'verification.json', audit)
    if 'execution_progress' in data:
        put(out / 'execution-progress.json', data['execution_progress'])
    with (out / 'scores.csv').open('w', newline='', encoding='utf-8-sig') as f:
        fields = ['agent', 'name', 'task_id', 'category', 'review_status', 'score', 'score_lower', 'score_upper', 'pending_nodes', 'packet',
                  'execution_status', 'answer_sha256', 'execution_mode']
        writer = csv.DictWriter(f, fieldnames=fields); writer.writeheader()
        for r in data['rows']:
            writer.writerow({**{k: r.get(k) for k in fields if k in r},
                             'score_lower': r['score_interval'][0] if r['score_interval'] else None,
                             'score_upper': r['score_interval'][1] if r['score_interval'] else None,
                             'pending_nodes': ';'.join(r['pending_nodes'])})
    groups = {}
    for r in data['pending']:
        groups.setdefault((r['task_id'], r['node']), []).append(r)
    lines = ['# 待核事项清单', '', f'结果快照：{data["generated_at"]}。每项保留原评审判断，不在本报告中改分。', '',
             '优先处理影响多个配置的同题同项问题；统一参考院系身份或事实依据后，再对所有受影响答卷应用相同规则。不要将待核直接计零或满分。', '']
    for (tid, node), rows in sorted(groups.items(), key=lambda x: (-len(x[1]), x[0])):
        lines += [f'## {tid} / {node}', '', '影响配置：' + '、'.join(r['name'] for r in rows) + '。', '',
                  f'单题权重上限：{rows[0]["max_points"]:.4g}分；20题等权时，每个配置的整套均值最多受该项影响{rows[0]["max_points"]/20:.4g}分。覆盖匹配存在相互约束，该上限不能与其他项简单相加作为精确影响。', '']
        for r in rows:
            lines += [f'**{r["name"]}**（评审包 `{r["packet"]}`）', '', r['reason'], '']
    (out / 'pending-review.md').write_text('\n'.join(lines) + '\n')


def score_bounds_chart(out, data, font_path):
    """Zero-based bars: purple lower bounds with gold unresolved contributions."""
    sys.path.insert(0, str(REPO))
    from scripts.render_benchmark_figures import EditorialFigure
    ink, muted, paper, rule = '#30283F', '#746C7E', '#FAF7F1', '#E4D9CD'
    solid, possible, track = '#7854A6', '#E9B949', '#EDE5EF'
    configurations = data['summary']
    height = 450 + 83 * len(configurations)
    f = EditorialFigure('Dev20 results: score bounds',
               'Bars share a zero-to-100 axis. Purple shows lower score bounds; gold extends to upper bounds. Pending evidence ranges are not final means or confidence intervals. Unreviewed configurations have no bar.',
               height, font_path)
    f.rect(0, 12, 1600, height-24, paper, radius=36)
    f.text(68, 51, 'BAOYAN AGENT BENCHMARK', 18, solid, True)
    f.text(1532, 51, '02 / DEV20 RESULTS', 18, muted, anchor='end')
    f.text(68, 100, 'How do the agents compare?', 46, ink, True)
    f.text(68, 165, f'{len(configurations)} configurations · Same 20 tasks · 100-point scale', 24, muted)
    f.rect(68, 216, 20, 20, solid, radius=4)
    f.text(100, 216, 'Lower bound', 20, ink)
    f.rect(295, 216, 20, 20, possible, radius=4)
    f.text(327, 216, 'Pending contribution', 20, ink)
    f.text(1532, 216, 'Ranges reflect unresolved evidence', 20, muted, anchor='end')
    f.text(68, 270, 'AGENT CONFIGURATION', 16, muted, True)
    f.text(462, 270, 'SCORE / 100', 16, muted, True)
    f.text(1350, 270, 'MEAN BOUNDS', 16, muted, True, 'end')
    f.text(1532, 270, 'PENDING TASKS', 16, muted, True, 'end')
    f.line(68, 303, 1532, 303, rule, 1)
    x0, plot_width = 462, 634
    axis_y = 331 + len(configurations) * 83 - 26
    for v in range(0, 101, 25):
        x = x0 + v / 100 * plot_width
        f.line(x, 317, x, axis_y, rule, 1)
        f.text(x, axis_y+13, str(v), 17, muted, anchor='middle')
    for i, row in enumerate(configurations):
        y = 329 + i * 83
        f.text(68, y+2, row['name'], 26, ink, True)
        if row['score_bounds'] is None:
            f.text(x0, y+5, f'Reviewed {row["reviewed"]}/20 · mean unavailable', 22, muted)
            f.text(1350, y+1, '—', 27, ink, True, 'end')
            f.text(1508, y+5, '—', 22, muted, anchor='end')
            continue
        lower, upper = row['score_bounds']
        f.rect(x0, y, plot_width, 32, track, radius=5)
        f.rect(x0, y, lower / 100 * plot_width, 32, solid, radius=5)
        if upper > lower:
            f.rect(x0 + lower / 100 * plot_width, y,
                   (upper-lower) / 100 * plot_width, 32, possible)
        f.text(1350, y+1, cell(row), 28, ink, True, 'end')
        f.text(1508, y+5, f'{row["pending"]} / 20', 23, muted, anchor='end')
    f.line(x0, axis_y, x0+plot_width, axis_y, rule, 1)
    f.rect(68, height-72, 1464, 42, ink, radius=12)
    f.text(800, height-61, 'Fixed denominator: 20 tasks  ·  Pending evidence bounds, not confidence intervals or finalized means',
           18, '#FFFFFF', True, 'middle')
    f.save(out, 'score-bounds')


def charts(out, data, font_path):
    sys.path.insert(0, str(REPO))
    from scripts.render_benchmark_figures import Figure, BLUE, GREEN, OCHRE, INK, MUTED, LINE, FILLS
    class Chart(Figure):
        def header(self, number_, title, subtitle):
            self.rect(64, 44, 8, 22, BLUE)
            self.text(88, 44, 'Baoyan Agent Benchmark', 20, INK, True)
            self.text(1536, 46, 'DEV20  /  LOCAL RESULTS', 17, MUTED, anchor='end')
            self.text(64, 108, title, 42, INK, True)
            self.text(64, 179, subtitle, 20, MUTED)
    configurations = data['summary']
    score_bounds_chart(out, data, font_path)
    # Exact scores and pending intervals, with a common denominator in every column.
    width_col = 1160 / max(len(configurations), 1)
    h = 354 + len(data['tasks']) * 44
    f = Chart('Per-task review results', 'Numeric scores are colored. Pending values show their score interval with a P label.', h, font_path)
    f.header('', 'Where do the scores come from?', 'All 20 tasks, same order for every configuration. P = pending evidence; two-stage tasks count once.')
    for i, row in enumerate(configurations):
        x = 360 + i * width_col
        label_lines = {'deepseek-v4-1-flash': ['DeepSeek', 'V4.1 Flash'],
                       'ark-glm-5-3-flash-260828': ['GLM 5.3 Flash', 'Ark Managed Agent']}.get(row['agent'], [row['name']])
        for line_index, label in enumerate(label_lines):
            y = 229 + 20 * line_index if len(label_lines) == 2 else 239
            f.text(x + width_col / 2, y, label,
                   min(19, int((width_col - 16) / (len(label) * .62))), INK, True, 'middle')
    by_key = {(r['agent'], r['task_id']): r for r in data['rows']}
    for j, task in enumerate(data['tasks']):
        y = 279 + j * 44
        f.text(64, y + 8, task['task_id'], 18, INK, True)
        f.text(205, y + 9, ('REC' if task['category'] == '择校推荐' else 'PLAN' if task['category'] == '规划与决策' else 'STAGED'), 14, MUTED)
        for i, row in enumerate(configurations):
            r = by_key[row['agent'], task['task_id']]; x = 360 + i * width_col
            if r['score_interval'] is None:
                fill, color, label = '#EDF1F4', MUTED, '—'
            elif r['score'] is None:
                fill, color = FILLS[2], OCHRE
                label = 'P  ' + '–'.join(f'{n:.1f}' for n in r['score_interval'])
            else:
                v = r['score'] / 100
                fill = '#%02x%02x%02x' % tuple(round(247 + (c - 247) * v) for c in (58, 111, 153))
                color = 'white' if v >= .6 else INK; label = f'{r["score"]:.1f}'
            f.rect(x + 3, y, width_col - 6, 38, fill, radius=3)
            f.text(x + width_col / 2, y + 9, label, 18, color, True, 'middle')
    f.footer('Each cell shows one task score. P = pending. — = not reviewed.')
    f.save(out, 'task-scores')


def report(out, data, audit, png, zh=False):
    complete = [r for r in data['summary'] if r['review_complete']]
    rest = [r for r in data['summary'] if not r['review_complete']]
    ext = 'png' if png else 'svg'
    lines = ['# ' + ('首批20题评测结果' if zh else 'Dev20 results'), '',
             ('[English](README.md)' if zh else '[简体中文](README.zh-CN.md)'), '',
             ('更新时间：' if zh else 'Updated: ') + data['generated_at'], '',
             (f'本报告包含{len(data["summary"])}个配置，其中{len(complete)}个已完成20题评审。以下为本地开发集初评结果。'
              if zh else f'This report includes {len(data["summary"])} configurations; {len(complete)} have completed all 20 reviews. These are preliminary local development-set results.'), '',
             ('分数范围按固定20题和待核项的可得分上下界计算，不是置信区间或已确定的均分。全部题目完成评分后才报告完整均分。' if zh else 'Bounds cover the fixed 20 tasks using the possible scores of pending items. They are not confidence intervals or finalized means. A complete mean requires scores for all tasks.'), '',
             ('**评分复核范围：** 本次公开答卷、运行记录及初评结果。完整逐项评审材料与离线评分复核包暂未公开，因此目前无法仅凭公开材料独立重算全部评分。本页的校验记录反映组织者在本地完成的复算。' if zh else '**Score verification scope:** This release includes answers, execution records, and preliminary results. The complete item-level judgments and offline score verification package are not currently public, so the public materials alone do not support independent recomputation of all scores. The verification records on this page document recomputation performed locally by the organizer.'), '',
             ('| 模型 | 20题均分范围 | 已评审 | 已评分 | 待核题 |' if zh else '| Model | Dev20 mean bounds | Reviewed | Scored | Pending tasks |'),
             '| --- | ---: | ---: | ---: | ---: |']
    for r in data['summary']:
        lines.append(f'| {r["name"]} | {cell(r)} | {r["reviewed"]}/20 | {r["scored"]}/20 | {r["pending"]} |')
    if 'execution_progress' in data:
        progress = data['execution_progress']
        row = next(r for r in data['summary'] if r['agent'] == progress['agent'])
        counts = row['execution_status_counts']
        continued = [r for r in progress['records']
                     if r['mode'] == 'record_assisted_continuation_not_native_session_resume']
        continued_ids = {r['task_id'] for r in continued}
        reviewed_continued = sum(r['agent'] == progress['agent'] and r['task_id'] in continued_ids
                                and r['review_status'] == 'completed' for r in data['rows'])
        missing_checkpoints = sum(r.get('checkpoint_status', '').startswith('failed') for r in continued)
        lines += ['', (f'执行快照：{row["name"]}已完成{row["current_answers"]}/20份答卷，已评审{row["reviewed"]}/20。'
                      f'其中{len(continued)}份答卷在超时后携带既有记录开启新会话并延长时限，属于补充执行，'
                      f'并非原生会话恢复；这些答卷已有{reviewed_continued}份完成评审。'
                      f'{missing_checkpoints}份续作答卷已核对成功交付，但未保存可恢复的会话检查点。'
                      '逐题执行方式、原失败与恢复来源见执行记录。'
                      if zh else f'Execution snapshot: {row["name"]} has {row["current_answers"]}/20 completed answers '
                      f'and {row["reviewed"]}/20 reviews. {len(continued)} answers used new sessions with prior records '
                      f'and an extended budget after timeouts; these are supplemental executions, not native session resumes. '
                      f'{reviewed_continued} of those answers have been reviewed. '
                      f'{missing_checkpoints} were verified as delivered without restorable session checkpoints. '
                      'Per-task execution modes, original failures, and recovery provenance are recorded below.'), '',
                  ('[执行记录与答卷指纹](execution-progress.json)' if zh else '[Execution records and answer fingerprints](execution-progress.json)')]
    for snapshot in data.get('execution_snapshots', []):
        model = NAMES[snapshot['agent']]
        done = sum(r['status'] == 'completed' for r in snapshot['records'])
        failed = sum(r['status'] == 'failed' for r in snapshot['records'])
        lines += ['', (f'{model}：执行快照中{done}/20题有完整答卷，{failed}题执行失败。失败题不计零分；只有20题均有确定分数时才报告整套均分。'
                       if zh else f'{model}: {done}/20 tasks have complete answers and {failed} executions failed in this snapshot. Failed tasks are not assigned zero; a complete mean requires all 20 numeric scores.')]
    if any(r['agent'] == 'ark-glm-5-3-flash-260828' for r in data['summary']):
        lines += ['', ('GLM 配置：GLM 5.3 Flash（火山方舟 Managed Agent），实际模型 `glm-5-3-flash-260828`，通过 arkcli 1.0.37 调用；不是豆包模型。云端隔离未独立审计。'
                       if zh else 'GLM configuration: GLM 5.3 Flash (Volcengine Managed Agent), model `glm-5-3-flash-260828`, via arkcli 1.0.37. This is not a Doubao model. Cloud isolation has not been independently audited.')]
    lines += ['', f'![Dev20 results](score-bounds.{ext})', '',
              ('## 按题型比较' if zh else '## Results by task type'), '',
              ('| 模型 | 择校推荐（6题） | 规划与决策（10题） | 两阶段任务（4题） |'
               if zh else '| Model | Recommendations (6) | Planning & decisions (10) | Two-stage tasks (4) |'),
              '| --- | ---: | ---: | ---: |']
    for r in data['summary']:
        lines.append('| ' + r['name'] + ' | ' + ' | '.join(cell(r['categories'][c]) for c in CATEGORIES.values()) + ' |')
    lines += ['', ('## 逐题分数' if zh else '## Per-task scores'), '', f'![Task results](task-scores.{ext})', '',
              ('[查看待核项](pending-review.md)' if zh else '[View pending items](pending-review.md)'), '']
    if rest:
        lines += [('## 评审进度' if zh else '## Review progress'), '',
                  ('| 模型 | 已收答卷 | 已评审 |' if zh else '| Model | Answers received | Reviewed |'),
                  '| --- | ---: | ---: |']
        for r in rest:
            lines.append(f'| {r["name"]} | {r.get("current_answers", r["snapshot_answers"])}/20 | {r["reviewed"]}/20 |')
        lines += ['']
    lines += ['<details>', ('<summary>评审设置与复现</summary>' if zh else '<summary>Review setup and reproduction</summary>'), '',
              ('- 题集：public-dev-20-v1。20题等权，两阶段题合并计分。'
               if zh else '- Selection: public-dev-20-v1. All 20 tasks have equal weight; two-stage tasks receive one score.'),
              ('- 评审器：Codex CLI 0.162.0，ChatGPT订阅，gpt-6.1-sol / high / live web search。采用单一评审模型，可能存在同模型家族偏差。'
               if zh else '- Reviewer: Codex CLI 0.162.0, ChatGPT subscription, gpt-6.1-sol / high / live web search. A single reviewer may introduce model-family bias.'),
              (f'- 已校验并复算{audit["verified_judgments"]}份评审记录，详情见 [verification.json](verification.json)。'
               if zh else f'- Recomputed and verified {audit["verified_judgments"]} reviews; see [verification.json](verification.json).'),
              ('- 各配置的客户端、认证和工具见 [results.json](results.json)。Kimi包含已留档的答卷恢复及评审超时补跑记录；Qwen的BY-H-APPLY评审亦因超时在相同输入与配置下另行补跑。'
               if zh else '- Client, authentication, and tools are recorded in [results.json](results.json). Kimi includes archived answer-recovery and review-timeout recovery records; Qwen BY-H-APPLY also required a separate review after timeout using the same inputs and configuration.'), '',
              ('生成新报告（需要未公开的本地评审材料）：' if zh else 'Generate a new report (requires the unpublished local review materials):'), '',
              '```sh', 'python3 scripts/export_review_results.py \\', f'  --review-dir reviews/{data["review_source"]} \\',
              *[f'  --additional-review-dir reviews/{name} \\' for name in data.get('additional_review_sources', [])],
              *([f'  --cohort {audit["publication_cohort_path"]} \\'] if audit.get('publication_cohort_path') else []),
              *([f'  --execution-progress {audit["execution_progress_path"]} \\'] if audit.get('execution_progress_path') else []),
              '  --out experiments/subset20-results-YYYYMMDD-HHMMSS', '```', '',
              ('可添加 `--png --font /path/to/font.ttc` 生成PNG。' if zh else 'Add `--png --font /path/to/font.ttc` to generate PNGs.'), '',
              '</details>', '',
              ('[逐题数据](scores.csv) · [完整结果](results.json) · [校验记录](verification.json) · [文件校验值](checksums.json)'
               if zh else '[Task data](scores.csv) · [Full results](results.json) · [Verification](verification.json) · [Checksums](checksums.json)'), '']
    (out / ('README.zh-CN.md' if zh else 'README.md')).write_text('\n'.join(lines), encoding='utf-8')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--review-dir', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--additional-review-dir', type=Path, action='append', default=[], help='Merge a disjoint configuration reviewed under the same protocol')
    p.add_argument('--cohort', type=Path, help='Publish only configurations in this campaign_by_agent index')
    p.add_argument('--execution-progress', type=Path, help='Attach a separately verified, later execution snapshot')
    p.add_argument('--png', action='store_true')
    p.add_argument('--font', type=Path)
    args = p.parse_args()
    source, out = args.review_dir.resolve(), args.out.absolute()
    require(not out.exists() and not out.is_symlink(), 'Use a new report directory')
    require(not out.is_relative_to(source) and not source.is_relative_to(out), 'Keep report and review directories separate')
    require(not args.png or (args.font and args.font.is_file()), 'PNG requires an existing font')
    data, audit = collect(source)
    for extra_source in args.additional_review_dir:
        extra_source = extra_source.resolve()
        require(extra_source != source and not out.is_relative_to(extra_source)
                and not extra_source.is_relative_to(out), 'Keep additional review evidence separate')
        extra_data, extra_audit = collect(extra_source)
        data, audit = merge_review_collections(data, audit, extra_data, extra_audit)
    if args.cohort:
        cohort = read(args.cohort)
        require(cohort['selection_sha256'] == sha(source / 'snapshot/public-dev-20-v1.json'),
                'Publication cohort uses another selection')
        data, audit = select_cohort(data, audit, cohort['campaign_by_agent'])
        audit['publication_cohort_sha256'] = sha(args.cohort)
        audit['publication_cohort_path'] = args.cohort.as_posix()
    if args.execution_progress:
        progress = read(args.execution_progress)
        verify_hashes(REPO, progress['source_files_sha256'])
        apply_execution_progress(data, audit, progress)
        audit['execution_progress_sha256'] = sha(args.execution_progress)
        audit['execution_progress_path'] = args.execution_progress.as_posix()
        audit['execution_progress_verification'] = 'Source files and already reviewed answer bindings checked; existing scores unchanged.'
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.review-report-', dir=out.parent) as tmp:
        stage = Path(tmp) / 'report'; stage.mkdir()
        write_tables(stage, data, audit)
        charts(stage, data, args.font if args.png else None)
        report(stage, data, audit, args.png); report(stage, data, audit, args.png, zh=True)
        put(stage / 'checksums.json', {'exporter_sha256': sha(Path(__file__)), 'files': tree_hashes(stage)})
        stage.rename(out)
    print(json.dumps({'out': str(out), 'verified_judgments': audit['verified_judgments'],
                      'fully_reviewed': [r['name'] for r in data['summary'] if r['review_complete']],
                      'numeric_complete': [r['name'] for r in data['summary'] if r['complete']],
                      'summary': [{k: r[k] for k in ('name', 'reviewed', 'scored', 'pending', 'score_bounds', 'mean')} for r in data['summary']]}, ensure_ascii=False))


if __name__ == '__main__':
    main()
