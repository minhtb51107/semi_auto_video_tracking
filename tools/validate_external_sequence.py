"""GT-assisted validation evidence only; no tracker/analyzer modifications."""
import argparse
from collections import Counter,defaultdict
import csv
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
from motlib import by_frame,by_track,iou,parse_mot
from validate_review_flags import matching_trace,spans,write_csv,REASONS
from visualize_tracks import dashed_rectangle

ROOT=Path(__file__).resolve().parents[1]


def verify_lock(root,base,out):
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    lock=json.loads((out/'blind_lock.json').read_text())
    checks={p:sha(root/p)==h for p,h in {**lock['protected_hashes'],**lock['outputs'],**lock['round1_hashes']}.items()}
    for file,key in [('images_download.json','source_manifest_sha256'),('frame_manifest.json','frame_manifest_sha256')]:
        checks[file]=sha(base/file)==lock[key]
    checks['preblind_dataset_protocol.md']=sha(out/'preblind_dataset_protocol.md')==lock['protocol_sha256']
    manifest=json.loads((base/'images_download.json').read_text())
    for r in manifest['files']:checks[r['path']]=sha(base/'source'/r['path'])==r['sha256']
    frames=json.loads((base/'frame_manifest.json').read_text())
    for r in frames:checks['jpeg/'+r['jpeg']]=sha(base/'clip/img1'/r['jpeg'])==r['jpeg_sha256']
    bad=[p for p,ok in checks.items() if not ok]
    if bad:raise ValueError(f'Blind integrity failure: {bad}')
    if len(frames)!=len(manifest['files']):raise ValueError('Image count mismatch')
    return dict(verified_utc=datetime.now(timezone.utc).isoformat(),checks=len(checks),source_images=len(frames),all_pass=True,blind_lock_sha256=sha(out/'blind_lock.json'))


def consolidate_events(events):
    """Explicit adjudication links only: never infer shared physical identity."""
    groups={}
    for e in events:
        key=e['review_event_id']
        if key not in groups:
            groups[key]=dict(event_id=key,raw_groups=[],track_ids=[],start_frame=e['start_frame'],end_frame=e['end_frame'],reasons=[],flag_ids=[],verdict=e['verdict'],evidence_images=[],evidence_notes=[],gt_association=[],dontcare_status=[])
        g=groups[key]
        if g['verdict']!=e['verdict']:raise ValueError('Merged events must have a consistent verdict')
        g['raw_groups'].append(e['event_id']);g['track_ids'].append(e['track_id'])
        g['start_frame']=min(g['start_frame'],e['start_frame']);g['end_frame']=max(g['end_frame'],e['end_frame'])
        g['reasons']=sorted(set(g['reasons']+e['reasons']));g['flag_ids']+=e['flag_ids']
        for dest,source in [('evidence_images','evidence_image'),('evidence_notes','evidence_note'),('gt_association','gt_association'),('dontcare_status','dontcare_status')]:g[dest].append(e[source])
    return list(groups.values())


