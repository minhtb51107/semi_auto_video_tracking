"""Frame-level CVAT Issues adapter; never writes annotations or analyzer outputs."""
import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler


class IntegrationError(ValueError):
    pass


def load_dotenv(path=None, environ=None):
    """Fill missing CVAT_* variables from a local .env; never overwrite process env."""
    environ = os.environ if environ is None else environ
    path = Path(path or Path(__file__).resolve().parents[1]/'.env')
    if not path.is_file():
        return {}
    allowed = {
        'CVAT_URL', 'CVAT_TOKEN', 'CVAT_TASK_ID', 'CVAT_JOB_ID',
        'CVAT_AUTH_SCHEME', 'KAGGLE_API_TOKEN',
    }
    loaded = {}
    for number, raw in enumerate(path.read_text(encoding='utf-8-sig').splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        if '=' not in line:
            raise IntegrationError(f'Invalid .env line {number}')
        key, value = (part.strip() for part in line.split('=', 1))
        if key.startswith('export '):
            key = key[7:].strip()
        if key not in allowed:
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]
        if '\n' in value or '\r' in value:
            raise IntegrationError(f'Invalid .env value for {key}')
        # An empty inherited variable is not a usable credential/config value.
        # Treat it as missing so a local, ignored .env can still supply it.
        if not environ.get(key):
            environ[key] = value
            loaded[key] = value
    return loaded


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def save(path, value):
    path = Path(path)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    temp.replace(path)


def integer(value, minimum=0):
    return type(value) is int and value >= minimum


def parse_events(data):
    if not isinstance(data, dict) or data.get('schema_version') != 2 or not isinstance(data.get('events'), list):
        raise IntegrationError('Expected Analyzer v2 review_events schema_version=2')
    seen = set()
    keys = ('context_start', 'start_frame', 'anchor_frame', 'end_frame', 'context_end')
    for e in data['events']:
        if not isinstance(e, dict) or not re.fullmatch(r'[A-Za-z0-9_-]+', str(e.get('event_id', ''))):
            raise IntegrationError('Invalid event_id')
        if e['event_id'] in seen:
            raise IntegrationError('Duplicate event_id')
        seen.add(e['event_id'])
        if not all(integer(e.get(k), 1) for k in keys) or [e[k] for k in keys] != sorted(e[k] for k in keys):
            raise IntegrationError('Invalid temporal range')
        if not integer(e.get('track_id')) or not isinstance(e.get('related_track_ids'), list) or not all(integer(x) for x in e['related_track_ids']):
            raise IntegrationError('Invalid external track IDs')
        if not isinstance(e.get('reasons'), list) or not e['reasons'] or not all(isinstance(x, str) and x for x in e['reasons']):
            raise IntegrationError('Missing reasons')
    return data['events']


