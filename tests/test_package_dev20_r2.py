import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import package_dev20_r2 as package


class PackageDev20R2Tests(unittest.TestCase):
    def test_restored_stage_is_counted_once_and_conflicts_are_rejected(self):
        call = {'invocation_id': 'same-stage', 'agent': package.AGENT,
                'task_id': 'N08-02', 'stage_id': 'S0', 'started_at': '2026-10-09T15:10:00Z',
                'finished_at': '2026-10-09T15:13:00Z', 'elapsed_seconds': 180,
                'status': 'completed', 'event_sha256': 'original-events',
                'usage': {'input_tokens': 100, 'output_tokens': 20, 'cost_usd': None},
                'aliases': [{'source': 'original'}], 'evidence': 'original/history'}
        restored = copy.deepcopy(call)
        restored.update(aliases=[{'source': 'restored'}], evidence='restored/history')
        result = package.merge_invocations([call, restored])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['usage']['input_tokens'], 100)
        self.assertIsNone(result[0]['usage']['cost_usd'])
        self.assertEqual(len(result[0]['aliases']), 2)
        self.assertEqual(result[0]['evidence_aliases'], ['original/history', 'restored/history'])
        restored['usage']['input_tokens'] = 101
        with self.assertRaisesRegex(ValueError, 'Conflicting invocation'):
            package.merge_invocations([call, restored])

    def test_all_agents_get_scores_and_pending_stays_pending(self):
        rows = [{'agent': 'old-agent', 'task_id': 'A', 'score': None, 'score_status': 'not_scored'},
                {'agent': package.AGENT, 'task_id': 'B', 'score': 90}]
        scores = {('old-agent', 'A'): {'score': None, 'score_status': 'pending_evidence',
                    'review_status': 'completed', 'score_interval': [70, 75], 'pending_nodes': ['x']},
                  (package.AGENT, 'B'): {'score': 90, 'score_status': 'scored_draft',
                    'review_status': 'completed', 'score_interval': [90, 90], 'pending_nodes': []}}
        package.attach_scores(rows, scores)
        for row in rows:
            for field, value in scores[row['agent'], row['task_id']].items():
                self.assertEqual(row[field], value)

    def test_same_metadata_basename_resolves_to_distinct_exports(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(package, 'ROOT', Path(temp)):
            root = Path(temp)
            base = root / 'export'
            receipts = []
            for campaign in ('first', 'recovery'):
                source = root / campaign / 'progress.json'
                source.parent.mkdir()
                source.write_text('{"status":"completed"}')
                receipts.append(package.metadata(source, base / campaign / source.name, relative_to=base))
            self.assertEqual(len({r['path'] for r in receipts}), 2)
            for receipt in receipts:
                self.assertEqual(package.sha((base / receipt['path']).read_bytes()), receipt['export_sha256'])


if __name__ == '__main__':
    unittest.main()
