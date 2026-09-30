"""Reference-free experimental duplicate candidates and lossless review events."""
import argparse
from collections import defaultdict
import csv
import hashlib
import json
import math
from pathlib import Path

from motlib import by_frame, iou
from review_tracks import (DEFAULT_CONFIG, analyze, classes_compatible, load_config,
                           load_tracks, review_file)

DEFAULT_V2 = Path(__file__).resolve().parents[1] / 'configs/review_v2.json'


def validate_config(c):
    keys = {'status', 'duplicate_min_iou', 'duplicate_max_center_distance',
            'duplicate_max_size_ratio', 'duplicate_min_consecutive_frames', 'context_padding'}
    if set(c) != keys or c['status'] != 'experimental_uncalibrated':
        raise ValueError('Invalid experimental v2 config')
    for k in keys - {'status'}:
        if type(c[k]) not in (int, float) or not math.isfinite(c[k]):
            raise ValueError(f'Invalid {k}')
    if not 0 < c['duplicate_min_iou'] <= 1 or c['duplicate_max_center_distance'] < 0 or c['duplicate_max_size_ratio'] < 1:
        raise ValueError('Invalid geometry thresholds')
    if type(c['duplicate_min_consecutive_frames']) is not int or c['duplicate_min_consecutive_frames'] < 2:
        raise ValueError('Temporal evidence requires at least two consecutive frames')
    if type(c['context_padding']) is not int or c['context_padding'] < 0:
        raise ValueError('Invalid context padding')
    return c


def duplicate_flags(detections, config, class_compatibility=None):
    c = validate_config(config)
    pairs = defaultdict(list)
    for frame, boxes in sorted(by_frame(detections).items()):
        boxes = sorted(boxes, key=lambda d: d.track_id)
        for j, a in enumerate(boxes):
            for b in boxes[j+1:]:
                if a.track_id == b.track_id:
                    continue
                # Only comparable semantic classes can be duplicate tracks.
                # Legacy MOT rows have class_id=None and retain v1 behavior.
                if not classes_compatible(a.class_id, b.class_id, class_compatibility):
                    continue
                overlap = iou(a, b)
                distance = math.hypot(a.x+a.w/2-b.x-b.w/2, a.y+a.h/2-b.y-b.h/2)
                distance /= min(math.hypot(a.w, a.h), math.hypot(b.w, b.h))
                ratio = max(a.w/b.w, b.w/a.w, a.h/b.h, b.h/a.h)
                if overlap >= c['duplicate_min_iou'] and distance <= c['duplicate_max_center_distance'] and ratio <= c['duplicate_max_size_ratio']:
                    pairs[a.track_id, b.track_id].append((frame, overlap, distance, ratio))
    flags = []
    for (a, b), rows in sorted(pairs.items()):
        runs = []
        for row in rows:
            if not runs or row[0] != runs[-1][-1][0]+1:
                runs.append([])
            runs[-1].append(row)
        for run in runs:
            if len(run) < c['duplicate_min_consecutive_frames']:
                continue
            flags.append(dict(frame_id=run[c['duplicate_min_consecutive_frames']-1][0],
                track_id=a, related_track_id=b, previous_frame_id=run[0][0],
                start_frame=run[0][0], end_frame=run[-1][0], reason='possible_duplicate',
                observed_value=dict(consecutive_frames=len(run), min_iou=min(r[1] for r in run),
                    max_center_distance=max(r[2] for r in run), max_size_ratio=max(r[3] for r in run)),
                threshold={k: c[k] for k in sorted(c) if k.startswith('duplicate_')},
                explanation='Different IDs coexist with similar boxes in consecutive frames; geometry is not identity proof.'))
    return flags


def aggregate_events(flags, padding=2, total_frames=None):
    groups = {}
    for f in flags:
        related = [] if f['related_track_id'] is None else [f['related_track_id']]
        key = (f['track_id'], f['start_frame'], f['end_frame'], tuple(related))
        if key not in groups:
            groups[key] = dict(track_id=key[0], related_track_ids=related, start_frame=key[1],
                end_frame=key[2], anchor_frame=f['frame_id'], reasons=[], raw_flag_ids=[],
                class_id=f.get('class_id'),
                related_class_ids=[] if f.get('related_class_id') is None else [f.get('related_class_id')],
                context_start=max(1, key[1]-padding),
                context_end=min(total_frames, key[2]+padding) if total_frames is not None else key[2]+padding)
        e = groups[key]
        e['anchor_frame'] = min(e['anchor_frame'], f['frame_id'])
        e['reasons'] = sorted(set(e['reasons']+[f['reason']]))
        e['raw_flag_ids'].append(f['raw_flag_id'])
    events = sorted(groups.values(), key=lambda e: (e['start_frame'],e['end_frame'],e['track_id'],e['related_track_ids']))
    for n,e in enumerate(events,1):
        e['event_id'] = f'E{n:06d}'
        e['raw_flag_ids'].sort()
    return events