def image_inventory(folder):
    # This project's locked clip contract is 000001.jpg .. N.jpg, MOT 1-based.
    from PIL import Image
    paths = sorted(Path(folder).glob('*.jpg'))
    if not paths or [p.name for p in paths] != [f'{i:06d}.jpg' for i in range(1, len(paths)+1)]:
        raise IntegrationError('Require complete project JPEG sequence 000001.jpg .. N.jpg')
    result = []
    for p in paths:
        with Image.open(p) as im:
            width, height = im.size
        result.append(dict(name=p.name, width=width, height=height, sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
    return result


def frame_mapping(snapshot, images, task_id, job_id):
    if not isinstance(snapshot, dict) or not all(isinstance(snapshot.get(k), dict) for k in ('task', 'job', 'meta')):
        raise IntegrationError('Unexpected task/job metadata schema')
    if not integer(task_id, 1) or not integer(job_id, 1):
        raise IntegrationError('Task/job IDs must be positive integers')
    task, job, meta = (snapshot[k] for k in ('task', 'job', 'meta'))
    n = len(images)
    if task.get('id') != task_id or job.get('id') != job_id or job.get('task_id') != task_id:
        raise IntegrationError('Task/job mismatch')
    if task.get('dimension') != '2d' or job.get('type') != 'annotation':
        raise IntegrationError('Only 2D annotation jobs supported')
    if job.get('start_frame') != 0 or job.get('stop_frame') != n-1:
        raise IntegrationError('Require one job covering the full sequence/context')
    if meta.get('size') != n or meta.get('start_frame') != 0 or meta.get('stop_frame') != n-1 or meta.get('frame_filter', '') not in ('', 'step=1'):
        raise IntegrationError('Unsupported count/start/stop/frame filter')
    if meta.get('deleted_frames') != [] or meta.get('included_frames'):
        raise IntegrationError('Deleted/subsampled frames are unsupported')
    frames = meta.get('frames', [])
    if not isinstance(frames, list) or len(frames) != n or n == 0 or not all(isinstance(f, dict) for f in frames):
        raise IntegrationError('Require full image metadata, not video summary')
    names = [str(f.get('name', '')).replace('\\', '/').split('/')[-1] for f in frames]
    if len(set(names)) != n or names != [i['name'] for i in images]:
        raise IntegrationError('Image order/names mismatch')
    mapping = {}
    for cvat_frame, (remote, local) in enumerate(zip(frames, images)):
        if any(remote.get(k) != local[k] for k in ('width', 'height')):
            raise IntegrationError('Image dimensions mismatch')
        mapping[cvat_frame+1] = dict(mot_frame=cvat_frame+1, cvat_frame=cvat_frame,
                                    name=local['name'], width=local['width'], height=local['height'])
    return mapping


def make_plan(data, snapshot, images, task_id, job_id, sequence, base_url):
    if not re.fullmatch(r'[A-Za-z0-9_-]+', sequence):
        raise IntegrationError('Invalid sequence namespace')
    events = parse_events(data)
    mapping = frame_mapping(snapshot, images, task_id, job_id)
    items = []
    for e in events:
        if e['context_end'] > len(mapping):
            raise IntegrationError(f"Out-of-range frame in {e['event_id']}")
        cv = {k: mapping[e[k]]['cvat_frame'] for k in ('anchor_frame', 'start_frame', 'end_frame', 'context_start', 'context_end')}
        marker = f"SATV2|{sequence}|{e['event_id']}"
        metadata = dict(event=e, analyzer_version='2', event_source_sha256=digest(data),
                        external_track_id=e['track_id'], object_mapping='UNAVAILABLE',
                        cvat_frames=cv, experimental='possible_duplicate' in e['reasons'])
        message = marker + '\n' + json.dumps(metadata, sort_keys=True, ensure_ascii=False)
        frame = mapping[e['anchor_frame']]
        # Point near top-left is explicitly frame-level, never a claimed object location.
        payload = dict(job=job_id, frame=cv['anchor_frame'], position=[min(10, frame['width']/2), min(10, frame['height']/2)], message=message)
        url = f'{base_url}/tasks/{task_id}/jobs/{job_id}'
        items.append(dict(event_id=e['event_id'], marker=marker, payload=payload, metadata=metadata,
                          links={k: f'{url}?frame={v}' for k, v in cv.items()}))
    return dict(schema_version=1, human_review_status='PREPARED_NOT_EXECUTED', task_id=task_id, job_id=job_id,
                sequence=sequence, url=base_url, source_sha256=digest(data),
                snapshot_status=snapshot.get('provenance', 'OFFLINE_UNVERIFIED'),
                image_inventory_sha256=digest(images), frame_mapping=list(mapping.values()), items=items,
                validation_errors=[], event_count=len(items))


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise IntegrationError('HTTP redirect refused; set the correct CVAT_URL')


class Client:
    def __init__(self, url=None, token=None, scheme=None):
        load_dotenv()
        self.url = (url or os.environ.get('CVAT_URL', '')).rstrip('/')
        token = token or os.environ.get('CVAT_TOKEN', '')
        scheme = scheme or os.environ.get('CVAT_AUTH_SCHEME', 'Bearer')
        parsed = urlsplit(self.url)
        if not self.url or not token:
            raise IntegrationError('Missing CVAT_URL/CVAT_TOKEN; offline --snapshot --dry-run is available')
        if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ('', '/'):
            raise IntegrationError('CVAT_URL must be a server origin without credentials/path/query')
        if parsed.scheme == 'http' and parsed.hostname not in ('localhost', '127.0.0.1', '::1'):
            raise IntegrationError('Use HTTPS except for a local disposable server')
        if scheme not in ('Bearer', 'Token') or '\n' in token or '\r' in token:
            raise IntegrationError('Invalid authentication configuration')
        self.headers = {'Authorization': f'{scheme} {token}', 'Content-Type': 'application/json'}
        self.opener = build_opener(NoRedirect())

    def request(self, method, path, payload=None):
        # Hard boundary: the only remote mutation permitted by this adapter is creating an issue.
        if not path.startswith('/api/') or (method != 'GET' and (method != 'POST' or path != '/api/issues')):
            raise IntegrationError('Disallowed API operation')
        req = Request(self.url+path, data=None if payload is None else json.dumps(payload).encode(), headers=self.headers, method=method)
        try:
            with self.opener.open(req, timeout=30) as response:
                result = json.load(response)
                if not isinstance(result, dict):
                    raise IntegrationError('Unexpected CVAT response schema')
                return result
        except HTTPError as exc:
            raise IntegrationError(f'CVAT HTTP {exc.code} for {method} {path.split("?")[0]}; no automatic retry') from None
        except (URLError, TimeoutError, OSError, ValueError):
            raise IntegrationError(f'CVAT network/response failure for {method}; reconcile before retry, no automatic POST retry') from None

    def listing(self, path, **params):
        rows, page = [], 1
        while True:
            result = self.request('GET', path+'?'+urlencode(dict(params, page=page, page_size=100)))
            if not isinstance(result, dict) or not isinstance(result.get('results'), list):
                raise IntegrationError('Unsupported paginated API response')
            rows.extend(result['results'])
            if not result.get('next'):
                return rows
            if not result['results'] or page > 10000:
                raise IntegrationError('Invalid pagination')
            page += 1  # Never follow an arbitrary authenticated next URL.

    def snapshot(self, task, job):
        return dict(provenance='LIVE_GET', about=self.request('GET', '/api/server/about'),
                    task=self.request('GET', f'/api/tasks/{task}'),
                    job=self.request('GET', f'/api/jobs/{job}'),
                    meta=self.request('GET', f'/api/tasks/{task}/data/meta'))


def reconcile(plan, issues, comments, prior=None):
    if not isinstance(issues, list) or not isinstance(comments, list):
        raise IntegrationError('Unexpected issues/comments schema')
    seen_issues, seen_comments = set(), set()
    for i in issues:
        if (not isinstance(i, dict) or not integer(i.get('id'), 1)
                or not integer(i.get('job'), 1) or not integer(i.get('frame'))
                or not isinstance(i.get('position'), list) or type(i.get('resolved')) is not bool
                or i['id'] in seen_issues):
            raise IntegrationError('Unexpected issue schema or duplicate issue ID')
        seen_issues.add(i['id'])
    for c in comments:
        if (not isinstance(c, dict) or not integer(c.get('id'), 1)
                or not integer(c.get('issue'), 1) or not isinstance(c.get('message'), str)
                or c['id'] in seen_comments):
            raise IntegrationError('Unexpected comment schema or duplicate comment ID')
        seen_comments.add(c['id'])
    issue_map = {i['id']: i for i in issues if i.get('job') == plan['job_id']}
    by_marker = {}
    for c in comments:
        message = c.get('message', '')
        marker = message.split('\n', 1)[0]
        if marker.startswith('SATV2|'):
            by_marker.setdefault(marker, []).append(c)
    prefix = f"SATV2|{plan['sequence']}|"
    expected = {i['marker'] for i in plan['items']}
    if any(m.startswith(prefix) and m not in expected for m in by_marker):
        raise IntegrationError('Remote namespace contains events absent from this source; refuse source drift')
    actions = []
    for item in plan['items']:
        matches = by_marker.get(item['marker'], [])
        if len(matches) > 1:
            raise IntegrationError('Duplicate remote event markers; manual audit required')
        old_id = (prior or {}).get(item['event_id'])
        if not matches:
            if old_id is not None:
                raise IntegrationError('Previously mapped issue/marker missing; refuse recreation')
            actions.append(dict(event_id=item['event_id'], action='CREATE', issue_id=None))
            continue
        c = matches[0]
        issue = issue_map.get(c.get('issue'))
        payload = item['payload']
        if issue is None or c['message'] != payload['message'] or issue.get('frame') != payload['frame'] or issue.get('position') != payload['position']:
            raise IntegrationError('Remote event payload/frame conflict')
        if old_id is not None and old_id != issue['id']:
            raise IntegrationError('Local/remote issue mapping conflict')
        actions.append(dict(event_id=item['event_id'], action='SKIP_EXISTING', issue_id=issue['id'], resolved=issue.get('resolved')))
    return actions


def remote_actions(client, plan, prior=None):
    return reconcile(plan, client.listing('/api/issues', job_id=plan['job_id']),
                     client.listing('/api/comments', job_id=plan['job_id']), prior)


def execute(client, plan, mode, prior=None, checkpoint=None):
    if mode not in ('push', 'verify', 'dry-run'):
        raise IntegrationError('Invalid execution mode')
    actions = remote_actions(client, plan, prior)
    evidence = dict(mode=mode, actions=actions, annotations_unchanged=None, verified=False)
    if mode == 'dry-run':
        return evidence
    before = digest(client.request('GET', f"/api/jobs/{plan['job_id']}/annotations"))
    known = dict(prior or {})
    try:
        known.update({a['event_id']: a['issue_id'] for a in actions if a['issue_id'] is not None})
        if checkpoint and mode == 'push':
            checkpoint(known)
        for item, action in zip(plan['items'], actions):
            if action['action'] == 'CREATE' and mode == 'push':
                response = client.request('POST', '/api/issues', item['payload'])
                if not isinstance(response, dict) or not integer(response.get('id'), 1):
                    raise IntegrationError('Issue response has no valid ID; reconcile next run')
                known[item['event_id']] = response['id']
                if checkpoint:
                    checkpoint(known)
            elif action['issue_id'] is not None:
                known[item['event_id']] = action['issue_id']
        evidence['readback'] = remote_actions(client, plan, known)
        evidence['verified'] = all(a['action'] == 'SKIP_EXISTING' for a in evidence['readback'])
        evidence['event_issue_map'] = known
    finally:
        after = digest(client.request('GET', f"/api/jobs/{plan['job_id']}/annotations"))
        evidence.update(annotations_before_sha256=before, annotations_after_sha256=after, annotations_unchanged=before == after)
    if before != after:
        raise IntegrationError('Annotations changed during operation (possibly concurrent edit); audit required')
    return evidence


@contextmanager
def writer_lock(folder):
    path = folder/'push.lock'
    try:
        handle = path.open('x')
    except FileExistsError:
        raise IntegrationError('Existing push.lock: another writer or interrupted run; inspect before removing') from None
    try:
        handle.write(str(os.getpid())); handle.close()
        yield
    finally:
        path.unlink()


def write_navigation(path, plan):
    lines = ['# CVAT review navigation', '', 'Frame-level candidates; external IDs are not CVAT object IDs.',
             f"Metadata provenance: {plan['snapshot_status']}. Offline placeholders are not live tasks.", '',
             '| Event | External tracks | Reasons | Anchor | Context start / end |', '|---|---|---|---|---|']
    for i in plan['items']:
        e, links = i['metadata']['event'], i['links']
        reasons = ', '.join(e['reasons']) + (' (EXPERIMENTAL)' if i['metadata']['experimental'] else '')
        reasons = reasons.replace('|', '\\|').replace('\n', ' ')
        lines.append(f"| {e['event_id']} | {e['track_id']}, related={e['related_track_ids']} | {reasons} | [open]({links['anchor_frame']}) | [start]({links['context_start']}) / [end]({links['context_end']}) |")
    path.write_text('\n'.join(lines)+'\n', encoding='utf-8')


def plan_identity(plan):
    return {k: plan[k] for k in ('url', 'task_id', 'job_id', 'sequence', 'source_sha256',
                                 'image_inventory_sha256', 'frame_mapping', 'items')}


def validate_state(path, scope, plan):
    if not path.exists():
        return {}
    try:
        state = read(path)
        mapping = state['mapping']
        allowed = {i['event_id'] for i in plan['items']}
        if (state['scope'] != scope or not isinstance(mapping, dict)
                or not set(mapping) <= allowed or not all(integer(i, 1) for i in mapping.values())
                or len(set(mapping.values())) != len(mapping)):
            raise ValueError()
        return mapping
    except (ValueError, KeyError, TypeError, OSError):
        raise IntegrationError('Corrupt or mismatched local state; original state preserved') from None


def guard_source(folder, plan, source_path, mode):
    """Check immutable approved plan before touching evidence or calling POST."""
    planned = folder/'request_plan.json'
    locked = folder/'source_lock.json'
    identity = digest(plan_identity(plan))
    source_bytes = hashlib.sha256(source_path.read_bytes()).hexdigest()
    wanted = dict(schema_version=1, plan_sha256=identity, source_file_sha256=source_bytes)
    try:
        if planned.exists() and digest(plan_identity(read(planned))) != identity:
            raise IntegrationError('Source/target/frame mapping differs from locked request plan')
        if locked.exists():
            if read(locked) != wanted:
                raise IntegrationError('Source file or plan differs from immutable source lock')
        elif mode == 'push' and not planned.exists():
            raise IntegrationError('Push requires a prior dry-run request plan')
    except (KeyError, TypeError, json.JSONDecodeError):
        raise IntegrationError('Corrupt plan/source lock; original evidence preserved') from None
    return wanted


def main(argv=None):
    load_dotenv()
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--events', type=Path, required=True)
    p.add_argument('--images', type=Path, required=True)
    p.add_argument('--sequence', required=True)
    p.add_argument('--task', type=int, default=os.environ.get('CVAT_TASK_ID'))
    p.add_argument('--job', type=int, default=os.environ.get('CVAT_JOB_ID'))
    p.add_argument('--snapshot', type=Path, help='Offline metadata only, never allowed for push/verify')
    p.add_argument('--out', type=Path, required=True, help='Dedicated integration directory, not validation outputs')
    modes = p.add_mutually_exclusive_group(required=True)
    modes.add_argument('--dry-run', action='store_true')
    modes.add_argument('--push', action='store_true')
    modes.add_argument('--verify', action='store_true')
    p.add_argument('--confirm-test-task', type=int)
    a = p.parse_args(argv)
    a.out.mkdir(parents=True, exist_ok=True)
    try:
        if a.task is None or a.job is None:
            raise IntegrationError('Missing --task/--job or CVAT_TASK_ID/CVAT_JOB_ID')
        if a.snapshot and not a.dry_run:
            raise IntegrationError('Offline snapshot is dry-run only')
        if a.push and a.confirm_test_task != a.task:
            raise IntegrationError('Push requires --confirm-test-task equal to the disposable task ID')
        data, images = read(a.events), image_inventory(a.images)
        client = None if a.snapshot else Client()
        snapshot = read(a.snapshot) if a.snapshot else client.snapshot(a.task, a.job)
        if a.snapshot:
            snapshot['provenance'] = 'OFFLINE_UNVERIFIED'
        url = snapshot.get('url', 'https://cvat.example.invalid') if a.snapshot else client.url
        plan = make_plan(data, snapshot, images, a.task, a.job, a.sequence, url)
        scope = digest({k: plan[k] for k in ('url', 'task_id', 'job_id', 'sequence', 'source_sha256', 'image_inventory_sha256')})
        state_path = a.out/'state.json'
        mode = 'dry-run' if a.dry_run else 'push' if a.push else 'verify'
        def checkpoint(mapping):
            save(state_path, dict(scope=scope, mapping=mapping))
        with writer_lock(a.out):
            prior = validate_state(state_path, scope, plan)
            source_lock = guard_source(a.out, plan, a.events, mode)
            # Never rewrite approved plans or first metadata evidence on retry.
            if not (a.out/'request_plan.json').exists():
                save(a.out/'request_plan.json', plan)
            if not (a.out/'source_lock.json').exists():
                save(a.out/'source_lock.json', source_lock)
            if not (a.out/'snapshot.json').exists():
                save(a.out/'snapshot.json', snapshot)
            if not (a.out/'navigation.md').exists():
                write_navigation(a.out/'navigation.md', plan)
            if client:
                result = execute(client, plan, mode, prior, checkpoint)
            else:
                result = dict(mode=mode, actions=reconcile(plan, snapshot.get('issues', []), snapshot.get('comments', [])),
                              verified=False, annotations_unchanged=None, live_cvat=False)
            if a.push and result.get('event_issue_map') is not None:
                checkpoint(result['event_issue_map'])
        result.update(task_id=a.task, job_id=a.job, event_count=len(plan['items']), validation_errors=[],
                      frame_mapping=plan['frame_mapping'], human_review_status='PREPARED_NOT_EXECUTED')
        save(a.out/(mode+'.json'), result)
        print(json.dumps(result, indent=2))
        return 0 if not a.verify or result['verified'] else 2
    except (IntegrationError, KeyError, TypeError, OSError, json.JSONDecodeError) as exc:
        result = dict(validation_errors=[str(exc)], human_review_status='PREPARED_NOT_EXECUTED', success=False)
        save(a.out/'error.json', result)
        print(json.dumps(result))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
