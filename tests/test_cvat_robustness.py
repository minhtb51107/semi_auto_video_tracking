"""Fault injection only: never connect to a real CVAT server."""
import copy
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from cvat_integration import (Client, IntegrationError, digest, execute, main,
                              make_plan, read, reconcile)
from test_cvat_integration import FakeAPI, fixture


class FaultAPI(FakeAPI):
    url = 'https://example.invalid'

    def __init__(self):
        super().__init__()
        self.metadata = fixture()[1]
        self.fail_at = None

    def snapshot(self, task, job):
        return copy.deepcopy(self.metadata)

    def request(self, method, path, payload=None):
        if method == 'POST' and self.fail_at == len(self.issues):
            self.fail_at = None
            raise IntegrationError('Injected network failure before next POST commits')
        return super().request(method, path, payload)


class RobustnessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.data, self.snapshot, self.images = fixture()
        seed = self.data['events'][0]
        self.data['events'] = [dict(copy.deepcopy(seed), event_id=f'E{i:06d}') for i in range(1, 21)]
        self.source = self.root/'events.json'
        self.source.write_text(json.dumps(self.data))
        self.out = self.root/'out'
        self.api = FaultAPI()
        self.args = ['--events', str(self.source), '--images', 'fixture-images', '--sequence', 'fixture',
                     '--task', '1', '--job', '2', '--out', str(self.out)]

    def run_cli(self, mode):
        with patch('cvat_integration.Client', return_value=self.api), patch('cvat_integration.image_inventory', return_value=self.images), redirect_stdout(io.StringIO()):
            return main(self.args+[mode]+(['--confirm-test-task', '1'] if mode == '--push' else []))

    def prepare(self):
        self.assertEqual(self.run_cli('--dry-run'), 0)

    def test_partial_7_of_20_checkpoint_retry_13_no_duplicates(self):
        self.prepare(); self.api.fail_at = 7
        self.assertEqual(self.run_cli('--push'), 2)
        self.assertEqual(len(self.api.issues), 7)
        self.assertEqual(len(read(self.out/'state.json')['mapping']), 7)
        self.assertEqual(self.run_cli('--push'), 0)
        result = read(self.out/'push.json')
        self.assertEqual(sum(a['action'] == 'SKIP_EXISTING' for a in result['actions']), 7)
        self.assertEqual(sum(a['action'] == 'CREATE' for a in result['actions']), 13)
        self.assertEqual(len(self.api.issues), 20)
        self.assertEqual(len({c['message'].split('\n')[0] for c in self.api.comments}), 20)
        self.assertTrue(result['annotations_unchanged'])

    def test_lost_state_recovers_existing_remote_resolved_issues(self):
        self.prepare(); self.assertEqual(self.run_cli('--push'), 0)
        (self.out/'state.json').unlink(); self.api.issues[0]['resolved'] = True
        self.assertEqual(self.run_cli('--push'), 0)
        result = read(self.out/'push.json')
        self.assertTrue(all(a['action'] == 'SKIP_EXISTING' for a in result['actions']))
        self.assertEqual(len(read(self.out/'state.json')['mapping']), 20)
        self.assertTrue(self.api.issues[0]['resolved'])
        self.assertEqual(len(self.api.issues), 20)

    def test_lost_response_before_checkpoint_reconciles(self):
        self.prepare(); self.api.fail_after_create = True
        self.assertEqual(self.run_cli('--push'), 2)
        self.assertEqual(len(self.api.issues), 1)
        self.assertEqual(self.run_cli('--push'), 0)
        self.assertEqual(len(self.api.issues), 20)
        self.assertEqual(read(self.out/'push.json')['actions'][0]['action'], 'SKIP_EXISTING')

    def test_corrupt_state_safe_fail_preserves_bytes(self):
        self.prepare()
        for value in ['{broken', 'null', '{"scope":"bad","mapping":{}}']:
            (self.out/'state.json').write_text(value)
            self.assertEqual(self.run_cli('--push'), 2)
            self.assertEqual((self.out/'state.json').read_text(), value)
            self.assertEqual(len(self.api.issues), 0)

    def test_source_drift_before_first_push_preserves_approved_plan(self):
        self.prepare(); original = (self.out/'request_plan.json').read_bytes()
        self.data['events'][0]['track_id'] = 999
        self.source.write_text(json.dumps(self.data))
        self.assertEqual(self.run_cli('--push'), 2)
        self.assertEqual((self.out/'request_plan.json').read_bytes(), original)
        self.assertEqual(len(self.api.issues), 0)

    def test_raw_source_bytes_changed_even_same_semantics_rejected(self):
        self.prepare(); self.source.write_text(json.dumps(self.data, indent=4))
        self.assertEqual(self.run_cli('--push'), 2)
        self.assertEqual(len(self.api.issues), 0)

    def test_corrupt_source_lock_and_missing_dryrun_fail(self):
        self.assertEqual(self.run_cli('--push'), 2)
        self.prepare(); (self.out/'source_lock.json').write_text('invalid')
        self.assertEqual(self.run_cli('--push'), 2)
        self.assertEqual((self.out/'source_lock.json').read_text(), 'invalid')
        self.assertEqual(len(self.api.issues), 0)

    def test_remote_orphan_marker_detects_dropped_event_without_local_state(self):
        self.prepare(); self.assertEqual(self.run_cli('--push'), 0)
        plan = read(self.out/'request_plan.json'); plan['items'].pop()
        with self.assertRaises(IntegrationError): reconcile(plan, self.api.issues, self.api.comments)

    def test_task_job_frame_and_image_mismatch_no_post(self):
        self.prepare()
        changes = [('job', 'task_id', 10), ('meta', 'size', 4), ('meta', 'frame_filter', 'step=2'),
                   ('meta', 'deleted_frames', [1]), ('meta', 'frames', []), ('meta', 'frames', self.images[::-1])]
        for section, field, value in changes:
            self.api.metadata = copy.deepcopy(self.snapshot)
            self.api.metadata[section][field] = value
            self.assertEqual(self.run_cli('--push'), 2)
            self.assertEqual(len(self.api.issues), 0)

    def test_server_unavailable_timeout_401_403_404_no_retry(self):
        client = Client('https://example.invalid', 'fixture-token-not-real')
        errors = [URLError('offline'), TimeoutError()] + [HTTPError(client.url, code, 'fixture', {}, None) for code in (401, 403, 404)]
        for error in errors:
            with patch.object(client.opener, 'open', side_effect=error) as opened:
                with self.assertRaises(IntegrationError): client.request('GET', '/api/tasks/1')
                self.assertEqual(opened.call_count, 1)

    def test_cli_metadata_api_failure_no_post_no_plan_rewrite(self):
        self.prepare(); before = (self.out/'request_plan.json').read_bytes()
        with patch.object(self.api, 'snapshot', side_effect=IntegrationError('CVAT HTTP 404')):
            self.assertEqual(self.run_cli('--push'), 2)
        self.assertEqual(len(self.api.issues), 0)
        self.assertEqual((self.out/'request_plan.json').read_bytes(), before)

    def test_unexpected_remote_schema_no_post(self):
        self.prepare()
        for path, rows in [('/api/issues', [None]), ('/api/issues', [dict(id=1)]), ('/api/comments', [None]), ('/api/comments', [dict(id=1, issue=1, message=None)])]:
            original = self.api.listing
            with patch.object(self.api, 'listing', side_effect=lambda p, **kw: rows if p == path else original(p, **kw)):
                self.assertEqual(self.run_cli('--push'), 2)
            self.assertEqual(len(self.api.issues), 0)

    def test_unexpected_metadata_schema_no_post(self):
        self.api.metadata = dict(task=[], job={}, meta={})
        self.assertEqual(self.run_cli('--dry-run'), 2)
        self.assertEqual(len(self.api.issues), 0)

    def test_malformed_duplicate_out_of_range_events_no_post(self):
        self.prepare()
        for events in [[None], self.data['events']*2, [dict(self.data['events'][0], context_end=6)]]:
            self.source.write_text(json.dumps(dict(schema_version=2, events=events)))
            self.assertEqual(self.run_cli('--push'), 2)
            self.assertEqual(len(self.api.issues), 0)

    def test_stale_lock_no_state_or_plan_mutation(self):
        self.prepare(); original = (self.out/'request_plan.json').read_bytes()
        (self.out/'push.lock').write_text('interrupted-process')
        self.assertEqual(self.run_cli('--push'), 2)
        self.assertEqual((self.out/'request_plan.json').read_bytes(), original)
        self.assertEqual((self.out/'push.lock').read_text(), 'interrupted-process')
        self.assertEqual(len(self.api.issues), 0)

    def test_local_inventory_drift_safe_fail(self):
        self.prepare(); self.images[0]['sha256'] = 'different-image-bytes'
        self.assertEqual(self.run_cli('--push'), 2)
        self.assertEqual(len(self.api.issues), 0)


if __name__ == '__main__':
    unittest.main()
