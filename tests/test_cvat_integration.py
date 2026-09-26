import copy
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import URLError, HTTPError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from cvat_integration import (Client, IntegrationError, execute, frame_mapping, main,
                              load_dotenv, make_plan, parse_events, reconcile, writer_lock)


def fixture():
    images = [dict(name=f'{i:06d}.jpg', width=100, height=50) for i in range(1, 6)]
    snapshot = dict(task=dict(id=1, dimension='2d'), job=dict(id=2, task_id=1, type='annotation', start_frame=0, stop_frame=4),
                    meta=dict(size=5, start_frame=0, stop_frame=4, frame_filter='', deleted_frames=[], frames=copy.deepcopy(images)))
    event = dict(event_id='E000001', track_id=77, related_track_ids=[85], start_frame=2, end_frame=4,
                 anchor_frame=3, context_start=1, context_end=5, reasons=['possible_duplicate'], raw_flag_ids=['F1'])
    return dict(schema_version=2, events=[event]), snapshot, images


class FakeAPI:
    """Synthetic transport only. Never a CVAT round-trip or human evidence."""
    def __init__(self):
        self.issues = []
        self.comments = []
        self.calls = []
        self.fail_after_create = False
        self.annotations = dict(version=1, shapes=[], tracks=[])

    def listing(self, path, **kwargs):
        self.calls.append(('GET', path))
        return copy.deepcopy(self.issues if path == '/api/issues' else self.comments)

    def request(self, method, path, payload=None):
        self.calls.append((method, path))
        if method == 'GET' and path.endswith('/annotations'):
            return copy.deepcopy(self.annotations)
        if method == 'POST' and path == '/api/issues':
            i = dict(id=len(self.issues)+1, job=payload['job'], frame=payload['frame'], position=payload['position'], resolved=False)
            self.issues.append(i)
            self.comments.append(dict(id=i['id'], issue=i['id'], message=payload['message']))
            if self.fail_after_create:
                self.fail_after_create = False
                raise IntegrationError('Simulated connection loss after server commit')
            return copy.deepcopy(i)
        raise AssertionError((method, path))


