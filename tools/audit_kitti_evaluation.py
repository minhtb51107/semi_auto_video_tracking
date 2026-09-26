"""Finalize existing KITTI evidence; no inference, downloads or metric changes."""
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from motlib import parse_mot, by_frame, by_track, iou
from validate_review_flags import matching_trace, write_csv
from kitti_tracking_to_mot import convert

ROOT=Path(__file__).resolve().parents[1]
B=ROOT/'data/external_validation/kitti_0001'
O=ROOT/'outputs/external_validation/kitti_0001'


def main():
    lock=json.loads((O/'blind_lock.json').read_text()); checks={}
    for name,h in {**lock['protected_hashes'],**lock['outputs']}.items():
        p=O/'preblind_dataset_protocol.md' if name.replace('\\','/')=='docs/EXTERNAL_DATASET.md' else ROOT/name
        checks[name]=hashlib.sha256(p.read_bytes()).hexdigest()==h
    assert all(checks.values())
    old=json.loads((ROOT/'outputs/validation/summary.json').read_text())['input_hashes']
    for name in ['tools\\review_tracks.py','configs\\review_thresholds.json']:
        assert old[name]==lock['protected_hashes'][name]
    for entry in json.loads((B/'download_manifest.json').read_text()):
        assert hashlib.sha256((B/'source'/entry['path']).read_bytes()).hexdigest()==entry['sha256']
    converted,_=convert(B/'source/data/KITTI/label_2/0001.txt',B/'source/data/KITTI/image_2/0001')
    assert converted==(B/'gt/gt.txt').read_text()
    gt=parse_mot(B/'gt/gt.txt'); pred=parse_mot(O/'tracks.txt'); gf=by_frame(gt); pt=by_track(pred)
    trace,clear=matching_trace(gt,pred)
    matched={(f,p.track_id):(g.track_id,s) for f,pairs,_,_ in trace for g,p,s in pairs}
    regions=json.loads((B/'conversion_audit.json').read_text())['records']
    def dc(p):
        vals=[]
        for r in regions:
            if r['type']=='DontCare' and r['frame_id']==p.frame:
                l,t,rr,b=r['bbox_ltrb']; vals.append(max(0,min(p.x+p.w,rr)-max(p.x,l))*max(0,min(p.y+p.h,b)-max(p.y,t))/(p.w*p.h))
        return min(1,max(vals,default=0))
    rows=[]
    for p in pred:
        best=max(((iou(g,p),g.track_id) for g in gf[p.frame]),default=(0,None))
        overlap=dc(p); match=matched.get((p.frame,p.track_id))
        category='MATCHED_TARGET' if match else ('DONTCARE_OVERLAP' if overlap>=.5 else 'AMBIGUOUS' if overlap>0 else 'REGULAR_FP')
        rows.append(dict(frame_id=p.frame,kitti_frame=p.frame-1,pred_track_id=p.track_id,
                         best_gt_track_id=best[1],best_iou=best[0],clear_gt_track_id=match[0] if match else None,
                         dontcare_intersection_over_pred_area=overlap,category=category,
                         interpretation='Audit category only; REGULAR_FP is unmatched outside DontCare, not automatically a semantic hallucination'))
    write_csv(O/'prediction_audit.csv',rows,list(rows[0]))
    candidate_path=O/'false_positive_track_candidates.csv'
    candidates=list(csv.DictReader(candidate_path.open(encoding='utf-8-sig')))
    for r in candidates:
        if int(r['pred_track_id'])==85:
            r['classification']='TRUE_ISSUE'
            r['note']='Confirmed duplicate of P77 on vehicle G93 at frames23-24; see issue_events.csv E2 and frame images. Not a hallucinated object.'
    write_csv(candidate_path,candidates,list(candidates[0]))
    identity=[r for r in rows if r['pred_track_id']==54]
    write_csv(O/'identity_P54_by_frame.csv',identity,list(rows[0]))
    flags=json.loads((O/'review/review_flags.json').read_text())['flags']
    decisions=json.loads((O/'adjudications.json').read_text()); labels=[]
    for n,f in enumerate(flags,1):
        r=next(r for r in rows if r['frame_id']==f['frame_id'] and r['pred_track_id']==f['track_id'])
        labels.append(dict(flag_id=n,event_id=f"P{f['track_id']}_{f['previous_frame_id']}_{f['frame_id']}",**f,
                           gt_track_id=r['clear_gt_track_id'],best_gt_track_id=r['best_gt_track_id'],best_iou=r['best_iou'],
                           dontcare_overlap=r['dontcare_intersection_over_pred_area'],**decisions[str(n)],
                           context_image=f"images/flag_P{f['track_id']}_{f['previous_frame_id']}_{f['frame_id']}.jpg"))
    write_csv(O/'flag_labels.csv',labels,list(labels[0]))
    # Curated events, NOT every FP/FN as a new review issue. Full atoms remain reference_issues.csv.
    events=[
      (20,31,10,None,'missed_gt_track','TRUE_ISSUE','G10/KITTI9: visible car has no matched prediction in all12 frames; images/G10_context.jpg'),
      (23,24,93,85,'duplicate_prediction','TRUE_ISSUE','P85 duplicates P77 on G93/KITTI92 in both frames; P77 gets CLEAR match. images/frames/000024.jpg'),
      (23,26,'95;96',54,'possible_identity_merge','UNCERTAIN','Best IoU G96->G95 at23, returnsG96 at25; CLEAR return26. Overlapping boxes/occlusion; reference association conflict confirmed, physical identity error not independently resolved. images/P54_identity_context.jpg'),
      (1,31,7,'5;60','fragmentation_candidate','UNCERTAIN','Best-IoU diagnostic uses P5 thenP60, but P5 matches G5 throughout and overlaps P60 lifetime17-31. Not confirmed temporal split. images/G7_context.jpg'),
      (1,1,None,7,'large_localization_error_candidate','UNCERTAIN','Partial boundary box with no target match; ambiguous target extent, not automatically hallucination. images/fp_candidates.jpg'),
      (17,30,None,64,'ghost_or_identity_reuse_candidate','UNCERTAIN','Partial boundary vehicles, frame30 strongDontCare. No confirmed ghost; already targeted by gap/reappeared. images/P64_context.jpg')]
    missed=[]
    for start,end,gid,pid,kind,status,note in events:
        flagged=pid==64
        missed.append(dict(event_id=f'E{len(missed)+1}',frame_id=start,end_frame=end,gt_track_id=gid,pred_track_id=pid,
                           error_type=kind,analyzer_flagged=flagged,validation_status=status,note=note))
    write_csv(O/'issue_events.csv',missed,list(missed[0]))
    write_csv(O/'missed_issues.csv',[r for r in missed if not r['analyzer_flagged']],list(missed[0]))
    phase=json.loads((B/'phase_b_started.json').read_text())
    assert lock['locked_utc']<phase['first_semantic_label_read_utc']
    summary=dict(locked_artifacts_unchanged=checks,threshold_matches_prior_validation=True,
                 source_download_checksums_verified=True,conversion_reproduced_in_memory=True,
                 blind_locked_utc=lock['locked_utc'],phase_b_record=phase,
                 chronology_caveat='Local process records, not independent proof of first read; PhaseB timestamp was recorded just after the first semantic read, not a filesystem access audit.',
                 prediction_categories=dict(Counter(r['category'] for r in rows)),
                 flag_labels=dict(Counter(r['label'] for r in labels)),
                 unique_flag_events=len({r['event_id'] for r in labels}),
                 confirmed_missed_events=sum(r['validation_status']=='TRUE_ISSUE' and not r['analyzer_flagged'] for r in missed),
                 uncertain_missed_events=sum(r['validation_status']=='UNCERTAIN' and not r['analyzer_flagged'] for r in missed),
                 audit_overlap_threshold=.5,overlap_policy='max single-region intersection/prediction area; descriptive audit, not official KITTI ignore preprocessing')
    (O/'final_integrity.json').write_text(json.dumps(summary,indent=2))
    print(json.dumps({k:v for k,v in summary.items() if k!='locked_artifacts_unchanged'},indent=2))


if __name__=='__main__': main()
