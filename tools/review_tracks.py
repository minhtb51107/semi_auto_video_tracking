"""MOT result -> heuristic review candidates. Does not correct annotations."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

from motlib import MotFormatError, by_track, iou, parse_mot

DEFAULT_CONFIG = Path(__file__).resolve().parents[1] / 'configs/review_thresholds.json'
FIELDS = ['frame_id', 'track_id', 'reason', 'observed_value', 'threshold',
          'previous_frame_id', 'related_track_id']
RULES = {
    'track_gap_min_missing_frames': (1, None, True),
    'track_reappeared_min_missing_frames': (1, None, True),
    'large_motion_jump_max_diagonals': (0, None, False),
    'abnormal_size_change_max_ratio': (1, None, False),
    'low_consecutive_iou_min': (0, 1, False),
    'fragmentation_max_frame_distance': (1, None, True),
    'fragmentation_min_endpoint_iou': (0, 1, False),
}


def validate_config(config):
    if set(config) != set(RULES) | {'status'}:
        raise ValueError('Config must contain exactly status and documented threshold keys')
    if config['status'] != 'experimental_uncalibrated':
        raise ValueError('Thresholds are experimental_uncalibrated; no calibration supplied')
    for key, (minimum, maximum, integer) in RULES.items():
        value = config[key]
        if (type(value) not in (int, float) or not math.isfinite(value)
                or value < minimum or (maximum is not None and value > maximum)
                or (integer and type(value) is not int)):
            raise ValueError(f'Invalid threshold: {key}')
    if config['large_motion_jump_max_diagonals'] <= 0:
        raise ValueError('Motion threshold must be positive')
    if config['track_reappeared_min_missing_frames'] < config['track_gap_min_missing_frames']:
        raise ValueError('Reappearance threshold must be >= gap threshold')
    return config


def load_config(path=DEFAULT_CONFIG):
    return validate_config(json.loads(Path(path).read_text(encoding='utf-8-sig')))


def load_tracks(path):
    """Guard legacy parser's permissive coercions, then reuse its MOT semantics.

    Accept repository MOT 6/7/9/10-column variants; ignore conf=0 as motlib does.
    Validate ignored rows too, so malformed input never silently becomes success.
    """
    path = Path(path)
    for line_number, line in enumerate(path.read_text(encoding='utf-8-sig').splitlines(), 1):
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        parts = [p.strip() for p in line.replace(';', ',').split(',')]
        try:
            if len(parts) not in (6, 7, 9, 10) or any(not p for p in parts):
                raise ValueError('expected 6, 7, 9 or 10 nonempty columns')
            values = [float(p) for p in parts]
            if not all(math.isfinite(v) for v in values):
                raise ValueError('nonfinite value')
            if not values[0].is_integer() or values[0] < 1:
                raise ValueError('frame must be an integer >= 1')
            if not values[1].is_integer() or values[1] < 0:
                raise ValueError('track ID must be an integer >= 0')
            if values[4] <= 0 or values[5] <= 0:
                raise ValueError('width and height must be positive')
        except ValueError as exc:
            raise MotFormatError(f'{path}:{line_number}: {exc}') from exc
    detections = parse_mot(path)
    seen = set()
    for det in detections:
        key = (det.frame, det.track_id)
        if key in seen:
            raise MotFormatError(f'{path}: duplicate frame/track {key}')
        seen.add(key)
    return detections


def classes_compatible(first, second, class_compatibility=None):
    """Compare detector classes using canonical labels when they are known.

    With no mapping (or an incomplete mapping), retain the prior safe behavior:
    known detector subclasses must be equal, while class-less legacy MOT rows
    remain eligible for geometry-only analysis.
    """
    if first is None or second is None:
        return True
    if class_compatibility is not None:
        first_group = class_compatibility.get(first)
        second_group = class_compatibility.get(second)
        if first_group is not None and second_group is not None:
            return first_group == second_group
    return first == second


def analyze(detections, config, class_compatibility=None):
    validate_config(config)
    tracks = by_track(detections)
    flags = []

    def flag(current, previous, reason, observed, threshold, related=None):
        flags.append(dict(frame_id=current.frame, track_id=current.track_id,
                          reason=reason, observed_value=observed, threshold=threshold,
                          previous_frame_id=previous.frame, related_track_id=related))

    for track in tracks.values():
        for previous, current in zip(track, track[1:]):
            missing = current.frame - previous.frame - 1
            if missing >= config['track_gap_min_missing_frames']:
                flag(current, previous, 'track_gap', missing,
                     config['track_gap_min_missing_frames'])
            if missing >= config['track_reappeared_min_missing_frames']:
                flag(current, previous, 'track_reappeared', missing,
                     config['track_reappeared_min_missing_frames'])
            if missing != 0:
                continue
            motion = math.hypot(current.x + current.w / 2 - previous.x - previous.w / 2,
                                current.y + current.h / 2 - previous.y - previous.h / 2)
            motion /= math.hypot(previous.w, previous.h)
            ratio = max(current.w / previous.w, previous.w / current.w,
                        current.h / previous.h, previous.h / current.h)
            overlap = iou(previous, current)
            for reason, value, key, exceeded in (
                ('large_motion_jump', motion, 'large_motion_jump_max_diagonals', True),
                ('abnormal_size_change', ratio, 'abnormal_size_change_max_ratio', True),
                ('low_consecutive_iou', overlap, 'low_consecutive_iou_min', False),
            ):
                threshold = config[key]
                if (value > threshold) if exceeded else (value < threshold):
                    flag(current, previous, reason, value, threshold)

    # Candidate endpoint pairs only. Never associate tracks or claim identity truth.
    for old_id, old in tracks.items():
        for new_id, new in tracks.items():
            if old_id == new_id:
                continue
            # Class-aware MOT must not suggest cross-class fragmentation.
            # Missing class identity keeps the legacy geometry-only behavior.
            if not classes_compatible(old[-1].class_id, new[0].class_id,
                                      class_compatibility):
                continue
            distance = new[0].frame - old[-1].frame
            if 1 <= distance <= config['fragmentation_max_frame_distance']:
                overlap = iou(old[-1], new[0])
                if overlap >= config['fragmentation_min_endpoint_iou']:
                    flag(new[0], old[-1], 'possible_fragmentation', overlap,
                         config['fragmentation_min_endpoint_iou'], old_id)
    return sorted(flags, key=lambda f: (f['frame_id'], f['track_id'], f['reason'],
                                       -1 if f['related_track_id'] is None else f['related_track_id']))


def review_file(tracks_path, config_path, out_dir):
    tracks_path, config_path, out_dir = map(Path, (tracks_path, config_path, out_dir))
    targets = [out_dir / 'review_flags.csv', out_dir / 'review_flags.json']
    if any(p.resolve() in (tracks_path.resolve(), config_path.resolve()) for p in targets):
        raise ValueError('Output must not overwrite an input')
    config = load_config(config_path)
    detections = load_tracks(tracks_path)
    flags = analyze(detections, config)
    result = dict(schema_version=1, interpretation='heuristic_review_candidates_not_ground_truth',
                  input_file=str(tracks_path), input_sha256=hashlib.sha256(tracks_path.read_bytes()).hexdigest(),
                  frame_index_base=1, config=config,
                  summary=dict(rows=len(detections), tracks=len(by_track(detections)),
                               observed_frames=len({d.frame for d in detections}),
                               flags=len(flags), flagged_frames=len({f['frame_id'] for f in flags}),
                               empty_input=not detections), flags=flags)
    out_dir.mkdir(parents=True, exist_ok=True)
    with targets[0].open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(flags)
    targets[1].write_text(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + '\n', encoding='utf-8')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tracks', required=True, type=Path)
    parser.add_argument('--config', type=Path, default=DEFAULT_CONFIG)
    parser.add_argument('--out-dir', required=True, type=Path)
    args = parser.parse_args()
    try:
        result = review_file(args.tracks, args.config, args.out_dir)
    except (OSError, ValueError) as exc:
        parser.exit(2, f'ERROR: {exc}\n')
    print(json.dumps(result['summary']))
    print('Experimental heuristic candidates; review images before changing annotations.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