class CVATTests(unittest.TestCase):
    def setUp(self):
        self.data, self.snapshot, self.images = fixture()
        self.plan = make_plan(self.data, self.snapshot, self.images, 1, 2, 'fixture', 'https://example.invalid')

    def test_event_schema_and_duplicate_event_rejected(self):
        self.assertEqual(len(parse_events(self.data)), 1)
        for invalid in [{}, dict(schema_version=1, events=[]), dict(schema_version=2, events=self.data['events']*2)]:
            with self.assertRaises(IntegrationError): parse_events(invalid)

    def test_bad_temporal_and_id_fields(self):
        for key, value in [('anchor_frame', 6), ('context_start', 0), ('track_id', True), ('related_track_ids', '85'), ('reasons', [])]:
            data = copy.deepcopy(self.data); data['events'][0][key] = value
            with self.assertRaises(IntegrationError): parse_events(data)

    def test_first_middle_last_and_context_mapping(self):
        mapping = frame_mapping(self.snapshot, self.images, 1, 2)
        self.assertEqual([mapping[f]['cvat_frame'] for f in [1, 3, 5]], [0, 2, 4])
        cv = self.plan['items'][0]['metadata']['cvat_frames']
        self.assertEqual((cv['anchor_frame'], cv['context_start'], cv['context_end']), (2, 0, 4))

    def test_invalid_target_job_or_task(self):
        for task, job in [(0, 2), (1, 9), (9, 2), (True, 2)]:
            with self.assertRaises(IntegrationError): frame_mapping(self.snapshot, self.images, task, job)
        self.snapshot['job']['task_id'] = 8
        with self.assertRaises(IntegrationError): frame_mapping(self.snapshot, self.images, 1, 2)

    def test_unsupported_order_step_subset_dimensions(self):
        variants = []
        for key, value in [('frame_filter', 'step=2'), ('start_frame', 1), ('deleted_frames', [2]), ('size', 4)]:
            s = copy.deepcopy(self.snapshot); s['meta'][key] = value; variants.append(s)
        s = copy.deepcopy(self.snapshot); s['meta']['frames'].reverse(); variants.append(s)
        s = copy.deepcopy(self.snapshot); s['meta']['frames'][0]['width'] = 1; variants.append(s)
        s = copy.deepcopy(self.snapshot); s['job']['stop_frame'] = 3; variants.append(s)
        for s in variants:
            with self.assertRaises(IntegrationError): frame_mapping(s, self.images, 1, 2)

    def test_out_of_bounds_event(self):
        self.data['events'][0]['context_end'] = 6
        with self.assertRaises(IntegrationError): make_plan(self.data, self.snapshot, self.images, 1, 2, 'fixture', '')

    def test_object_unavailable_and_experimental_metadata(self):
        item = self.plan['items'][0]
        self.assertTrue(item['metadata']['experimental'])
        self.assertEqual(item['metadata']['object_mapping'], 'UNAVAILABLE')
        self.assertEqual(item['metadata']['external_track_id'], 77)
        self.assertNotIn('object_id', item['payload'])
        self.assertEqual(json.loads(item['payload']['message'].split('\n')[1])['event']['related_track_ids'], [85])

    def test_namespace_prevents_cross_dataset_collision(self):
        other = make_plan(self.data, self.snapshot, self.images, 1, 2, 'different', '')
        self.assertNotEqual(self.plan['items'][0]['marker'], other['items'][0]['marker'])

    def test_dry_run_no_remote_mutation(self):
        api = FakeAPI(); result = execute(api, self.plan, 'dry-run')
        self.assertEqual(result['actions'][0]['action'], 'CREATE')
        self.assertTrue(all(c[0] == 'GET' for c in api.calls))
        self.assertEqual(api.issues, [])

    def test_push_roundtrip_and_second_run_idempotent(self):
        api = FakeAPI(); first = execute(api, self.plan, 'push')
        second = execute(api, self.plan, 'push', first['event_issue_map'])
        self.assertTrue(first['verified'] and first['annotations_unchanged'])
        self.assertEqual(second['actions'][0]['action'], 'SKIP_EXISTING')
        self.assertEqual(sum(c[0] == 'POST' for c in api.calls), 1)

    def test_resolved_stays_resolved_and_verify_readonly(self):
        api = FakeAPI(); execute(api, self.plan, 'push'); api.issues[0]['resolved'] = True; api.calls.clear()
        result = execute(api, self.plan, 'verify')
        self.assertTrue(result['readback'][0]['resolved'])
        self.assertTrue(all(c[0] == 'GET' for c in api.calls))

    def test_timeout_after_server_commit_recovers_without_duplicate(self):
        api = FakeAPI(); api.fail_after_create = True
        with self.assertRaises(IntegrationError): execute(api, self.plan, 'push')
        result = execute(api, self.plan, 'push')
        self.assertTrue(result['verified']); self.assertEqual(len(api.issues), 1)

    def test_remote_drift_duplicate_and_deleted_marker_fail_closed(self):
        api = FakeAPI(); result = execute(api, self.plan, 'push')
        comments = copy.deepcopy(api.comments); comments[0]['message'] += 'edited'
        with self.assertRaises(IntegrationError): reconcile(self.plan, api.issues, comments)
        with self.assertRaises(IntegrationError): reconcile(self.plan, api.issues, api.comments*2)
        with self.assertRaises(IntegrationError): reconcile(self.plan, api.issues, [], result['event_issue_map'])

    def test_missing_credentials_and_unsafe_url(self):
        with patch.dict(os.environ, {}, clear=True), patch('cvat_integration.load_dotenv', return_value={}):
            with self.assertRaises(IntegrationError): Client()
        for url in ['https://user:secret@host', 'http://remote.invalid', 'https://host/?secret=x']:
            with self.assertRaises(IntegrationError): Client(url, 'test-only')

    def test_dotenv_fallback_and_environment_priority(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'.env'
            path.write_text('CVAT_URL=http://from-file:8080\nCVAT_TOKEN=file-secret\nCVAT_TASK_ID=6\nIGNORED=x\n')
            env = {'CVAT_URL': 'http://from-environment:8080'}
            loaded = load_dotenv(path, env)
            self.assertEqual(env['CVAT_URL'], 'http://from-environment:8080')
            self.assertEqual(env['CVAT_TOKEN'], 'file-secret')
            self.assertEqual(env['CVAT_TASK_ID'], '6')
            self.assertNotIn('IGNORED', env)
            self.assertNotIn('CVAT_URL', loaded)

    def test_dotenv_malformed_line_rejected_without_secret_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'.env'; path.write_text('CVAT_TOKEN=fixture-only\nbroken-line\n')
            with self.assertRaisesRegex(IntegrationError, 'line 2') as caught:
                load_dotenv(path, {})
            self.assertNotIn('fixture-only', str(caught.exception))

    def test_network_http_failure_no_retry_no_secret_leak(self):
        client = Client('https://example.invalid', 'SECRET_NOT_TO_LOG')
        for error in [URLError('SECRET_NOT_TO_LOG'), HTTPError('https://example.invalid', 403, 'secret', {}, None)]:
            with patch.object(client.opener, 'open', side_effect=error) as opened:
                with self.assertRaises(IntegrationError) as e: client.request('POST', '/api/issues', {})
                self.assertNotIn('SECRET_NOT_TO_LOG', str(e.exception)); self.assertEqual(opened.call_count, 1)

    def test_annotation_write_is_impossible_and_pagination(self):
        client = Client('https://example.invalid', 'test-only')
        for method in ['POST', 'PATCH', 'PUT', 'DELETE']:
            with self.assertRaises(IntegrationError): client.request(method, '/api/jobs/2/annotations', {})
        with patch.object(client, 'request', side_effect=[dict(results=[1], next='https://evil.invalid'), dict(results=[2], next=None)]) as call:
            self.assertEqual(client.listing('/api/issues', job_id=2), [1, 2])
            self.assertTrue(call.call_args.args[1].startswith('/api/issues?'))

    def test_cli_offline_payloads_and_push_protection(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); images = root/'images'; images.mkdir()
            for im in self.images: Image.new('RGB', (100, 50)).save(images/im['name'])
            (root/'events.json').write_text(json.dumps(self.data)); (root/'snapshot.json').write_text(json.dumps(self.snapshot))
            args = ['--events', str(root/'events.json'), '--images', str(images), '--sequence', 'fixture', '--task', '1', '--job', '2', '--snapshot', str(root/'snapshot.json'), '--out', str(root/'out')]
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(args+['--dry-run']), 0)
                self.assertEqual(main(args+['--push', '--confirm-test-task', '1']), 2)
            self.assertTrue((root/'out/navigation.md').exists())
            self.assertEqual(json.loads((root/'out/dry-run.json').read_text())['event_count'], 1)

    def test_local_writer_lock(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with writer_lock(root):
                with self.assertRaises(IntegrationError):
                    with writer_lock(root): pass
            self.assertFalse((root/'push.lock').exists())


if __name__ == '__main__':
    unittest.main()
