"""Post-lock evidence for the pinned external sample; never changes predictions."""
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from motlib import parse_mot, by_frame, by_track, iou
from validate_review_flags import matching_trace, spans, write_csv, REASONS
from visualize_tracks import dashed_rectangle

ROOT=Path(__file__).resolve().parents[1]
B=ROOT/'data/external_validation/kitti_0001'
O=ROOT/'outputs/external_validation/kitti_0001'


def main():
    lock=json.loads((O/'blind_lock.json').read_text())
    for name, sha in {**lock['protected_hashes'],**lock['outputs']}.items():
        path=O/'preblind_dataset_protocol.md' if name.replace('\\','/')=='docs/EXTERNAL_DATASET.md' else ROOT/name
        assert hashlib.sha256(path.read_bytes()).hexdigest()==sha, name
    gt=parse_mot(B/'gt/gt.txt'); pred=parse_mot(O/'tracks.txt')
    gf,pf,gt_t,pt=by_frame(gt),by_frame(pred),by_track(gt),by_track(pred)
    audit=json.loads((B/'conversion_audit.json').read_text())
    ignored=defaultdict(list)
    for r in audit['records']:
        if not r['kept']: ignored[r['frame_id']].append(r)
    flags=json.loads((O/'review/review_flags.json').read_text())['flags']
    trace,clear=matching_trace(gt,pred)
    ev=json.loads((O/'evaluation.json').read_text())
    assert all(clear[k]==ev['metrics'][k] for k in ('FP','FN','IDSW'))
    owners=defaultdict(Counter); inverse=defaultdict(set); matches=[]
    for frame,pairs,fn,fp in trace:
        for g,p,s in pairs:
            owners[p.track_id][g.track_id]+=1; inverse[g.track_id].add(p.track_id)
            matches.append(dict(frame_id=frame,gt_track_id=g.track_id,pred_track_id=p.track_id,iou=s))
    write_csv(O/'clear_matches.csv',matches,['frame_id','gt_track_id','pred_track_id','iou'])
    scope=spans(flags,31,2); issues=[]
    def ignore_overlap(p):
        vals=[]
        for r in ignored[p.frame]:
            l,t,rr,b=r['bbox_ltrb']; inter=max(0,min(p.x+p.w,rr)-max(p.x,l))*max(0,min(p.y+p.h,b)-max(p.y,t))
            vals.append(inter/(p.w*p.h))
        return max(vals,default=0)
    def add(frame,gid,pid,kind,note,status='REFERENCE_DIAGNOSTIC'):
        relevant={pid} if pid is not None else inverse[gid]
        exact=any(f['frame_id']==frame and f['track_id'] in relevant for f in flags)
        context=any(f['track_id'] in relevant and f['previous_frame_id']-2<=frame<=f['frame_id']+2 for f in flags)
        issues.append(dict(frame_id=frame,gt_track_id=gid,pred_track_id=pid,error_type=kind,
                           analyzer_flagged=exact,same_track_context=context,
                           validation_status=status,note=note))
    for frame,pairs,fn,fp in trace:
        for g in fn: add(frame,g.track_id,None,'missed_detection','CLEAR unmatched GT at IoU>=0.5')
        for p in fp:
            overlap=ignore_overlap(p)
            add(frame,None,p.track_id,'unmatched_prediction',f'Raw FP; max intersection/pred area with excluded region={overlap:.6f}; not automatically a hallucination',
                'UNCERTAIN' if overlap>0 else 'REFERENCE_DIAGNOSTIC')
    for r in ev['diagnostics']['loose_boxes']:
        add(r['frame'],r['gt_track'],r['pred_track'],'loose_box',f"Existing best-IoU criterion: {r['iou']}")
    for gid in ev['diagnostics']['missed_gt_tracks']:
        add(gt_t[gid][0].frame,gid,None,'missed_track',f'No best-IoU match across {len(gt_t[gid])} reference boxes; G10_context.jpg shows car with no prediction. Analyst-confirmed on this sample.', 'TRUE_ISSUE')
    # Diagnose fragmentation is best-IoU evidence, distinct from CLEAR IDSW.
    for r in ev['diagnostics']['fragmented_gt_tracks']:
        gid=r['gt_track']
        add(gt_t[gid][0].frame,gid,None,'fragmentation_candidate',f"Best-IoU owners {r['pred_tracks']}; verify overlapping tracks/duplicate boxes before asserting switch",'UNCERTAIN')
    for r in clear['switches']:
        add(r['frame'],r['gt_track'],r['to_track'],'id_switch',str(r),'TRUE_ISSUE')
    for pid, counts in owners.items():
        if len(counts)>1:
            first=min(r['frame_id'] for r in matches if r['pred_track_id']==pid and r['gt_track_id']!=max(counts,key=counts.get))
            add(first,None,pid,'reference_identity_merge_candidate',
                f'One pred matched multiple GT identities {dict(counts)}; CLEAR IDSW can remain zero. Overlapping/occluded reference boxes require independent adjudication.', 'UNCERTAIN')
    fields=list(issues[0]); write_csv(O/'reference_issues.csv',issues,fields)
    write_csv(O/'missed_issues.csv',[r for r in issues if not r['analyzer_flagged']],fields)
    vis=O/'images'; vis.mkdir(exist_ok=True); (vis/'frames').mkdir(exist_ok=True)
    font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',16)
    def panel(frame,selected=None):
        im=Image.open(B/'source/data/KITTI/image_2/0001'/f'{frame-1:06d}.png').convert('RGB'); d=ImageDraw.Draw(im)
        for r in ignored[frame]: d.rectangle(r['bbox_ltrb'],outline='gray',width=1)
        for g in gf.get(frame,[]):
            box=(g.x,g.y,g.x+g.w,g.y+g.h); dashed_rectangle(d,box,(0,255,0),2)
            d.text((g.x,g.y-17),f'G{g.track_id}',font=font,fill='lime',stroke_width=1,stroke_fill='black')
        for p in pf.get(frame,[]):
            c='red' if selected is None or p.track_id==selected else 'cyan'
            d.rectangle((p.x,p.y,p.x+p.w,p.y+p.h),outline=c,width=2)
            d.text((p.x,p.y+p.h),f'P{p.track_id}',font=font,fill=c,stroke_width=1,stroke_fill='black')
        d.rectangle((0,0,950,23),fill='black'); d.text((4,2),f'MOT {frame} / KITTI {frame-1} | GT green G=t+1, pred red/cyan, DontCare gray',font=font,fill='white')
        return im
    for frame in range(1,32): panel(frame).save(vis/'frames'/f'{frame:06d}.jpg',quality=95)
    events=sorted({(f['track_id'],f['previous_frame_id'],f['frame_id']) for f in flags})
    for tid,start,end in events:
        chosen=sorted({max(1,start-1),start,min(start+1,end),max(start,end-1),end,min(31,end+1)})
        sheet=Image.new('RGB',(1242,410*len(chosen)),(20,20,20)); draw=ImageDraw.Draw(sheet)
        for j,fr in enumerate(chosen):
            sheet.paste(panel(fr,tid),(0,410*j+30)); draw.text((4,410*j+4),f'P{tid} gap {start}->{end}; inspect full context frames for interiors',font=font,fill='white')
        sheet.save(vis/f'flag_P{tid}_{start}_{end}.jpg',quality=95)
    # Cropped contact sheets for all flagged tracks, missed GT and fragmentation candidate.
    for key,ids,frames in [('P8',('p',8),range(1,21)),('P64',('p',64),range(15,32)),('P92',('p',92),range(24,32)),
                          ('G7',('g',7),range(1,32)),('G10',('g',10),[g.frame for g in gt_t[10]])]:
        target=pt[ids[1]] if ids[0]=='p' else gt_t[ids[1]]
        l=max(0,int(min(x.x for x in target))-30); t=max(0,int(min(x.y for x in target))-25)
        r=min(1242,int(max(x.x+x.w for x in target))+30); b=min(375,int(max(x.y+x.h for x in target))+35)
        frames=list(frames); sheet=Image.new('RGB',(1000,230*((len(frames)+3)//4)),(20,20,20)); d=ImageDraw.Draw(sheet)
        for j,fr in enumerate(frames):
            tile=panel(fr,ids[1] if ids[0]=='p' else None).crop((l,t,r,b)); tile.thumbnail((248,200))
            x=(j%4)*250; y=(j//4)*230; sheet.paste(tile,(x,y+25)); d.text((x+3,y+3),f'{key} frame {fr}',font=font,fill='white')
        sheet.save(vis/(key+'_context.jpg'),quality=95)
    decisions=json.loads((O/'adjudications.json').read_text()) if (O/'adjudications.json').exists() else {}
    labels=[]
    for n,f in enumerate(flags,1):
        decision=decisions.get(str(n),{'label':'UNCERTAIN','note':'Not yet visually adjudicated'})
        labels.append(dict(flag_id=n,**f,**decision,visualization=f"images/flag_P{f['track_id']}_{f['previous_frame_id']}_{f['frame_id']}.jpg"))
    write_csv(O/'flag_labels.csv',labels,list(labels[0]))
    rule_rows=[]
    for reason in REASONS:
        rows=[r for r in labels if r['reason']==reason]; counts=Counter(r['label'] for r in rows)
        resolved=sum(counts[k] for k in ('TRUE_ISSUE','BENIGN_EVENT','FALSE_ALERT'))
        rule_rows.append(dict(reason=reason,flags=len(rows),**{k:counts[k] for k in ('TRUE_ISSUE','BENIGN_EVENT','FALSE_ALERT','UNCERTAIN')},
                              preliminary_precision=counts['TRUE_ISSUE']/resolved if resolved else None))
    write_csv(O/'rule_summary.csv',rule_rows,list(rule_rows[0]))
    summary=dict(metrics=ev['metrics'],flags=len(flags),rules=rule_rows,owners={k:dict(v) for k,v in owners.items()},
                 scope=scope,scope_frames=sum(b-a+1 for a,b in scope),
                 reference_issue_atoms=dict(Counter(r['error_type'] for r in issues)),
                 missed_exact_atoms=dict(Counter(r['error_type'] for r in issues if not r['analyzer_flagged'])),
                 protected_hashes_verified=True,blind_lock_utc=lock['locked_utc'])
    (O/'validation_summary.json').write_text(json.dumps(summary,indent=2))
    print(json.dumps(summary,indent=2))


if __name__=='__main__': main()
