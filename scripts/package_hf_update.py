#!/usr/bin/env python3
"""Build a public75 HF update from a verified release and scoped corrections."""
import argparse
import json
from pathlib import Path
import shutil
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from benchmark.core import digest, input_hash, query_prompt, validate_task
from scripts.export_review_results import read, sha, put, tree_hashes, verify_hashes, require
from scripts.publication_evidence import PATTERNS


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path, required=True)
    parser.add_argument('--base-commit', required=True)
    parser.add_argument('--results', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    base, report, out = (p.resolve() for p in (args.base, args.results, args.out))
    require(not out.exists(), 'Use a new output directory')
    verify_hashes(base, read(base / 'checksums.json'))
    verify_hashes(report, read(report / 'checksums.json')['files'])
    original_scope = read(base / 'selection-75.json')
    allowed = set(original_scope['task_ids'])
    require(len(allowed) == 75, 'Expected exactly 75 public tasks')
    shutil.copytree(base, out)
    revision = '1.0.1+adjudications-20261010'
    corrected = {}
    for tid in ('N06-03', 'N14-03'):
        folder = ROOT / 'release/errata/department-identities-20261010' / tid
        task, rubric = read(folder / 'task.json'), read(folder / 'rubric.json')
        old_task = read(base / 'tasks' / tid / 'task.json')
        validate_task(task, rubric, 'dev')
        require(input_hash(task) == input_hash(old_task), 'Candidate input changed')
        corrected[tid] = {'task': digest(task), 'rubric': digest(rubric)}
        put(out / 'tasks' / tid / 'task.json', task)
        put(out / 'tasks' / tid / 'rubric.json', rubric)
    for filename in ('single-stage.jsonl', 'staged.jsonl', 'rubrics.jsonl'):
        rows = [json.loads(line) for line in (out / filename).read_text().splitlines()]
        for row in rows:
            tid = row['task_id']
            require(tid in allowed, 'Out-of-scope task')
            if tid in corrected:
                task = read(out / 'tasks' / tid / 'task.json')
                rubric = read(out / 'tasks' / tid / 'rubric.json')
                row['rubric_sha256'] = digest(rubric)
                if 'task_json' in row:
                    require(row['input'] == query_prompt(task), 'Visible prompt changed')
                    row.update(task_json=json.dumps(task, ensure_ascii=False), task_sha256=digest(task))
                else:
                    row['rubric_json'] = json.dumps(rubric, ensure_ascii=False)
        (out / filename).write_text(''.join(json.dumps(row, ensure_ascii=False, sort_keys=True) + '\n' for row in rows))
    for filename in ('selection-20.json', 'selection-40.json', 'selection-75.json'):
        selection = read(out / filename)
        selection['release_revision'] = revision
        selection['prior_hf_source_files_sha256'] = selection['source_files_sha256']
        selection['reproduction_adjustment'] = 'HF paths and byte hashes bind this corrected release; original experiment selections remain frozen in their run packages. Candidate-visible inputs are unchanged.'
        bindings = {'scoring.md': sha(out / 'scoring.md')}
        for row in selection['tasks']:
            tid = row['task_id']
            require(tid in allowed, 'Selection outside public75')
            for kind in ('task', 'rubric'):
                name = f'tasks/{tid}/{kind}.json'
                row[kind + '_path'] = name
                row['fingerprints'][kind] = digest(read(out / name))
                bindings[name] = sha(out / name)
        selection['source_files_sha256'] = bindings
        put(out / filename, selection)
    result_dest = out / 'results' / report.name
    shutil.copytree(report, result_dest)
    for folder in sorted((ROOT / 'release/errata').iterdir()):
        if folder.is_dir():
            checks = read(folder / 'checksums.json')
            verify_hashes(folder, checks.get('files', checks))
            copied = out / 'errata' / folder.name
            shutil.copytree(folder, copied)
            # Historic reports are already public at this immutable GitHub revision.
            readme = copied / 'README.md'
            body = readme.read_text().replace('](../../../experiments/',
                '](https://github.com/yeyuxin777/baoyan-agent-benchmark/blob/1ad32258a995b05f2b8640286ea08efab5eabbc0/experiments/')
            if body != readme.read_text():
                readme.write_text(body)
                hashes = checks.get('files', checks)
                hashes['README.md'] = sha(readme)
                put(copied / 'checksums.json', checks)

    data = read(report / 'results.json')
    for zh in (False, True):
        name = 'README.zh-CN.md' if zh else 'README.md'
        card = (ROOT / 'docs/huggingface' / name).read_text()
        for old, new in (('../scoring.md','scoring.md'), ('../../LICENSE-DATA','LICENSE'),
                         ('../../config/selections/public-dev-75-v1.json','selection-75.json')):
            card = card.replace('](' + old + ')', '](' + new + ')')
        (out / name).write_text(card)
    manifest = read(out / 'manifest.json')
    manifest.update(schema='selected-hf-release.2', release_revision=revision,
                    previous_hf_commit=args.base_commit, selection_sha256=sha(out / 'selection-75.json'),
                    review_binding_verification='All 75 candidate-visible inputs preserved; N06-03 and N14-03 organizer references corrected under owner-approved errata. Historical teacher calibration status retained; no new teacher review claimed.',
                    corrected_fingerprints=corrected, latest_results=f'results/{report.name}/results.json',
                    results_sha256=sha(report / 'results.json'), numeric_answers=sum(r['scored'] for r in data['summary']),
                    pending_answers=sum(r['pending'] for r in data['summary']), pending_nodes=len(data['pending']),
                    candidate_reruns=0, new_independent_model_reviews=0,
                    publication_authorization='Explicit owner instruction to synchronize corrections and results to Hugging Face')
    put(out / 'manifest.json', manifest)
    # Validate task/rubric rows against canonical files, all selection bindings and public scope.
    for filename, count in [('single-stage.jsonl',61), ('staged.jsonl',14), ('rubrics.jsonl',75)]:
        rows = [json.loads(line) for line in (out / filename).read_text().splitlines()]
        require(len(rows) == len({r['task_id'] for r in rows}) == count, 'Invalid row count')
        for row in rows:
            tid = row['task_id']; task = read(out / 'tasks' / tid / 'task.json'); rubric = read(out / 'tasks' / tid / 'rubric.json')
            require(row['rubric_sha256'] == digest(rubric), 'Rubric row hash mismatch')
            if 'task_json' in row:
                require(json.loads(row['task_json']) == task and row['task_sha256'] == digest(task), 'Task row mismatch')
                if 'input' in row:
                    require(row['input'] == query_prompt(task), 'Prompt mismatch')
                else:
                    require(json.loads(row['stages_json']) == task['stages'], 'Stages changed')
            else:
                require(json.loads(row['rubric_json']) == rubric, 'Rubric JSON mismatch')
    require({p.name for p in (out / 'tasks').iterdir()} == allowed, 'Unexpected canonical task')
    for filename in ('selection-20.json', 'selection-40.json', 'selection-75.json'):
        selection = read(out / filename)
        verify_hashes(out, selection['source_files_sha256'])
        for row in selection['tasks']:
            for kind in ('task', 'rubric'):
                require(digest(read(out / row[kind + '_path'])) == row['fingerprints'][kind], 'Selection fingerprint mismatch')
    for path in out.rglob('*'):
        if not path.is_file() or path.name == 'checksums.json':
            continue
        body = path.read_text()
        hits = [name for name, pattern in PATTERNS.items() if pattern.search(body)]
        require(not hits, 'Public boundary scan: ' + str(path.relative_to(out)) + ' / ' + ', '.join(hits))
    hashes = tree_hashes(out); hashes.pop('checksums.json', None)
    put(out / 'checksums.json', hashes)
    verify_hashes(out, hashes)
    print(json.dumps({'out':str(out),'files':len(hashes)+1,'tasks':75,'numeric':manifest['numeric_answers'],
                      'pending':manifest['pending_answers'],'private_tasks':0},ensure_ascii=False))


if __name__ == '__main__':
    main()
