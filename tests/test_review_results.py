import unittest
import json
from pathlib import Path
import tempfile

from scripts.export_review_results import aggregate, apply_execution_progress, execution_paths, select_cohort, merge_review_collections, tree_hashes


def row(task_id, status='completed', score=80, bounds=None, pending=None):
    return {'task_id': task_id, 'review_status': status, 'score': score,
            'score_interval': bounds if bounds is not None else [score, score],
            'pending_nodes': pending or []}


class ReviewResultsTests(unittest.TestCase):
    def test_service_recovery_preserves_partial_files_and_rejects_changed_protocol(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            def put(name, value):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(value))
            record = {'packet': 'p1', 'packet_hashes': {}, 'task_id': 't1'}
            manifest = {'packets': [record], 'source_code_sha256': {}}
            request = {'model': 'fixed', 'prompt': 'original', 'packet_hashes': {}, 'auth': 'subscription'}
            put('executions/p1/status.json', {'status': 'failed', 'issue': 'CLI exit 1'})
            put('executions/p1/events.jsonl', {'type': 'turn.failed', 'error': {'message': '503 Service Unavailable'}})
            put('executions/p1/judgment.json', {'partial': True})
            put('executions/p1/request.json', request)
            put('retry/review-manifest.json', {'packets': [record]})
            for prefix in ('', 'retry/'):
                put(prefix + 'judge-settings.json', {'model': 'fixed'})
                put(prefix + 'run_reviews.py', 'same runner')
            put('retry/executions/p1/request.json', request)
            recovery = {'schema': 'review-service-recovery.1', 'same_model_prompt_effort_inputs': True,
                        'score_selection': False, 'packets': {'p1': {
                            'original_execution': 'executions/p1', 'new_execution': 'retry/executions/p1',
                            'original_files': tree_hashes(root / 'executions/p1')}}}
            put('service-recovery-manifest.json', recovery)
            self.assertEqual(execution_paths(root, manifest, {})['p1'], root / 'retry/executions/p1')
            self.assertEqual(json.loads((root / 'executions/p1/judgment.json').read_text()), {'partial': True})
            put('retry/executions/p1/request.json', dict(request, prompt='different'))
            with self.assertRaisesRegex(ValueError, 'native request changed'):
                execution_paths(root, manifest, {})
            put('retry/executions/p1/request.json', request)
            put('executions/p1/judgment.json', {'altered': True})
            with self.assertRaisesRegex(ValueError, 'failure changed'):
                execution_paths(root, manifest, {})
            put('executions/p1/score.json', {'score': 50})
            recovery['packets']['p1']['original_files'] = tree_hashes(root / 'executions/p1')
            put('service-recovery-manifest.json', recovery)
            with self.assertRaisesRegex(ValueError, 'accepted review'):
                execution_paths(root, manifest, {})

    def test_additional_configuration_requires_same_tasks_scorer_and_reviewer(self):
        import copy
        def inputs(agent):
            data = {'selection_id': 'dev20', 'selection_sha256': 'selection', 'task_count': 20,
                    'tasks': ['same-tasks'], 'reviewer': {'native': {'model': 'fixed'}},
                    'review_source': agent, 'generated_at': '2026-10-09',
                    'summary': [{'agent': agent}], 'rows': [{'agent': agent, 'score': 80}], 'pending': []}
            audit = {'scoring_code_sha256': {'score.py': 'same'}, 'verified_judgments': 1,
                     'records': [{'agent': agent}]}
            return data, audit
        base, audit = inputs('original'); extra, proof = inputs('added')
        merged, evidence = merge_review_collections(base, audit, extra, proof)
        self.assertEqual([r['score'] for r in merged['rows']], [80, 80])
        self.assertEqual(len(base['rows']), 1)
        self.assertEqual(evidence['verified_judgments'], 2)
        self.assertEqual([r['review_source'] for r in evidence['records']], ['original', 'added'])
        for field, value in [('selection_sha256', 'other'), ('tasks', ['different']),
                             ('reviewer', {'native': {'model': 'different'}}),
                             ('summary', [{'agent': 'original'}])]:
            changed = copy.deepcopy(extra); changed[field] = value
            with self.assertRaises(ValueError):
                merge_review_collections(base, audit, changed, proof)
        with self.assertRaisesRegex(ValueError, 'another scorer'):
            merge_review_collections(base, audit, extra, dict(proof, scoring_code_sha256={}))

    def test_later_execution_does_not_score_unreviewed_answers_or_replace_reviewed_input(self):
        import copy
        rows = [dict(row('a', score=80), agent='qwen'),
                dict(row('b', status='not_started', score=None), agent='qwen')]
        data = {'selection_id': 'dev20', 'selection_sha256': 'selection', 'task_count': 2,
                'tasks': [{'task_id': 'a'}, {'task_id': 'b'}], 'rows': rows,
                'summary': [dict(aggregate(rows, {}, ['a', 'b']), agent='qwen', snapshot_answers=1)]}
        audit = {'records': [{'agent': 'qwen', 'task_id': 'a',
                              'packet_hashes': {'answer.md': 'a' * 64}}]}
        progress = {'schema': 'review-execution-progress.1', 'selection_id': 'dev20',
                    'selection_sha256': 'selection', 'agent': 'qwen',
                    'records': [{'task_id': tid, 'status': 'completed', 'mode': 'original_campaign',
                                 'answer_sha256': tid * 64} for tid in ('a', 'b')]}
        original = copy.deepcopy(data)
        apply_execution_progress(data, audit, progress)
        self.assertEqual(data['summary'][0]['current_answers'], 2)
        self.assertEqual(data['summary'][0]['reviewed'], 1)
        self.assertIsNone(data['summary'][0]['mean'])
        self.assertIsNone(data['summary'][0]['score_bounds'])
        self.assertEqual([r['score'] for r in data['rows']], [80, None])
        progress['records'][0]['answer_sha256'] = 'c' * 64
        with self.assertRaisesRegex(ValueError, 'replace a reviewed answer'):
            apply_execution_progress(original, audit, progress)
        progress['records'][0]['answer_sha256'] = 'a' * 64
        progress['records'][1]['task_id'] = 'a'
        with self.assertRaisesRegex(ValueError, 'Missing or duplicate'):
            apply_execution_progress(original, audit, progress)

    def test_publication_exclusion_preserves_source_scores_and_removes_all_agent_rows(self):
        entries = [{'agent': 'keep', 'score': 80}, {'agent': 'exclude', 'score': 90}]
        data = {key: list(entries) for key in ('summary', 'rows', 'pending')}
        audit = {'records': list(entries), 'verified_judgments': 2}
        selected, evidence = select_cohort(data, audit, ['keep'])
        for key in ('summary', 'rows', 'pending'):
            self.assertEqual(selected[key], [entries[0]])
            self.assertEqual(len(data[key]), 2)
        self.assertEqual(evidence['records'], [entries[0]])
        self.assertEqual(evidence['verified_judgments'], 1)
        self.assertEqual(audit['verified_judgments'], 2)
        for agents in ([], ['unknown']):
            with self.assertRaises(ValueError):
                select_cohort(data, audit, agents)

    def test_timeout_recovery_is_selected_with_original_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            def put(name, value):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(value))
            record = {'packet': 'p1', 'packet_hashes': {}, 'task_id': 't1'}
            manifest = {'packets': [record], 'source_code_sha256': {}}
            put('executions/p1/status.json', {'status': 'failed', 'error_type': 'TimeoutExpired'})
            put('timeout-recovery-manifest.json', {
                'same_model_prompt_effort_inputs': True, 'score_selection': False,
                'packets': {'p1': {'original_execution': 'executions/p1',
                    'new_execution': 'retry/executions/p1', 'original_timeout_seconds': 1200,
                    'recovery_timeout_seconds': 2400}}})
            put('retry/review-manifest.json', {'packets': [record]})
            put('judge-settings.json', {'model': 'fixed', 'timeout_per_answer_seconds': 1200})
            put('retry/judge-settings.json', {'model': 'fixed', 'timeout_per_answer_seconds': 2400})
            bindings = {}
            self.assertEqual(execution_paths(root, manifest, bindings)['p1'], root / 'retry/executions/p1')
            self.assertIn('timeout-recovery-manifest.json', bindings)
            put('retry/judge-settings.json', {'model': 'different', 'timeout_per_answer_seconds': 2400})
            with self.assertRaisesRegex(ValueError, 'reviewer settings changed'):
                execution_paths(root, manifest, {})
            put('executions/p1/judgment.json', {'score': 20})
            with self.assertRaisesRegex(ValueError, 'existing judgment'):
                execution_paths(root, manifest, {})

    def test_pending_evidence_keeps_fixed_denominator_without_point_mean(self):
        result = aggregate([row('a', score=100),
                            row('b', score=None, bounds=[20, 60], pending=['r1'])], {}, ['a', 'b'])
        self.assertEqual(result['score_bounds'], [60, 80])
        self.assertIsNone(result['mean'])
        self.assertTrue(result['review_complete'])
        self.assertFalse(result['complete'])
        self.assertEqual((result['scored'], result['pending']), (1, 1))

    def test_unfinished_review_does_not_average_only_successful_tasks(self):
        for status in ('running', 'failed', 'not_started', 'input_error'):
            with self.subTest(status=status):
                result = aggregate([row('a'), row('b', status=status, score=None)], {}, ['a', 'b'])
                self.assertIsNone(result['score_bounds'])
                self.assertIsNone(result['mean'])
                self.assertFalse(result['review_complete'])

    def test_complete_numeric_scores_use_equal_task_weights(self):
        result = aggregate([row('a', score=40), row('b', score=100)], {}, ['a', 'b'])
        self.assertEqual(result['mean'], 70)
        self.assertEqual(result['score_bounds'], [70, 70])
        self.assertTrue(result['complete'])

    def test_missing_or_duplicate_task_identity_is_rejected(self):
        for rows, ids in (([row('a')], ['a', 'b']),
                          ([row('a'), row('a')], ['a', 'b']),
                          ([row('a')], ['a', 'a']), ([], [])):
            with self.subTest(ids=ids):
                with self.assertRaises(ValueError):
                    aggregate(rows, {}, ids)


if __name__ == '__main__':
    unittest.main()
