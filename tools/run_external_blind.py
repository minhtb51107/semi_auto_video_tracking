"""Prepare an acquired sequence and invoke frozen tracker/analyzer without GT."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import cv2

ROOT=Path(__file__).resolve().parents[1]
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def now(): return datetime.datetime.now(datetime.timezone.utc).isoformat()


def prepare(images,clip):
    paths=sorted(images.glob('*.png'))
    if not paths or [int(p.stem) for p in paths]!=list(range(len(paths))):
        raise ValueError('Require complete zero-based image sequence')
    if clip.exists(): raise ValueError('Preserve existing clip')
    (clip/'img1').mkdir(parents=True); rows=[]; sizes=set()
    for i,p in enumerate(paths,1):
        im=cv2.imread(str(p))
        if im is None: raise ValueError(f'Invalid image {p}')
        h,w=im.shape[:2]; sizes.add((w,h)); dst=clip/'img1'/f'{i:06d}.jpg'
        if not cv2.imwrite(str(dst),im,[cv2.IMWRITE_JPEG_QUALITY,95]): raise ValueError('JPEG write failed')
        rows.append(dict(kitti_frame=i-1,mot_frame=i,source=p.name,source_sha256=sha(p),jpeg=dst.name,jpeg_sha256=sha(dst),width=w,height=h))
    if len(sizes)!=1: raise ValueError('Changing image size')
    (clip/'seqinfo.ini').write_text(f'[Sequence]\nname={clip.parent.name}\nimDir=img1\nseqLength={len(rows)}\nimWidth={w}\nimHeight={h}\nimExt=.jpg\n')
    return rows


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--sequence',required=True);a=p.parse_args()
    b=ROOT/f'data/external_validation/kitti_{a.sequence}';o=ROOT/f'outputs/external_validation/kitti_{a.sequence}'
    if o.exists(): raise ValueError('Preserve existing run')
    if (b/'source/training/label_02'/f'{a.sequence}.txt').exists(): raise ValueError('This blind runner requires GT not yet downloaded')
    o.mkdir(parents=True)
    protected=[ROOT/'tools'/n for n in ['run_tracker.py','review_tracks.py','motlib.py','evaluate_tracking.py','evaluate_kitti_semantics.py','kitti_tracking_to_mot.py']]
    protected += [ROOT/'configs/review_thresholds.json',ROOT/'yolo26n.pt',ROOT/'.venv/Lib/site-packages/ultralytics/cfg/trackers/bytetrack.yaml']
    record=dict(started_utc=now(),protected_hashes={str(p.relative_to(ROOT)):sha(p) for p in protected},commands=[])
    # Preserve hashes of every round1 file including the adapter outputs.
    old=ROOT/'outputs/external_validation/kitti_0001'
    record['round1_hashes']={str(p.relative_to(ROOT)):sha(p) for p in old.rglob('*') if p.is_file()}
    (o/'preblind_dataset_protocol.md').write_bytes((ROOT/'docs/EXTERNAL_VALIDATION_02_DATASET.md').read_bytes())
    record['protocol_sha256']=sha(o/'preblind_dataset_protocol.md')
    (o/'blind_protocol.json').write_text(json.dumps(record,indent=2))
    manifest=prepare(b/f'source/training/image_02/{a.sequence}',b/'clip')
    (b/'frame_manifest.json').write_text(json.dumps(manifest,indent=2))
    record['source_manifest_sha256']=sha(b/'images_download.json')
    record['frame_manifest_sha256']=sha(b/'frame_manifest.json')
    env=os.environ.copy();env.pop('PYTHONPATH',None);env.pop('PYTHONHOME',None)
    env['PYTHONNOUSERSITE']='1';env['YOLO_CONFIG_DIR']=str(ROOT/'.runtime/ultralytics')
    for name,args in [('tracker',['tools/run_tracker.py','--clip',str(b/'clip'),'--model','yolo26n.pt','--tracker','bytetrack.yaml','--device','cpu','--out',str(o/'tracks.txt')]),
                      ('review',['tools/review_tracks.py','--tracks',str(o/'tracks.txt'),'--out-dir',str(o/'review')])]:
        cmd=[sys.executable,'-X','utf8',*args]; start=now(); result=subprocess.run(cmd,cwd=ROOT,env=env,capture_output=True)
        (o/f'{name}.log').write_bytes(result.stdout+result.stderr)
        record['commands'].append(dict(command=cmd,start_utc=start,end_utc=now(),exit_code=result.returncode))
        print(name,result.returncode,(result.stdout+result.stderr).decode('utf-8',errors='replace')[-1200:],flush=True)
        if result.returncode: raise RuntimeError(f'{name} failed')
    assert all(sha(ROOT/p)==h for p,h in record['protected_hashes'].items())
    record['outputs']={str(p.relative_to(ROOT)):sha(p) for p in [o/'tracks.txt',o/'review/review_flags.json',o/'review/review_flags.csv']}
    record['locked_utc']=now();record['gt_present_before_lock']=False
    (o/'blind_lock.json').write_text(json.dumps(record,indent=2));print('BLIND LOCK COMPLETE',flush=True)


if __name__=='__main__':main()
