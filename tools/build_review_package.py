"""Build offline prediction-only human review pages, not human results."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import shutil

from review_tracks import load_tracks

ROOT=Path(__file__).resolve().parents[1]
ASSETS=Path(__file__).resolve().parent/'human_review'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def payload(sequence,mode,tracks,events,images,total,source_hashes,practice=False):
    if mode not in ('A','B'):raise ValueError('Unknown mode')
    if total<1 or len(images)!=total:raise ValueError('Incomplete image set')
    boxes={str(i):[] for i in range(1,total+1)}
    for d in tracks:
        if not 1<=d.frame<=total:raise ValueError('Prediction beyond sequence')
        boxes[str(d.frame)].append(dict(id=d.track_id,x=d.x,y=d.y,w=d.w,h=d.h))
    required={'event_id','track_id','related_track_ids','start_frame','end_frame','anchor_frame','reasons','raw_flag_ids','context_start','context_end'}
    clean=[]
    if mode=='B':
        for e in events:
            if not required<=e.keys() or not 1<=e['context_start']<=e['start_frame']<=e['end_frame']<=e['context_end']<=total:raise ValueError('Invalid event context')
            clean.append({k:e[k] for k in sorted(required)})
    core=dict(sequence=sequence,mode=mode,total_frames=total,boxes=boxes,events=clean,images=images,source_hashes=source_hashes,practice=practice)
    core['package_id']=hashlib.sha256(json.dumps(core,sort_keys=True).encode()).hexdigest()
    return core


def render(template,data):
    # Prevent accidental script termination in embedded strings.
    return template.replace('__PAYLOAD__',json.dumps(data,ensure_ascii=False).replace('<','\\u003c'))


def build(out):
    if out.exists():raise ValueError('Output already exists; preserve collected sessions and package')
    # Validate every source before creating the package.
    inputs=[]
    for seq,total in [('0000',154),('0001',31)]:
        base=ROOT/f'data/external_validation/kitti_{seq}'
        pred=ROOT/f'outputs/external_validation/kitti_{seq}/tracks.txt'
        ev=ROOT/f'outputs/analyzer_v2_regression/kitti_{seq}/v2/review_events.json'
        images=[base/f'clip/img1/{f:06d}.jpg' for f in range(1,total+1)]
        if not all(p.exists() for p in images):raise ValueError(f'Missing image in {seq}')
        ds=load_tracks(pred);events=json.loads(ev.read_text())['events']
        hashes={str(p.relative_to(ROOT)):sha(p) for p in [pred,ev,ROOT/'tools/review_tracks_v2.py',ROOT/'configs/review_v2.json',ROOT/'configs/review_thresholds.json']}
        hashes.update({str(p.relative_to(ROOT)):sha(p) for p in sorted(ASSETS.iterdir()) if p.is_file()})
        inputs.append((seq,total,ds,events,images,hashes))
    out.mkdir(parents=True);(out/'assets').mkdir();(out/'collected').mkdir();(out/'qa').mkdir()
    for name in ['style.css','review.js','metrics.js','adjudication.js']:shutil.copy2(ASSETS/name,out/'assets'/name)
    manifest={};template=(ASSETS/'review.html').read_text(encoding='utf-8')
    for seq,total,ds,events,images,hashes in inputs:
        folder=out/'packages'/f'kitti_{seq}';(folder/'images').mkdir(parents=True)
        relative={str(i):f'images/{i:06d}.jpg' for i in range(1,total+1)}
        for i,p in enumerate(images,1):shutil.copy2(p,folder/relative[str(i)]);manifest[str(p.relative_to(ROOT))]=sha(p)
        manifest.update(hashes)
        for mode in ['A','B']:(folder/f'{mode}.html').write_text(render(template,payload('kitti_'+seq,mode,ds,events,relative,total,hashes)),encoding='utf-8')
    practice=out/'packages/practice';(practice/'images').mkdir(parents=True)
    for i in [1,2]:shutil.copy2(inputs[1][4][i-1],practice/f'images/{i:06d}.jpg')
    event=dict(event_id='PRACTICE',track_id=1,related_track_ids=[],start_frame=1,end_frame=2,anchor_frame=2,reasons=['practice_context'],raw_flag_ids=[],context_start=1,context_end=2)
    practice_data=payload('practice','B',[d for d in inputs[1][2] if d.frame<=2],[event],{str(i):f'images/{i:06d}.jpg' for i in [1,2]},2,{},True)
    (practice/'B.html').write_text(render(template,practice_data),encoding='utf-8')
    refs=[]
    with (ROOT/'outputs/analyzer_v2_regression/issue_capture.csv').open(encoding='utf-8-sig') as s:
        for r in csv.DictReader(s):
            if r['dataset'].startswith('kitti_'):refs.append(dict(sequence=r['dataset'],reference_issue_id=r['dataset']+':'+r['issue_id'],issue_type=r['issue_type'],note=r['note'],source=r['source']))
    (out/'historical_partial_reference.json').write_text(json.dumps(refs,indent=2),encoding='utf-8')
    admin=(ASSETS/'adjudication.html').read_text(encoding='utf-8').replace('__REFERENCES__',json.dumps(refs,ensure_ascii=False).replace('<','\\u003c'))
    (out/'adjudication.html').write_text(admin,encoding='utf-8')
    (out/'index.html').write_text('''<!doctype html><meta charset="utf-8"><title>Human review pilot</title><link rel="stylesheet" href="assets/style.css"><h1>Human-in-the-loop workflow pilot</h1><p>Chưa có human results. Đọc protocol trước; chọn group X/Y, ghi familiarity, không xem adjudication trước review.</p><p><a href="packages/practice/B.html">Practice (không tính human metrics)</a></p><table><tr><th>Sequence</th><th>Baseline A</th><th>Assisted B</th></tr><tr><td>KITTI0000 ·154 frames</td><td><a href="packages/kitti_0000/A.html">A0000</a></td><td><a href="packages/kitti_0000/B.html">B0000 ·12 events</a></td></tr><tr><td>KITTI0001 ·31 frames</td><td><a href="packages/kitti_0001/A.html">A0001</a></td><td><a href="packages/kitti_0001/B.html">B0001 ·7 events</a></td></tr></table><p>X: A0000 → B0001 → break≥24h nếu có thể → B0000 → A0001.</p><p>Y: B0000 → A0001 → break → A0000 → B0001.</p><p><a href="HUMAN_REVIEW_PROTOCOL.md">Protocol đi kèm</a></p><p><a href="adjudication.html">Adjudication & comparison — chỉ sau tất cả timed sessions</a></p><p>Giữ các JSON tải xuống. Giao diện không tự ghi file vào project. Không tune analyzer, không auto-correction.</p>''',encoding='utf-8')
    shutil.copy2(ROOT/'docs/HUMAN_REVIEW_PROTOCOL.md',out/'HUMAN_REVIEW_PROTOCOL.md')
    templates={
      'baseline_template.csv':['session_id','reviewer','sequence','mode','started_at','ended_at','active_seconds','wall_seconds','reviewed_frames','findings_reported','correction_actions_self_reported','finding_id','start_frame','end_frame','tracks','fix_type','note'],
      'assisted_template.csv':['session_id','reviewer','sequence','mode','started_at','ended_at','active_seconds','wall_seconds','reviewed_frames','findings_reported','correction_actions_self_reported','event_id','track_id','related_track_ids','context_start','context_end','verdict','fix_type','note'],
      'adjudication_template.csv':['session_id','sequence','finding_id','verdict','canonical_id','note','adjudicator','independence']}
    for name,fields in templates.items():
        with (out/name).open('w',newline='',encoding='utf-8') as s:csv.writer(s).writerow(fields)
    (out/'source_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    (out/'status.json').write_text(json.dumps(dict(status='READY_FOR_TECHNICAL_QA_HUMAN_COLLECTION_PENDING',human_sessions=0,human_results=None,reference_scope='historical_partial_v1',reference_counts={seq:sum(r['sequence']==seq for r in refs) for seq in ['kitti_0000','kitti_0001']}),indent=2))
    return out


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,default=ROOT/'outputs/human_review');a=p.parse_args()
    print(build(a.out))
