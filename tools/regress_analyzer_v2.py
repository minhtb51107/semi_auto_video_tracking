"""Offline regression on stored predictions; no tracker or reference access."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from review_tracks import DEFAULT_CONFIG,review_file
from review_tracks_v2 import DEFAULT_V2,review_v2

ROOT=Path(__file__).resolve().parents[1]
DATASETS={
    'clip_01':('outputs/runs/renamed_verified/clip_01',190),
    'clip_02':('outputs/runs/renamed_verified/clip_02',60),
    'kitti_0001':('outputs/external_validation/kitti_0001',31),
    'kitti_0000':('outputs/external_validation/kitti_0000',154)}


def main():
    out=ROOT/'outputs/analyzer_v2_regression'
    if (out/'summary.json').exists():raise ValueError('Regression already exists; preserve it')
    out.mkdir(exist_ok=True)
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    (out/'frozen_runtime.json').write_text(json.dumps({str(p.relative_to(ROOT)):sha(p) for p in [ROOT/'tools/review_tracks.py',ROOT/'tools/review_tracks_v2.py',DEFAULT_CONFIG,DEFAULT_V2]},indent=2))
    rows=[]
    for name,(folder,total) in DATASETS.items():
        tracks=Path(folder)/'tracks.txt';dest=out/name
        if dest.exists():raise ValueError(f'Output exists: {dest}')
        v1=review_file(tracks,DEFAULT_CONFIG,dest/'v1')
        subprocess.run([sys.executable,'tools/review_tracks_v2.py','--tracks',str(tracks),'--out-dir',str(dest/'compat_v1'),'--compat-v1'],check=True,cwd=ROOT)
        for ext in ('csv','json'):
            assert (dest/f'v1/review_flags.{ext}').read_bytes()==(dest/f'compat_v1/review_flags.{ext}').read_bytes()
        previous=json.loads((ROOT/folder/'review/review_flags.json').read_text())
        assert v1['flags']==previous['flags'] and v1['input_sha256']==previous['input_sha256']
        v2=review_v2(tracks,DEFAULT_CONFIG,DEFAULT_V2,dest/'v2',total)
        legacy=[{k:f[k] for k in previous['flags'][0]} for f in v2['flags'] if f['reason']!='possible_duplicate']
        assert legacy==v1['flags']
        new=[f for f in v2['flags'] if f['reason']=='possible_duplicate']
        rows.append(dict(dataset=name,frames=total,v1_flags=len(v1['flags']),v2_flags=len(v2['flags']),events=len(v2['events']),duplicate_flags=len(new),duplicates=new,compatibility_bytes_equal=True,legacy_flags_equal=True))
    (out/'summary.json').write_text(json.dumps(rows,indent=2));print(json.dumps(rows,indent=2))


if __name__=='__main__':main()