def analyze_v2(detections, v1_config, v2_config, total_frames=None,
               class_compatibility=None):
    validate_config(v2_config)
    if total_frames is not None and (type(total_frames) is not int or total_frames < max((d.frame for d in detections), default=0) or total_frames < 1):
        raise ValueError('total_frames must cover all predictions')
    legacy = analyze(detections, v1_config, class_compatibility)
    classes = {}
    for detection in detections:
        if detection.track_id not in classes or classes[detection.track_id] is None:
            classes[detection.track_id] = detection.class_id
    flags = [dict(f, start_frame=f['previous_frame_id'], end_frame=f['frame_id'],
                  class_id=classes.get(f['track_id']),
                  related_class_id=classes.get(f['related_track_id']) if f['related_track_id'] is not None else None)
             for f in legacy]
    flags += duplicate_flags(detections, v2_config, class_compatibility)
    for flag in flags:
        flag.setdefault('class_id', classes.get(flag['track_id']))
        flag.setdefault('related_class_id', classes.get(flag['related_track_id']) if flag['related_track_id'] is not None else None)
    flags.sort(key=lambda f: (f['frame_id'], f['track_id'], f['reason'], -1 if f['related_track_id'] is None else f['related_track_id']))
    for n,f in enumerate(flags,1):
        f['raw_flag_id'] = f'F{n:06d}'
    return dict(schema_version=2, interpretation='experimental_heuristic_candidates_not_ground_truth',
        v1_config=v1_config, v2_config=v2_config, total_frames=total_frames,
        class_compatibility=class_compatibility,
        context_limit='provided_total_frames' if total_frames is not None else 'unbounded_without_sequence_metadata',
        flags=flags, events=aggregate_events(flags,v2_config['context_padding'],total_frames))


def write_csv(path, rows, fields):
    with path.open('w',encoding='utf-8',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader()
        for row in rows:
            writer.writerow({k:json.dumps(row.get(k),sort_keys=True) if isinstance(row.get(k),(dict,list)) else row.get(k) for k in fields})


def review_v2(tracks, v1_config, v2_config, out, total_frames=None,
              class_compatibility=None):
    tracks,v1_config,v2_config,out=map(Path,(tracks,v1_config,v2_config,out))
    names=['review_flags_v2.json','review_flags_v2.csv','review_events.json','review_events.csv']
    if any((out/n).exists() or (out/n).resolve() in {tracks.resolve(),v1_config.resolve(),v2_config.resolve()} for n in names):
        raise ValueError('Use fresh output paths; refuse overwrite')
    result=analyze_v2(load_tracks(tracks),load_config(v1_config),validate_config(json.loads(v2_config.read_text(encoding='utf-8-sig'))),total_frames,class_compatibility)
    result.update(input_file=str(tracks),input_sha256=hashlib.sha256(tracks.read_bytes()).hexdigest())
    out.mkdir(parents=True,exist_ok=True)
    (out/names[0]).write_text(json.dumps(result,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    fields=['raw_flag_id','frame_id','track_id','related_track_id','class_id','related_class_id','reason','observed_value','threshold','previous_frame_id','start_frame','end_frame','explanation']
    write_csv(out/names[1],result['flags'],fields)
    (out/names[2]).write_text(json.dumps(dict(schema_version=2,events=result['events']),indent=2)+'\n',encoding='utf-8')
    write_csv(out/names[3],result['events'],['event_id','track_id','related_track_ids','class_id','related_class_ids','start_frame','end_frame','anchor_frame','reasons','raw_flag_ids','context_start','context_end'])
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--tracks',required=True,type=Path);p.add_argument('--out-dir',required=True,type=Path)
    p.add_argument('--config',type=Path,default=DEFAULT_CONFIG);p.add_argument('--v2-config',type=Path,default=DEFAULT_V2)
    p.add_argument('--total-frames',type=int);p.add_argument('--compat-v1',action='store_true')
    a=p.parse_args()
    try:
        if a.compat_v1:
            if any((a.out_dir/n).exists() for n in ['review_flags.csv','review_flags.json']):raise ValueError('Use fresh output paths')
            result=review_file(a.tracks,a.config,a.out_dir)
        else:result=review_v2(a.tracks,a.config,a.v2_config,a.out_dir,a.total_frames)
    except (OSError,ValueError) as exc:p.exit(2,f'ERROR: {exc}\n')
    print(json.dumps(dict(flags=len(result['flags']),events=len(result.get('events',[])))))


if __name__=='__main__':main()