def group_flags(flags):
    groups={}
    for index,f in enumerate(flags,1):
        key=(f['track_id'],f['previous_frame_id'],f['frame_id'],f['related_track_id'])
        if key not in groups:groups[key]=dict(event_id=f'R{len(groups)+1:03d}',track_id=key[0],start_frame=key[1],end_frame=key[2],related_track_id=key[3],reasons=[],flag_ids=[])
        groups[key]['reasons'].append(f['reason']);groups[key]['flag_ids'].append(index)
    return list(groups.values())


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--sequence',required=True);args=parser.parse_args()
    b=ROOT/f'data/external_validation/kitti_{args.sequence}';o=ROOT/f'outputs/external_validation/kitti_{args.sequence}'
    integrity=verify_lock(ROOT,b,o)
    (o/'integrity_verified.json').write_text(json.dumps(integrity,indent=2))
    gt=parse_mot(b/'gt/gt.txt');pred=parse_mot(o/'tracks.txt');gf,pf=by_frame(gt),by_frame(pred);gt_t,pt=by_track(gt),by_track(pred)
    total=len(json.loads((b/'frame_manifest.json').read_text()));audit=json.loads((b/'conversion_audit.json').read_text())
    raw=json.loads((o/'evaluation.json').read_text());adjusted=json.loads((o/'kitti_semantics/evaluation.json').read_text())
    prep={(int(r['frame_id']),int(r['pred_track_id'])):r for r in csv.DictReader((o/'kitti_semantics/prediction_preprocessing_audit.csv').open(encoding='utf-8-sig'))}
    flags=json.loads((o/'review/review_flags.json').read_text())['flags'];events=group_flags(flags)
    trace,clear=matching_trace(gt,pred);assert all(clear[k]==raw['metrics'][k] for k in ['FP','FN','IDSW'])
    matches={};owners=defaultdict(Counter);gt_owners=defaultdict(Counter)
    for f,pairs,_,_ in trace:
        for g,p,s in pairs:matches[f,p.track_id]=(g.track_id,s);owners[p.track_id][g.track_id]+=1;gt_owners[g.track_id][p.track_id]+=1
    association=[]
    for p in pred:
        score,gid=max(((iou(g,p),g.track_id) for g in gf.get(p.frame,[])),default=(0,None))
        row=prep[p.frame,p.track_id]
        association.append(dict(frame_id=p.frame,pred_track_id=p.track_id,best_gt_track_id=gid,best_iou=score,clear_gt_track_id=matches.get((p.frame,p.track_id),('',0))[0],kitti_status=row['status'],dontcare_ioa=row['max_dontcare_ioa']))
    write_csv(o/'association_by_frame.csv',association,list(association[0]))
    coverage=[]
    for gid,track in gt_t.items():
        coverage.append(dict(gt_track_id=gid,start_frame=track[0].frame,end_frame=track[-1].frame,gt_boxes=len(track),clear_matched_boxes=sum(gt_owners[gid].values()),any_pred_iou_ge_05=sum(any(iou(g,p)>=.5 for p in pf.get(g.frame,[])) for g in track),clear_pred_ids=str(dict(gt_owners[gid]))))
    write_csv(o/'track_coverage.csv',coverage,list(coverage[0]))
    candidates=[]
    def add(kind,start,end,gid=None,pid=None,related=None,note=''):
        relevant={pid,related}-{None}
        targeted=any(e['track_id'] in relevant and e['start_frame']<=end and e['end_frame']>=start for e in events)
        candidates.append(dict(event_id=f'M{len(candidates)+1:03d}',error_type=kind,start_frame=start,end_frame=end,gt_track_id=gid,pred_track_id=pid,related_track_id=related,analyzer_targeted=targeted,note=note))
    for gid,track in gt_t.items():
        if not gt_owners[gid]:add('missed_track',track[0].frame,track[-1].frame,gid=gid,note=f'No CLEAR match across {len(track)} GT boxes')
    dup=defaultdict(list)
    for frame,ps in pf.items():
        for j,p in enumerate(ps):
            gp=max(((iou(g,p),g.track_id) for g in gf.get(frame,[])),default=(0,None))
            for q in ps[j+1:]:
                gq=max(((iou(g,q),g.track_id) for g in gf.get(frame,[])),default=(0,None))
                if gp[0]>=.5 and gq[0]>=.5 and gp[1]==gq[1] and iou(p,q)>=.5:
                    dup[(gp[1],min(p.track_id,q.track_id),max(p.track_id,q.track_id))].append(frame)
    for (gid,pid,qid),frames in sorted(dup.items()):add('duplicate_prediction',min(frames),max(frames),gid,pid,qid,f'Candidate overlap in frames {frames}; verify physical duplication visually')
    for s in clear['switches']:add('gt_to_pred_id_switch',s['frame'],s['frame'],s['gt_track'],s['to_track'],s['from_track'],'CLEAR switch; inspect context')
    for pid,own in owners.items():
        if len(own)>1:add('possible_identity_merge',pt[pid][0].frame,pt[pid][-1].frame,pid=pid,note=f'CLEAR GT ownership: {dict(own)}')
    for r in raw['diagnostics']['fragmented_gt_tracks']:
        gid=r['gt_track'];add('fragmentation_candidate',gt_t[gid][0].frame,gt_t[gid][-1].frame,gid=gid,note=f"Best-IoU owners {r['pred_tracks']}; not a confirmed split")
    for pid,track in pt.items():
        if not owners[pid]:add('ghost_candidate',track[0].frame,track[-1].frame,pid=pid,note='No CLEAR owner; inspect DontCare/duplicate/localization before verdict')
        else:
            gid=owners[pid].most_common(1)[0][0];after=[p.frame for p in track if p.frame>gt_t[gid][-1].frame]
            if after:add('false_continuation_candidate',min(after),max(after),gid,pid,note='Prediction continues after majority-reference lifetime; check edge/DontCare')
    # Find geometry mismatch beyond flags, in runs of frames; candidates are not labels.
    loc=defaultdict(list)
    for f,_,missing,_ in trace:
        for g in missing:
            best=max(((iou(g,p),p.track_id) for p in pf.get(f,[])),default=(0,None))
            if .1<=best[0]<.5:loc[g.track_id,best[1]].append(f)
    for (gid,pid),frames in sorted(loc.items()):add('large_localization_error_candidate',min(frames),max(frames),gid,pid,note=f'Unmatched GT with bestIoU0.1..0.5 at frames {frames}')
    decisions=json.loads((o/'adjudications.json').read_text()) if (o/'adjudications.json').exists() else {}
    vis=o/'images';vis.mkdir(exist_ok=True);(vis/'frames').mkdir(exist_ok=True)
    font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',16);ignored=defaultdict(list)
    for r in audit['records']:
        if not r['kept']:ignored[r['frame_id']].append(r)
    def draw_frame(f):
        im=Image.open(b/f'source/training/image_02/{args.sequence}/{f-1:06d}.png').convert('RGB');d=ImageDraw.Draw(im)
        for r in ignored[f]:d.rectangle(r['bbox_ltrb'],outline='gray',width=1)
        for g in gf.get(f,[]):
            dashed_rectangle(d,g.corners,(0,255,0),2);d.text((g.x,g.y-17),f'G{g.track_id}',font=font,fill='lime',stroke_width=1,stroke_fill='black')
        for p in pf.get(f,[]):
            d.rectangle(p.corners,outline='red',width=2);d.text((p.x,p.y+p.h),f'P{p.track_id}',font=font,fill='red',stroke_width=1,stroke_fill='black')
        d.rectangle((0,0,850,22),fill='black');d.text((3,2),f'MOT {f} KITTI {f-1}: green GT IDs=KITTI+1, red predictions, gray ignored',font=font,fill='white')
        return im
    for f in range(1,total+1):draw_frame(f).save(vis/'frames'/f'{f:06d}.jpg',quality=95)
    for event in events+candidates:
        start,end=event['start_frame'],event['end_frame'];pid=event.get('track_id',event.get('pred_track_id'));gid=event.get('gt_track_id')
        selected=sorted({max(1,start-1),start,min(total,start+1),(start+end)//2,max(start,end-1),end,min(total,end+1)})
        target=[p for p in pt.get(pid,[]) if max(1,start-2)<=p.frame<=min(total,end+2)]
        if gid is not None:target += [g for g in gt_t[gid] if start<=g.frame<=end]
        if not target:target=[g for g in gt if g.track_id==gid]
        w,h=draw_frame(start).size
        bbox=(0,0,w,h) if not target else (max(0,int(min(d.x for d in target))-30),max(0,int(min(d.y for d in target))-30),min(w,int(max(d.x+d.w for d in target))+30),min(h,int(max(d.y+d.h for d in target))+35))
        sheet=Image.new('RGB',(1000,270*((len(selected)+2)//3)),(20,20,20));dr=ImageDraw.Draw(sheet)
        for j,f in enumerate(selected):
            tile=draw_frame(f).crop(bbox);tile.thumbnail((330,240));x=(j%3)*333;y=(j//3)*270
            sheet.paste(tile,(x,y+25));dr.text((x+3,y+2),f"{event['event_id']} f{f} P{pid} G{gid}",font=font,fill='white')
        name=f"images/{event['event_id']}.jpg";sheet.save(o/name,quality=95);event['evidence_image']=name
        event.update(dict(verdict='UNCERTAIN',evidence_note='Candidate is not truth; insufficient visual/reference evidence',review_event_id=event['event_id'],confirmed_event_id=''))
        event.update(decisions.get(event['event_id'],{}))
        involved=[p for p in pred if p.track_id==pid and start<=p.frame<=end]
        event['gt_association']=str(dict(owners[pid])) if pid is not None else str(gid)
        event['dontcare_status']=str(Counter('strong' if float(prep[p.frame,p.track_id]['max_dontcare_ioa'])>.5 else 'weak' if float(prep[p.frame,p.track_id]['max_dontcare_ioa'])>0 else 'none' for p in involved))
    # Full-width context for confirmed splits: include old ID's last frame and new ID's first,
    # which can precede the CLEAR switch frame after prolonged occlusion.
    for e in candidates:
        if e['verdict']!='TRUE_ISSUE' or e['error_type']!='gt_to_pred_id_switch':continue
        before=pt[e['related_track_id']][-1].frame;after=pt[e['pred_track_id']][0].frame
        selected=sorted({before,min(total,before+1),max(1,after-1),after,(after+e['start_frame'])//2,e['start_frame']})
        w,h=draw_frame(before).size;sheet=Image.new('RGB',(2*w,(h+25)*((len(selected)+1)//2)))
        for j,f in enumerate(selected):sheet.paste(draw_frame(f),((j%2)*w,(j//2)*(h+25)))
        sheet.save(vis/f"{e['event_id']}_extended.jpg",quality=95)
    if candidates:write_csv(o/'issue_candidates.csv',candidates,list(candidates[0]))
    missed=[x for x in candidates if not x['analyzer_targeted']]
    if candidates:write_csv(o/'missed_issues.csv',missed,list(candidates[0]))
    if events:write_csv(o/'raw_review_groups.csv',events,list(events[0]))
    review_events=consolidate_events(events)
    if review_events:write_csv(o/'review_events.csv',review_events,list(review_events[0]))
    flag_rows=[]
    for n,f in enumerate(flags,1):
        e=next(e for e in events if n in e['flag_ids']);p=prep[f['frame_id'],f['track_id']]
        flag_rows.append(dict(flag_id=n,**f,raw_group_id=e['event_id'],event_id=e['review_event_id'],best_gt_track_id=p['best_relevant_gt_id'],best_gt_type=p['best_relevant_gt_type'],best_iou=p['best_relevant_iou'],kitti_status=p['status'],dontcare_ioa=p['max_dontcare_ioa'],context_start=max(1,e['start_frame']-2),context_end=min(total,e['end_frame']+2),verdict=e['verdict'],evidence_note=e['evidence_note'],evidence_image=e['evidence_image']))
    write_csv(o/'flag_labels.csv',flag_rows,list(flag_rows[0]) if flag_rows else ['flag_id','event_id','verdict'])
    rule_rows=[]
    for reason in REASONS:
        rs=[r for r in flag_rows if r['reason']==reason];rule_rows.append(dict(reason=reason,flags=len(rs),**{k:sum(r['verdict']==k for r in rs) for k in ['TRUE_ISSUE','BENIGN_EVENT','FALSE_ALERT','UNCERTAIN']}))
    write_csv(o/'rule_summary.csv',rule_rows,list(rule_rows[0]))
    confirmed={}
    for r in missed:
        if r['verdict']=='TRUE_ISSUE':
            if not r['confirmed_event_id']:raise ValueError('Confirmed missed issue needs explicit deduplication ID')
            confirmed.setdefault(r['confirmed_event_id'],r)
    write_csv(o/'confirmed_missed_events.csv',list(confirmed.values()),list(candidates[0]))
    summary=dict(sequence=args.sequence,frames=total,gt_boxes=len(gt),gt_tracks=len(gt_t),pred_boxes=len(pred),pred_tracks=len(pt),flags=len(flags),raw_groups=len(events),events=len(review_events),flag_verdicts=dict(Counter(r['verdict'] for r in flag_rows)),event_verdicts=dict(Counter(r['verdict'] for r in review_events)),candidate_types=dict(Counter(r['error_type'] for r in candidates)),raw_metrics=raw['metrics'],kitti_metrics=adjusted['adjusted_project_metrics'],scope=spans(flags,total,2),flagged_frames=len({f['frame_id'] for f in flags}),confirmed_missed=list(confirmed.values()),hashes_unchanged=True)
    (o/'validation_summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
