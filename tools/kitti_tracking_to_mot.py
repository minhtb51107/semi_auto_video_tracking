"""Convert KITTI tracking GT only; fixed custom vehicle policy, not KITTI scoring."""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path

KEEP = {'Car', 'Van', 'Truck'}
TYPES = KEEP | {'Pedestrian', 'Person_sitting', 'Cyclist', 'Tram', 'Misc', 'DontCare'}


def convert(label: Path, images: Path):
    paths = sorted(images.glob('*.png'))
    frames = [int(p.stem) for p in paths]
    if not frames or frames != list(range(len(frames))):
        raise ValueError('Require complete consecutive image indices starting at zero')
    records, mot, seen, classes = [], [], set(), {}
    for number, line in enumerate(label.read_text(encoding='utf-8').splitlines(), 1):
        if not line.strip():
            continue
        parts = line.split()
        if len(parts) != 17:
            raise ValueError(f'Line {number}: expected 17 KITTI tracking GT fields')
        frame, tid = int(parts[0]), int(parts[1])
        kind = parts[2]
        values = list(map(float, parts[3:]))
        if frame not in frames or kind not in TYPES or not all(map(math.isfinite, values)):
            raise ValueError(f'Line {number}: invalid frame/type/nonfinite value')
        left, top, right, bottom = values[3:7]
        if right <= left or bottom <= top:
            raise ValueError(f'Line {number}: invalid bbox')
        if kind != 'DontCare':
            if tid < 0 or (frame, tid) in seen:
                raise ValueError(f'Line {number}: invalid/duplicate track ID')
            seen.add((frame, tid))
            if tid in classes and classes[tid] != kind:
                raise ValueError(f'Line {number}: inconsistent track class')
            classes[tid] = kind
        keep = kind in KEEP
        records.append(dict(source_line=number, kitti_frame=frame, frame_id=frame+1,
                            kitti_track_id=tid, mot_track_id=tid+1 if keep else None,
                            type=kind, kept=keep, truncated=values[0], occluded=values[1],
                            bbox_ltrb=[left, top, right, bottom]))
        if keep:
            mot.append((frame+1, tid+1, left, top, right-left, bottom-top))
    if not mot or {r['kitti_frame'] for r in records} != set(frames):
        raise ValueError('Sample lacks vehicle labels or label coverage for every image')
    text = ''.join(f'{f},{t},{x:.6f},{y:.6f},{w:.6f},{h:.6f},1,-1,-1,-1\n'
                   for f,t,x,y,w,h in sorted(mot))
    metadata = dict(policy='custom Car+Van+Truck; no difficulty/ignore suppression',
                    label_sha256=hashlib.sha256(label.read_bytes()).hexdigest(),
                    frames=len(frames), original_rows=len(records), kept_rows=len(mot),
                    kept_tracks=len({r[1] for r in mot}),
                    class_rows=dict(Counter(r['type'] for r in records)),
                    mapping='frame+1, track_id+1; xywh=(left,top,right-left,bottom-top)',
                    records=records)
    return text, metadata


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--labels', required=True, type=Path)
    parser.add_argument('--images', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--audit', required=True, type=Path)
    args=parser.parse_args()
    if args.out.resolve() == args.audit.resolve() or any(p.exists() for p in (args.out,args.audit)):
        parser.error('Outputs must be distinct new paths; preserve source/evidence')
    text, metadata=convert(args.labels,args.images)
    for p in (args.out,args.audit):
        p.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(text,encoding='utf-8')
    args.audit.write_text(json.dumps(metadata,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in metadata.items() if k!='records'}))


if __name__=='__main__':
    main()
