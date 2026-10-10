#!/usr/bin/env python3
"""Create a local-only, immutable publication draft. Never calls models or uploads."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from benchmark.core import digest, query_prompt


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def sha(data):
    return hashlib.sha256(data).hexdigest()


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n', encoding='utf-8')


def jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(x, ensure_ascii=False, sort_keys=True) + '\n' for x in rows), encoding='utf-8')


def inside(base, name):
    rel = Path(name)
    if rel.is_absolute() or '..' in rel.parts or (base / rel).is_symlink():
        raise ValueError('Unsafe artifact path: ' + str(name))
    path = (base / rel).resolve()
    if not path.is_relative_to(base.resolve()):
        raise ValueError('Artifact escapes source')
    return path


def safe_id(value):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', value):
        raise ValueError('Unsafe identifier')
    return value


SECRET_KEY = re.compile(r'^(?:authorization|cookie|set-cookie|api[_-]?key|access[_-]?token|refresh[_-]?token|id[_-]?token|password|client[_-]?secret|email)$', re.I)


def clean_text(value):
    value = re.sub(r'/Users/[^/\s"\\]+', '/Users/REDACTED', value)
    value = re.sub(r'/home/[^/\s"\\]+', '/home/REDACTED', value)
    value = re.sub(r'(?i)(Bearer\s+)[A-Za-z0-9._~+/=-]+', r'\1[REDACTED]', value)
    value = re.sub(r'\b(?:sk-|hf_|ghp_|github_pat_)[A-Za-z0-9_-]{16,}', '[REDACTED]', value)
    value = re.sub(r'(?i)((?:api[_-]?key|access[_-]?token|refresh[_-]?token|password|client[_-]?secret)\s*[=:]\s*)[^\s,;"\'}]+', r'\1[REDACTED]', value)
    value = re.sub(r'\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b', '[REDACTED_JWT]', value)
    value = re.sub(r'\bAKIA[A-Z0-9]{16}\b', '[REDACTED_KEY]', value)
    value = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b', '[REDACTED_EMAIL]', value)
    value = re.sub(r'(?<![A-Za-z0-9])(?:\+?86[- ]?)?1[3-9]\d{9}(?![A-Za-z0-9])', '[REDACTED_PHONE]', value)
    value = re.sub(r'(?im)((?:set-cookie|cookie)\s*:\s*)[^\r\n]+', r'\1[REDACTED_COOKIE]', value)
    value = re.sub(r'(?i)((?:[?&]|\\u0026)(?:token|access_token|api_key|key|signature|x-amz-signature|x-goog-signature)=)[^\s"&\\<>]+', r'\1[REDACTED]', value)
    return value


def clean(value):
    if isinstance(value, dict):
        return {k: '[REDACTED]' if SECRET_KEY.fullmatch(k) else clean(v) for k, v in value.items()}
    if isinstance(value, list):
        return [clean(v) for v in value]
    return clean_text(value) if isinstance(value, str) else value


META = ('schema_version', 'adapter', 'adapter_version', 'cli', 'cli_version', 'model', 'product',
        'reported_models', 'model_identity_status', 'model_observation', 'auth_mode', 'execution_config',
        'execution_backend', 'status', 'started_at', 'finished_at', 'created_at', 'elapsed_seconds',
        'timeout_seconds', 'exit_code', 'usage', 'usage_status', 'trajectory_status', 'answer_capture',
        'official', 'task_id', 'task_sha256', 'rubric_sha256', 'protocol_sha256', 'experiment_sha256',
        'isolation_verified', 'host_configuration_verified', 'execution_mode', 'isolation_evidence_source',
        'execution_contract_sha256', 'snapshot_sha256', 'timing_provenance')


def export_capture(source, hashes, destination):
    """Only allowlisted public artifacts; never copy HOME, credentials or checkpoints."""
    from scripts.publication_evidence import PATTERNS
    artifacts = []
    for name, expected in sorted(hashes.items()):
        path = inside(source, name)
        leaf = path.name
        allowed = (leaf in {'answer.md', 'final-response.md', 'query.md', 'trajectory.jsonl', 'events.jsonl',
                            'trace.jsonl', 'usage.json', 'execution.json', 'protocol.json', 'run.json',
                            'status.json', 'cli.stderr.log', 'stderr.log', 'worker.stderr.log', 'worker.stdout.log', 'result.json'} or
                   (leaf.endswith('-prompt.md') and 'visible' in Path(name).parts))
        if not allowed:
            continue
        raw = path.read_bytes()
        if sha(raw) != expected:
            raise ValueError('Finished artifact changed: ' + str(path))
        body = raw.decode('utf-8')
        if leaf == 'run.json':
            meta = json.loads(body)
            body = json.dumps(clean({k: meta[k] for k in META if k in meta}), ensure_ascii=False, sort_keys=True, indent=2) + '\n'
        elif path.suffix == '.json':
            body = json.dumps(clean(json.loads(body)), ensure_ascii=False, sort_keys=True, indent=2) + '\n'
        elif path.suffix == '.jsonl':
            lines = []
            for line in body.split('\n'):
                if not line.strip():
                    continue
                try:
                    lines.append(json.dumps(clean(json.loads(line)), ensure_ascii=False, sort_keys=True))
                except json.JSONDecodeError:
                    lines.append(clean_text(line))
            body = '\n'.join(lines) + ('\n' if lines else '')
        else:
            body = clean_text(body)
        public = body.encode('utf-8')
        out = inside(destination, name)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(public)
        artifacts.append({'path': name, 'source_sha256': expected, 'export_sha256': sha(public),
                          'transformed': public != raw, 'bytes': len(public),
                          'source_pattern_counts': {k: len(p.findall(raw.decode('utf-8')))
                              for k, p in PATTERNS.items() if p.search(raw.decode('utf-8'))}})
    put(destination / 'artifacts.json', artifacts)
    return artifacts


def load_selection(path):
    data = read(path)
    if data['task_count'] != len(data['tasks']) or data['task_ids'] != [x['task_id'] for x in data['tasks']]:
        raise ValueError('Selection count/order mismatch')
    if len(set(data['task_ids'])) != data['task_count']:
        raise ValueError('Duplicate task')
    for row in data['tasks']:
        safe_id(row['task_id'])
        for kind in ('task', 'rubric'):
            current = read(inside(ROOT, row[kind + '_path']))
            if digest(current) != row['fingerprints'][kind]:
                raise ValueError('Selected content changed: ' + row['task_id'])
    for name, expected in data['source_files_sha256'].items():
        if sha(inside(ROOT, name).read_bytes()) != expected:
            raise ValueError('Selection dependency changed: ' + name)
    return data


def dataset(out, selected, first, status):
    single, staged, rubrics = [], [], []
    for row in selected['tasks']:
        task = read(ROOT / row['task_path']); rubric = read(ROOT / row['rubric_path'])
        meta = {k: row[k] for k in ('task_id', 'track', 'category', 'case_group_id', 'stage_count')}
        meta.update(effective_review={'teacher_calibration': status['teacher_calibration'], 'basis': 'owner_confirmation', 'historical_review_fields': 'frozen_metadata_not_current_status'}, task_sha256=row['fingerprints']['task'], rubric_sha256=row['fingerprints']['rubric'],
                    in_first_experiment=row['task_id'] in first['task_ids'])
        if row['track'] == 'dev':
            single.append(dict(meta, input=query_prompt(task), task_json=json.dumps(task, ensure_ascii=False)))
        else:
            staged.append(dict(meta, stages_json=json.dumps(task['stages'], ensure_ascii=False), task_json=json.dumps(task, ensure_ascii=False)))
        rubrics.append({'task_id': row['task_id'], 'rubric_sha256': row['fingerprints']['rubric'], 'rubric_json': json.dumps(rubric, ensure_ascii=False), 'effective_review': meta['effective_review']})
        for kind, obj in [('task', task), ('rubric', rubric)]:
            put(out / 'tasks' / row['task_id'] / (kind + '.json'), obj)
    jsonl(out / 'single-stage.jsonl', single); jsonl(out / 'staged.jsonl', staged); jsonl(out / 'rubrics.jsonl', rubrics)
    put(out / 'selection-75.json', selected); put(out / 'selection-20.json', first)
    put(out / 'selection-40.json', read(ROOT / 'config/selections/public-test-40-v1.json'))
    for src, dest in [('docs/scoring.md', 'scoring.md'), ('LICENSE-DATA', 'LICENSE'),
                      ('docs/huggingface/CITATION.cff', 'CITATION.cff'),
                      ('docs/huggingface/CALIBRATION-STATUS.md', 'CALIBRATION-STATUS.md')]:
        (out / dest).write_bytes((ROOT / src).read_bytes())
    for name in ('README.md', 'README.zh-CN.md'):
        card = (ROOT / 'docs/huggingface' / name).read_text(encoding='utf-8')
        for source, target in (('../scoring.md', 'scoring.md'),
                               ('../../LICENSE-DATA', 'LICENSE'),
                               ('../../config/selections/public-dev-75-v1.json', 'selection-75.json')):
            card = card.replace('](' + source + ')', '](' + target + ')')
        (out / name).write_text(card, encoding='utf-8')
    put(out / 'manifest.json', {'schema': 'selected-hf-draft.2', 'scope': 'local_publication_draft',
        'task_count': selected['task_count'], 'stage_count': selected['stage_count'],
        'case_group_count': selected['case_group_count'], 'counts': selected['counts'],
        'selection_sha256': sha((ROOT / 'config/selections/public-dev-75-v1.json').read_bytes()),
        'teacher_calibration': status['teacher_calibration'], 'historical_review_fields': 'frozen_metadata_not_current_status', 'private_test_tasks_in_export': 0, 'official': False, 'uploaded': False, 'public_release_approved': False})


def experiment(out, index, first, captured_at):
    results, configurations = [], []
    snapshots = {}
    for agent, dirname in sorted(index['campaign_by_agent'].items()):
        safe_id(agent)
        campaign = Path(dirname).resolve()
        if not campaign.is_relative_to(ROOT / 'runs'):
            raise ValueError('Campaign outside local public runs')
        if campaign not in snapshots:
            batch_raw = (campaign / 'parallel-batch.json').read_bytes()
            state_raw = (campaign / 'parallel-state.json').read_bytes()
            batch, state = json.loads(batch_raw), json.loads(state_raw)
            snapshots[campaign] = batch, state, sha(batch_raw), sha(state_raw)
        batch, state, batch_hash, state_hash = snapshots[campaign]
        if (batch['selection_sha256'] != sha((campaign / 'selection.json').read_bytes())
                or read(campaign / 'selection.json') != first):
            raise ValueError('Campaign selection mismatch')
        config = next(a for a in batch['registry']['agents'] if a['id'] == agent)
        matching = [(j, state['jobs'][j['index']]) for j in batch['jobs'] if j['agent'] == agent]
        if [j['id'] for j, _ in matching] != first['task_ids']:
            raise ValueError('Cohort must have exactly the original 20 tasks')
        source_dir = out / 'sources' / campaign.name
        if not source_dir.exists():
            source_dir.mkdir(parents=True)
            from scripts.publication_scope import project, rebind_selection
            public_scope = read(ROOT / 'config/selections/public-dev-75-v1.json')
            report = project(batch['source_files'], campaign / 'source', source_dir / 'engine', public_scope)
            report.update(original_registry_digest=digest(batch['registry']),
                reproduction_adjustment='Public75 collection manifests and selected dependency hashes projected; registry restricted to the publication cohort; CLI absolute binaries become basenames. Retained task/rubric bytes, model/auth and budget unchanged.')
            put(source_dir / 'source-manifest.json', report)
            portable_registry = json.loads(json.dumps(batch['registry']))
            portable_registry['agents'] = [a for a in portable_registry['agents']
                                           if a['id'] in index['campaign_by_agent']]
            for recipe in portable_registry['agents']:
                recipe['binary'] = Path(recipe['binary']).name
            put(source_dir / 'registry.json', clean(portable_registry))
            put(source_dir / 'selection.json', rebind_selection(first, source_dir / 'engine'))
        configurations.append({'agent': agent, 'configuration': clean(config), 'campaign': campaign.name,
            'batch_sha256': batch_hash, 'state_sha256': state_hash, 'policy': clean(batch['policy']),
            'engine': str(source_dir.relative_to(out)), 'status_counts': dict(Counter(s['status'] for _, s in matching)),
            'prior_campaign': clean(batch.get('superseded_campaign', {}).get('path')),
            'account_recovery': clean(batch.get('account_recovery_attempts', {})),
            'repeats': batch['registry']['repeats'], 'official': False})
        for job, state_row in matching:
            task_id = safe_id(job['id'])
            target = out / 'records' / agent / task_id
            attempts = []
            for attempt in state_row['attempts']:
                entry = {k: clean(attempt[k]) for k in ('number', 'started_at', 'finished_at', 'result') if k in attempt}
                if attempt.get('files') and attempt.get('finished_at'):
                    relative = f'attempts/{job["index"]}/a{attempt["number"]}'
                    dest = target / f'a{attempt["number"]}'
                    files = export_capture(inside(campaign, relative), attempt['files'], dest)
                    entry.update(artifacts=str(dest.relative_to(out)), artifact_count=len(files))
                else:
                    entry['artifacts'] = None  # Active files are mutable; never read them.
                attempts.append(entry)
            selected = state_row.get('selected')
            selected_path = None
            if selected and 'reused' in selected:
                reuse = batch['reused_runs'][selected['reused']]
                source = Path(reuse['path']).resolve()
                if not source.is_relative_to(ROOT / 'runs'):
                    raise ValueError('Reused capture outside public runs')
                dest = target / 'reused'
                files = export_capture(source, reuse['files'], dest)
                selected_path = str(dest.relative_to(out))
                attempts.insert(0, {'kind': 'reused', 'source': clean_text(str(source.relative_to(ROOT))),
                    'artifacts': selected_path, 'artifact_count': len(files),
                    'source_files_sha256': reuse['files'], 'answer_sha256': reuse.get('answer_sha256')})
            elif selected and 'attempt' in selected:
                selected_path = str((target / f'a{selected["attempt"]}').relative_to(out))
            elif selected and 'prior' in selected:
                source = Path(selected['prior']).resolve()
                expected_source = Path(batch['prior_batches'][job['prior_index']]['path']) / 'answers' / job['path']
                if source != expected_source.resolve() or not source.is_relative_to(ROOT / 'runs'):
                    raise ValueError('Recovered source differs from frozen original job')
                prior_dest = target / 'prior-source'
                files = export_capture(source, job['prior_files'], prior_dest)
                answer_path = Path(selected['answer']).resolve()
                audit = state_row.get('audit', {})
                if not answer_path.is_relative_to(ROOT / 'runs') or sha(answer_path.read_bytes()) != audit.get('answer_sha256'):
                    raise ValueError('Audited recovered answer changed')
                if selected.get('provenance') == 'lossless_acknowledged_tool_write_extraction':
                    from benchmark.parallel_batch import recover_written_answer
                    body, receipt = recover_written_answer(config['cli'], source / 'workspace/trajectory.jsonl')
                    if body.encode('utf-8') != answer_path.read_bytes() or receipt != audit.get('extraction'):
                        raise ValueError('Lossless recovery receipt no longer verifies')
                elif selected.get('provenance') != 'legacy_final_response_capture_audited_not_relabelled':
                    raise ValueError('Unknown historical answer provenance')
                dest = target / 'recovered'
                export_capture(answer_path.parent, {'answer.md': audit['answer_sha256']}, dest)
                put(dest / 'recovery-receipt.json', clean(audit))
                selected_path = str(dest.relative_to(out))
                attempts.insert(0, {'kind': 'audited_historical_capture', 'source': source.relative_to(ROOT).as_posix(),
                    'artifacts': str(prior_dest.relative_to(out)), 'artifact_count': len(files),
                    'provenance': selected['provenance'], 'recovered_artifacts': selected_path})
            if state_row['status'] == 'completed':
                if not selected_path:
                    raise ValueError('Completed task has no selected capture')
                answers = list((out / selected_path).rglob('answer.md'))
                expected_count = 2 if job['kind'] == 'staged' else 1
                if len(answers) != expected_count or any(not p.read_text().strip() for p in answers):
                    raise ValueError('Selected answer/stage missing: ' + task_id)
            record = {'agent': agent, 'task_id': task_id, 'case_group_id': job['case_group_id'],
                'kind': job['kind'], 'repeat': job['repeat'], 'status': state_row['status'],
                'selected_artifacts': selected_path, 'attempts': attempts,
                'score': None, 'score_status': 'not_scored', 'official': False}
            put(target / 'record.json', record)
            results.append({k: v for k, v in record.items() if k != 'attempts'})
    jsonl(out / 'results.jsonl', results)
    put(out / 'configurations.json', configurations)
    put(out / 'selection.json', first)
    put(out / 'manifest.json', {'schema': 'subset-experiment-snapshot.1', 'snapshot_at': captured_at,
        'task_count_per_agent': 20, 'agent_count': len(configurations), 'expected_results': len(results),
        'completed': sum(r['status'] == 'completed' for r in results), 'scored': 0,
        'official': False, 'publication_status': 'local_draft_pending_artifact_review',
        'excluded': ['Claude Opus 5.5: removed from current cohort by owner; original records retained locally'] +
                    [a + ': excluded from this publication by owner; original records retained locally'
                     for a in index.get('excluded_agents', [])],
        'trajectory_policy': 'allowlisted text artifacts, automatic redaction, manual review still required',
        'history_scope': 'See evidence/invocations.jsonl for deduplicated reachable historical calls'})
    lines = ['# 首批公开20题实验记录', '', f'快照时间（UTC）：{captured_at}', '',
        '这是一个20题子集，不是20个子集。每配置20题、24阶段，重复次数为1。本快照尚未合并正在进行的独立评审结果，不生成排名或总均分。', '',
        '| 产品与模型配置 | 完成 | 失败 | 运行中 | 排队/其他 | 评分 |', '| --- | ---: | ---: | ---: | ---: | --- |']
    for row in configurations:
        c = row['status_counts']
        lines.append(f'| {row["agent"]} | {c.get("completed",0)}/20 | {c.get("failed",0)} | {c.get("running",0)} | {20-c.get("completed",0)-c.get("failed",0)-c.get("running",0)} | 待评分 |')
    lines += ['', '## 记录解释', '',
        'results.jsonl 始终包含每配置全部20题，失败和待执行项不被删除。records 保存选中答卷、可用轨迹、已结束尝试和复用来源。分数null表示本快照未导入评分，不是0分。不得只对成功题取平均。', '',
        'configurations.json 记录客户端、模型、认证、运行策略和冻结代码。run.json 是公开字段投影；其他文本经过自动去标识处理，artifacts.json 同时给出原文件和导出文件哈希。运行中日志、原生会话 checkpoint、凭据和HOME不导出。自动脱敏不构成人工公开审核。', '',
        '这些记录沿用原 official:false，不追溯改成预注册或独立盲测。选取首个完整答卷，复用与重试依实际策略披露，未按分数择优。不同批次的冻结执行器可能不同；按 sources 与 configurations 比较，不能假设完全相同。', '',
        '模型名是请求配置。能否确认实际模型须看每条 run.json 的 model_identity_status 和 reported_models；不报告身份不等于已验证。费用为 null 时不当作免费；Qwen 搜索辅助模型可能未包含在主模型用量中。', '',
        'evidence 保存按调用去重的历史台账及关联轨迹，包括可追溯的原始批次、重试与恢复。未知用量保持null；统计不包含无关联试跑或仍在执行的调用，不等于完整账单。', '',
        'sources/<campaign>/engine 是由历史79题冻结源树导出的公开75题副本；4题题面与细则已移除，集合清单与选择依赖哈希明确重绑。保留题目和代码不改；不再宣称整个源树逐字节等同历史。reproduce.py 仅离线准备原20题，不调用模型。', '',
        '本目录由 scripts/prepare_publication.py 生成，后续每次导出使用新目录，历史快照不可覆盖。']
    (out / 'README.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return configurations, results


def checksums(folder, relative_path='checksums.json'):
    put(folder / relative_path, {p.relative_to(folder).as_posix(): sha(p.read_bytes())
        for p in sorted(folder.rglob('*')) if p.is_file() and p.name != 'checksums.json'})



def repository(out, selected, cohort_agents=None):
    """Public75 code/data payload, separate from the live historical working tree."""
    from benchmark.reproduction import engine_files
    from benchmark.release import ROOT_FILES, CONFIG_FILES
    from scripts.publication_scope import project, rebind_selection
    files = engine_files(ROOT)
    for folder in ('data/dev', 'data/staged-dev', 'data/longitudinal', 'examples/public-smoke'):
        for path in (ROOT / folder).rglob('*.json'):
            files[path.relative_to(ROOT).as_posix()] = sha(path.read_bytes())
    for path in (ROOT / 'docs').glob('*.md'):
        files[path.relative_to(ROOT).as_posix()] = sha(path.read_bytes())
    for name in ('README.md', 'README.zh-CN.md', 'CITATION.cff', 'CALIBRATION-STATUS.md'):
        path = ROOT / 'docs/huggingface' / name
        files[path.relative_to(ROOT).as_posix()] = sha(path.read_bytes())
    # Export only the generated assets declared by each source-bound figure set.
    figure_manifests = sorted((ROOT / 'docs/figures').glob('*/manifest.json'))
    for path in figure_manifests:
        manifest = read(path)
        if manifest.get('schema') != 'benchmark-figures.1':
            raise ValueError('Unknown figure manifest: ' + str(path))
        for name, expected in manifest['source_files_sha256'].items():
            if sha(inside(ROOT, name).read_bytes()) != expected:
                raise ValueError('Figure source changed; regenerate figures: ' + name)
        guide_path = inside(ROOT, manifest.get('guide_path', 'docs/benchmark-guide.md'))
        if sha(guide_path.read_bytes()) != manifest['guide_sha256']:
            raise ValueError('Figure guide changed; regenerate figures')
        for name, expected in manifest['files'].items():
            asset = inside(path.parent, name)
            if asset.suffix not in ('.png', '.svg') or sha(asset.read_bytes()) != expected:
                raise ValueError('Invalid or changed figure asset: ' + name)
            files[asset.relative_to(ROOT).as_posix()] = expected
        files[path.relative_to(ROOT).as_posix()] = sha(path.read_bytes())
    # Keep README-linked analysis snapshots with their verified chart/data assets.
    # Only the exporter's fixed report outputs are eligible; raw reviews stay local.
    result_names = {'README.md', 'README.zh-CN.md', 'results.json', 'verification.json',
                    'scores.csv', 'pending-review.md', 'score-bounds.svg', 'score-bounds.png',
                    'task-scores.svg', 'task-scores.png', 'execution-progress.json'}
    result_files = {}
    for path in sorted((ROOT / 'experiments').glob('subset20-results-*/checksums.json')):
        manifest = read(path)
        data = read(path.parent / 'results.json')
        if cohort_agents is not None and {r['agent'] for r in data['summary']} != set(cohort_agents):
            continue  # Historical cohorts remain local, outside this publication.
        if data.get('schema') != 'benchmark-review-analysis.1' or not {
                t['task_id'] for t in data['tasks']} <= set(selected['task_ids']):
            raise ValueError('Review result outside the public selection: ' + str(path))
        for name, expected in manifest['files'].items():
            asset = inside(path.parent, name)
            if name not in result_names or sha(asset.read_bytes()) != expected:
                raise ValueError('Invalid or changed review result: ' + name)
            result_files[asset.relative_to(ROOT).as_posix()] = expected
        result_files[path.relative_to(ROOT).as_posix()] = sha(path.read_bytes())
    for name in CONFIG_FILES:
        path = ROOT / 'config' / name
        if path.is_file():
            files['config/' + name] = sha(path.read_bytes())
    files['benchmark/leaderboard.html'] = sha((ROOT / 'benchmark/leaderboard.html').read_bytes())
    for path in (ROOT / 'tests').glob('test_*.py'):
        files[path.relative_to(ROOT).as_posix()] = sha(path.read_bytes())
    report = project(files, ROOT, out, selected)
    for name, expected in result_files.items():
        raw = inside(ROOT, name).read_bytes()
        if sha(raw) != expected:
            raise ValueError('Review result changed during export: ' + name)
        target = inside(out, name)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        report['original_files'][name] = expected
        report['exported_files'][name] = expected
    for name in ROOT_FILES:
        (out / name).write_bytes((ROOT / name).read_bytes())
    for path in (ROOT / 'config/selections').glob('*.json'):
        data = read(path)
        if 'source_files_sha256' in data:
            data = rebind_selection(data, out)
        put(out / 'config/selections' / path.name, data)
    # Selection files were rebound to the public collection above. Keep both
    # source identities so the copied diagrams remain verifiable in that tree.
    for path in figure_manifests:
        name = path.relative_to(ROOT).as_posix()
        manifest = read(path)
        rebound = {n: sha(inside(out, n).read_bytes())
                   for n in manifest['source_files_sha256']}
        if rebound != manifest['source_files_sha256']:
            manifest['historical_source_files_sha256'] = manifest['source_files_sha256']
            manifest['source_files_sha256'] = rebound
            manifest['publication_adjustment'] = 'Source bindings updated for public75; figure images unchanged'
            put(out / name, manifest)
            report['exported_files'][name] = sha((out / name).read_bytes())
            report['changed'][name] = {'original_sha256': files[name],
                'export_sha256': report['exported_files'][name],
                'reason': manifest['publication_adjustment']}
    put(out / 'release/publication/publication-source-manifest.json', report)
    for name in ('review-status-75.json', 'review-status-200.json', 'content-audit-75.json'):
        put(out / 'release/publication' / name, read(ROOT / 'release/publication' / name))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--index', type=Path, default=ROOT / 'config/selections/public-dev20-cohort-20261009-kimi.json')
    args = parser.parse_args()
    out = args.out.resolve()
    if out.exists():
        raise ValueError('Destination already exists; use a new snapshot directory')
    first = load_selection(ROOT / 'config/selections/public-dev-20-v1.json')
    selected = load_selection(ROOT / 'config/selections/public-dev-75-v1.json')
    if selected['task_count'] != 75 or first['task_count'] != 20 or not set(first['task_ids']) <= set(selected['task_ids']):
        raise ValueError('Unexpected release scope')
    status = read(ROOT / 'release/publication/review-status-75.json')
    if status['selection_sha256'] != sha((ROOT / 'config/selections/public-dev-75-v1.json').read_bytes()):
        raise ValueError('Review status is for another selection')
    index = read(args.index)
    index['campaign_by_agent'] = {agent: str(Path(path) if Path(path).is_absolute() else ROOT / path)
                                  for agent, path in index['campaign_by_agent'].items()}
    if index['selection_sha256'] != sha((ROOT / 'config/selections/public-dev-20-v1.json').read_bytes()):
        raise ValueError('Index selection mismatch')
    captured_at = datetime.now(timezone.utc).isoformat()
    out.mkdir(parents=True)
    # A failed export has no COMPLETE marker and is never a publishable result.
    dataset(out / 'huggingface', selected, first, status)
    repository(out / 'github', selected, index['campaign_by_agent'])
    configs, results = experiment(out / 'github' / 'experiments' / 'subset20-20261009', index, first, captured_at)
    experiment_dir = out / 'github' / 'experiments' / 'subset20-20261009'
    put(experiment_dir / 'cohort.json', read(args.index))
    put(experiment_dir / 'review-status.json', status)
    put(experiment_dir / 'review-status-200.json', read(ROOT / 'release/publication/review-status-200.json'))
    content_audit = ROOT / 'release/publication/content-audit-75.json'
    if content_audit.is_file():
        audit = read(content_audit)
        if audit['selection_sha256'] != status['selection_sha256']:
            raise ValueError('Content audit belongs to another selection')
        put(experiment_dir / 'content-audit-75.json', audit)
    from scripts.publication_evidence import ledger, scan
    ledger(index, first, experiment_dir / 'evidence')
    put(experiment_dir / 'evidence/privacy-scan.json', scan(experiment_dir / 'evidence/history'))
    put(experiment_dir / 'privacy-scan.json', scan(experiment_dir / 'records'))
    put(experiment_dir / 'sources/privacy-scan.json', scan(experiment_dir / 'sources'))
    (experiment_dir / 'reproduce.py').write_bytes((ROOT / 'scripts/publication_reproduce.py').read_bytes())
    for name in ('LICENSE', 'LICENSE-DATA'):
        (experiment_dir / name).write_bytes((ROOT / name).read_bytes())
    checksums(out / 'huggingface')
    checksums(out / 'github', 'release/publication/checksums.json')
    put(out / 'COMPLETE.json', {'created_at': captured_at, 'local_only': True, 'uploaded': False,
        'dataset_tasks': 75, 'experiment_tasks_per_agent': 20, 'agents': len(configs),
        'completed': sum(r['status'] == 'completed' for r in results), 'scored': 0,
        'publication_approved': False, 'review_required': ['content-bound redistribution approval',
            'manual trajectory/privacy review', 'disclose history/cost provenance gaps']})
    print(json.dumps(read(out / 'COMPLETE.json'), ensure_ascii=False))


if __name__ == '__main__':
    main()
