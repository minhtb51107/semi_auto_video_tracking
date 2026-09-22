"""Run tests and both real-video pipelines using this project's own environment."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id', default=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    args = parser.parse_args()
    if not args.run_id or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in args.run_id):
        parser.error('--run-id must contain only letters, numbers, underscores and hyphens')
    if Path(sys.prefix).resolve() != (ROOT / '.venv').resolve():
        parser.error('Run with this project\'s .venv/Scripts/python.exe')
    out = ROOT / 'outputs/runs' / args.run_id
    out.mkdir(parents=True, exist_ok=False)
    env = os.environ.copy()
    env.pop('PYTHONPATH', None)
    env.pop('PYTHONHOME', None)
    env['PYTHONNOUSERSITE'] = '1'
    env['PYTHONUTF8'] = '1'
    runtime = ROOT / '.runtime'
    runtime.mkdir(exist_ok=True)
    env['YOLO_CONFIG_DIR'] = str(runtime / 'ultralytics')
    Path(env['YOLO_CONFIG_DIR']).mkdir(exist_ok=True)
    # Keep temporary test data local; no system Temp or source-repo dependency.
    temp = runtime / 'tmp'
    temp.mkdir(exist_ok=True)
    env['TMP'] = env['TEMP'] = str(temp)
    os.environ['YOLO_CONFIG_DIR'] = env['YOLO_CONFIG_DIR']
    summary = {'project_root': str(ROOT), 'python': sys.executable,
               'python_version': platform.python_version(), 'started_utc': datetime.now(timezone.utc).isoformat(),
               'status': 'running', 'commands': [], 'dependencies': {}, 'clips': {}}
    summary_path = out / 'acceptance.json'

    def save():
        summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')

    def run(label, arguments):
        command = [sys.executable, '-X', 'utf8', *map(str, arguments)]
        started = time.perf_counter()
        result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True, encoding='utf-8')
        (out / f'{label}.log').write_text(result.stdout + result.stderr, encoding='utf-8')
        summary['commands'].append({'label': label, 'command': command, 'cwd': str(ROOT),
                                    'returncode': result.returncode, 'seconds': time.perf_counter() - started})
        save()
        print(f'{label}: exit {result.returncode}', flush=True)
        if result.returncode:
            raise RuntimeError(f'{label} failed; see {out / (label + ".log")}')

    originals = [ROOT / p for p in ('annotations/clip_01/gt.txt', 'annotations/clip_02/gt.txt',
                                   'gold/clip_01/gt.txt', 'data/clips/clip_02/gt/gt.txt',
                                   'evidence/pre-gold/clip_01/gt.txt')]
    before = {p.relative_to(ROOT).as_posix(): digest(p) for p in originals}
    try:
        for name in ('torch', 'ultralytics', 'cv2', 'numpy', 'lap', 'PIL'):
            module = importlib.import_module(name)
            location = Path(module.__file__).resolve()
            if not location.is_relative_to(ROOT / '.venv'):
                raise RuntimeError(f'Dependency outside project environment: {name}: {location}')
            summary['dependencies'][name] = {'file': str(location), 'version': getattr(module, '__version__', None)}
        summary['weights_sha256'] = digest(ROOT / 'yolo26n.pt')
        run('pip_check', ['-m', 'pip', 'check'])
        run('tests', ['-m', 'unittest', 'discover', '-s', 'tests', '-v'])
        for number in ('01', '02'):
            clip = (out / f'clip_{number}').relative_to(ROOT)
            tracks = clip / 'tracks.txt'
            run(f'decode_{number}', ['tools/video_to_clip.py', '--video', f'assets/guide/clip-{number}-preview.mp4', '--out', clip])
            run(f'tracker_{number}', ['tools/run_tracker.py', '--clip', clip, '--model', 'yolo26n.pt',
                                     '--tracker', 'bytetrack.yaml', '--device', 'cpu', '--out', tracks])
            run(f'review_{number}', ['tools/review_tracks.py', '--tracks', tracks, '--out-dir', clip / 'review'])
            run(f'validate_{number}', ['tools/check_mot_labels.py', '--clip', clip, '--tracks', tracks])
            reference = 'gold/clip_01/gt.txt' if number == '01' else 'data/clips/clip_02/gt/gt.txt'
            run(f'evaluate_{number}', ['tools/evaluate_tracking.py', '--pred', tracks, '--gt', reference,
                                      '--seqinfo', clip / 'seqinfo.ini', '--mode', 'model', '--output', clip / 'evaluation.json'])
            run(f'visualize_{number}', ['tools/visualize_tracks.py', '--clip', clip, '--tracks', tracks,
                                       '--only-frames', '1,17,39', '--out', clip / 'vis_review'])
            result = json.loads((ROOT / clip / 'review/review_flags.json').read_text(encoding='utf-8'))
            historical = ROOT / f'outputs/mvp_video_clip_{number}/tracks.txt'
            summary['clips'][number] = {**result['summary'], 'tracks_sha256': digest(ROOT / tracks),
                                       'matches_original_mvp_tracks': digest(ROOT / tracks) == digest(historical)}
        after = {p.relative_to(ROOT).as_posix(): digest(p) for p in originals}
        if before != after:
            raise RuntimeError('Input labels changed')
        summary['input_hashes_unchanged'] = after
        summary['status'] = 'passed'
    except Exception as exc:
        summary['status'] = 'failed'
        summary['error'] = str(exc)
        raise
    finally:
        save()
    print(json.dumps(summary['clips'], indent=2))
    print(f'Evidence: {summary_path}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
