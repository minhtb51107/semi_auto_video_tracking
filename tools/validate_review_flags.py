"""Offline validation evidence only; does not modify analyzer, thresholds or labels.

Untruncated reference diagnostics, review scope, and annotated inspection sheets.
Human/analyst adjudications are separate JSON input; missing decisions stay UNCERTAIN.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from motlib import DEFAULT_IOU, EPS, by_frame, by_track, clear_mot, iou, maximise, parse_mot
from evaluate_tracking import diagnose
from visualize_tracks import colour, dashed_rectangle

ROOT = Path(__file__).resolve().parents[1]
REASONS = ['track_gap', 'track_reappeared', 'large_motion_jump', 'abnormal_size_change',
           'low_consecutive_iou', 'possible_fragmentation']
LABELS = ['TRUE_ISSUE', 'BENIGN_EVENT', 'FALSE_ALERT', 'UNCERTAIN']


def write_csv(path, rows, fields):
    with path.open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def matching_trace(gt, pred):
    """Expose the exact CLEAR matching of motlib for audit; assert aggregate parity."""
    gf, pf = by_frame(gt), by_frame(pred)
    previous, result = {}, []
    for frame in sorted(set(gf) | set(pf)):
        gs, ps = gf.get(frame, []), pf.get(frame, [])
        sim = [[iou(g, p) for p in ps] for g in gs]
        score = [[(1000.0 if previous.get(g.track_id) == p.track_id else 0.0) + sim[i][j]
                  if sim[i][j] >= DEFAULT_IOU - EPS else 0.0 for j, p in enumerate(ps)]
                 for i, g in enumerate(gs)]
        pairs = [(i, j) for i, j in maximise(score) if score[i][j] > EPS] if gs and ps else []
        previous = {gs[i].track_id: ps[j].track_id for i, j in pairs}
        result.append((frame, [(gs[i], ps[j], sim[i][j]) for i, j in pairs],
                       [g for i, g in enumerate(gs) if i not in {a for a, _ in pairs}],
                       [p for j, p in enumerate(ps) if j not in {b for _, b in pairs}]))
    clear = clear_mot(gt, pred)
    assert sum(len(fn) for _, _, fn, _ in result) == clear['FN']
    assert sum(len(fp) for _, _, _, fp in result) == clear['FP']
    matches = [item for _, pairs, _, _ in result for item in pairs]
    assert abs(sum(s for _, _, s in matches) / max(1, len(matches)) - clear['MOTP']) < 1e-9
    return result, clear


def spans(flags, total, padding):
    intervals = sorted((max(1, f['previous_frame_id'] - padding), min(total, f['frame_id'] + padding)) for f in flags)
    merged = []
    for start, end in intervals:
        if merged and start <= merged[-1][1] + 1:
            merged[-1][1] = max(end, merged[-1][1])
        else:
            merged.append([start, end])
    return merged


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir', type=Path, default=ROOT / 'outputs/runs/renamed_verified')
    parser.add_argument('--out-dir', type=Path, default=ROOT / 'outputs/validation')
    parser.add_argument('--adjudications', type=Path)
    args = parser.parse_args()
    out = args.out_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)
    decisions = json.loads(args.adjudications.read_text(encoding='utf-8')) if args.adjudications else {}
    flag_rows, issues, contexts, summary, hashes = [], [], [], {}, {}
    try:
        font = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 17)
        small = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 14)
    except OSError:
        font = small = ImageFont.load_default()

    for clip, total, reference in [('01', 190, 'gold/clip_01/gt.txt'), ('02', 60, 'data/clips/clip_02/gt/gt.txt')]:
        base = args.run_dir / f'clip_{clip}'
        gp, pp, fp = ROOT / reference, base / 'tracks.txt', base / 'review/review_flags.json'
        for path in (gp, pp, fp, ROOT / 'configs/review_thresholds.json', ROOT / 'tools/review_tracks.py'):
            hashes[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
        gt, pred = parse_mot(gp), parse_mot(pp)
        gf, pf, gt_t, pt = by_frame(gt), by_frame(pred), by_track(gt), by_track(pred)
        flags = json.loads(fp.read_text(encoding='utf-8'))['flags']
        trace, clear = matching_trace(gt, pred)
        old_eval = json.loads((base / 'evaluation.json').read_text(encoding='utf-8'))
        assert all(clear[k] == old_eval['metrics'][k] for k in ('FP', 'FN', 'IDSW'))
        diag = diagnose(gt, pred, clear, DEFAULT_IOU)
        owners = defaultdict(Counter)
        inverse = defaultdict(Counter)
        matched = {}
        for frame, pairs, _, _ in trace:
            for g, p, overlap in pairs:
                owners[p.track_id][g.track_id] += 1
                inverse[g.track_id][p.track_id] += 1
                matched[frame, g.track_id] = p.track_id
        scope = spans(flags, total, 2)
        scope_frames = {f for a, b in scope for f in range(a, b + 1)}
        events = {(f['track_id'], f['previous_frame_id'], f['frame_id']) for f in flags}
        summary[clip] = dict(total_frames=total, flags=len(flags), unique_events=len(events),
                             flagged_frames=len({f['frame_id'] for f in flags}), context_padding=2,
                             merged_contexts=scope, context_segments=len(scope), review_span_frames=len(scope_frames),
                             candidate_ratio=len({f['frame_id'] for f in flags}) / total,
                             review_span_ratio=len(scope_frames) / total,
                             sensitivity={str(p): {'segments': spans(flags, total, p),
                                                  'frames': sum(b-a+1 for a,b in spans(flags,total,p))} for p in (0,2,5)},
                             clear_metrics={k: clear[k] for k in ('FP','FN','IDSW','MOTP')},
                             missed_whole_tracks=diag['missed_gt_tracks'],
                             fragmented_gt_tracks=diag['fragmented_gt_tracks'], ghost_pred_tracks=diag['ghost_pred_tracks'],
                             partially_covered_gt_tracks=diag['partially_covered_gt_tracks'])
        for start, end in scope:
            contexts.append(dict(clip_id=clip, start_frame=start, end_frame=end, frames=end-start+1))

        def add_issue(frame, gid, pid, kind, note, related=None):
            relevant = {pid} if pid is not None else set(inverse.get(gid, {}))
            if related is not None:
                relevant.add(related)
            exact = any(f['frame_id'] == frame and (f['track_id'] in relevant or f['related_track_id'] in relevant) for f in flags)
            same_context = any(f['previous_frame_id']-2 <= frame <= f['frame_id']+2 and f['track_id'] in relevant for f in flags)
            status='REFERENCE_DIAGNOSTIC'
            if kind in ('id_switch','fragmentation'):
                status='TRUE_ISSUE'
            if clip=='01' and pid in (12,44) and kind=='ghost_false_positive':
                status='TRUE_ISSUE'
                note += ' Visual track-level inspection: static stall/road marker, not a vehicle; repeated FP of same object.'
            if (clip=='01' and pid==66) or (clip=='02' and pid==4) or kind=='false_continuation_candidate':
                status='UNCERTAIN'
                note += ' Tiny/clipped boundary object; reference lifetime/scope may differ. Do not equate missing reference with confirmed hallucination.'
            if kind=='missed_detection' and ((clip=='01' and ((gid==3 and 14<=frame<=16) or (gid==6 and frame==119)))
                                              or (clip=='02' and gid==5 and frame in (31,32,34))):
                status='TRUE_ISSUE'
                note += ' Visible vehicle in inspected gap sequence; reference remains present.'
            issues.append(dict(clip_id=clip, frame_id=frame, gt_track_id=gid, pred_track_id=pid,
                               error_type=kind, analyzer_flagged=exact, same_track_context=same_context,
                               any_review_context=frame in scope_frames, validation_status=status,note=note))

        for frame, pairs, missing, extra in trace:
            for g in missing:
                best = max((iou(g, p) for p in pf.get(frame, [])), default=0)
                add_issue(frame, g.track_id, None, 'missed_detection',
                          f'Unmatched reference box at CLEAR IoU>=0.5; best IoU={best:.6f}; associated pred IDs={sorted(inverse[g.track_id])}. Not a wholly missed track.')
            for p in extra:
                owner = owners[p.track_id].most_common(1)
                owner_id = owner[0][0] if owner else None
                kind = 'ghost_false_positive' if not owner else 'unmatched_prediction'
                if owner and p.frame > gt_t[owner_id][-1].frame:
                    kind = 'false_continuation_candidate'
                add_issue(frame, owner_id, p.track_id, kind,
                          'Unmatched prediction relative to supplied reference at IoU>=0.5; reference-relative diagnostic, not independent visual ground truth.')
        # Exact existing diagnose loose-box criterion, with no [:30] truncation.
        loose = []
        for frame, gs in gf.items():
            for g in gs:
                best = max(((iou(g, p), p.track_id) for p in pf.get(frame, [])), default=(0, None))
                if DEFAULT_IOU <= best[0] < .60:
                    loose.append(dict(frame=frame, gt_track=g.track_id, pred_track=best[1], iou=round(best[0], 3)))
                    add_issue(frame, g.track_id, best[1], 'loose_box', f'Existing diagnose rule 0.5<=best IoU<0.60; IoU={best[0]:.6f}.')
        assert sorted(loose, key=lambda d: d['iou'])[:30] == diag['loose_boxes']
        for switch in clear['switches']:
            add_issue(switch['frame'], switch['gt_track'], switch['to_track'], 'id_switch',
                      f"CLEAR persistent correspondence changes P{switch['from_track']} -> P{switch['to_track']}; same event as fragmentation row.", switch['from_track'])
        for frag in diag['fragmented_gt_tracks']:
            timeline = [(frame, matched[frame, frag['gt_track']]) for frame in sorted(gf) if (frame, frag['gt_track']) in matched]
            for (prev_frame, prev_id), (frame, next_id) in zip(timeline, timeline[1:]):
                if prev_id != next_id:
                    add_issue(frame, frag['gt_track'], next_id, 'fragmentation',
                              f"Reference G{frag['gt_track']} split over {frag['pred_tracks']}; last P{prev_id} at {prev_frame}; overlaps IDSW row, not a second independent error.", prev_id)

        # Existing visualization provides palette/dashed GT geometry. Add labels and context.
        def render(frame, title, highlight=None, crop=None):
            im = Image.open(base / 'img1' / f'{frame:06d}.jpg').convert('RGB')
            draw = ImageDraw.Draw(im)
            for g in gf.get(frame, []):
                dashed_rectangle(draw, g.corners, (50,255,100))
                x,y = g.x, max(24,g.y-20)
                draw.text((x,y), f'G{g.track_id}', fill=(50,255,100), stroke_width=1, stroke_fill=(0,0,0), font=font)
            for p in pf.get(frame, []):
                color = (255,65,65) if p.track_id == highlight else colour(p.track_id)
                draw.rectangle(p.corners, outline=color, width=3)
                draw.text((p.x,max(24,p.y+p.h)), f'P{p.track_id}', fill=color, stroke_width=1, stroke_fill=(0,0,0), font=font)
            draw.rectangle((0,0,im.width,23), fill=(0,0,0))
            draw.text((4,2), f'clip {clip} frame {frame} | GT dashed green G# / pred solid P#', fill='white', font=small)
            if crop:
                im=im.crop(crop)
            scale=min(600/im.width,338/im.height)
            im=im.resize((round(im.width*scale),round(im.height*scale)),Image.Resampling.LANCZOS)
            panel=Image.new('RGB',(600,390),'#101820')
            panel.paste(im,(0,42))
            d=ImageDraw.Draw(panel)
            d.text((5,3),title[:74],fill='white',font=small)
            d.text((5,21),f'frame {frame}; P{highlight}' if highlight else f'frame {frame}',fill='yellow',font=small)
            return panel

        image_dir=out/'images'/f'clip_{clip}'
        image_dir.mkdir(parents=True,exist_ok=True)
        event_files={}
        anchor_panels=[]
        for tid, a, b in sorted(events):
            selected=sorted({max(1,a-2),a,(a+b)//2,b,min(total,b+2)})
            endpoint=next(p for p in pt[tid] if p.frame==b)
            nearby=[endpoint]+[g for g in gf[b] if iou(endpoint,g)>.1]
            owner=owners[tid].most_common(1)
            if owner:
                nearby += [g for f in selected for g in gf.get(f,[]) if g.track_id==owner[0][0]]
            nearby += [p for f in selected for p in pf.get(f,[]) if p.track_id==tid]
            left=max(0,int(min(p.x for p in nearby))-65); top=max(0,int(min(p.y for p in nearby))-65)
            right=min(960,int(max(p.x+p.w for p in nearby))+65); bottom=min(540,int(max(p.y+p.h for p in nearby))+65)
            sheet=Image.new('RGB',(600*len(selected),780),'#101820')
            reasons='+'.join(sorted({f['reason'] for f in flags if (f['track_id'],f['previous_frame_id'],f['frame_id'])==(tid,a,b)}))
            for j,f in enumerate(selected):
                sheet.paste(render(f,f'{reasons}: P{tid} {a}->{b}',tid),(600*j,0))
                sheet.paste(render(f,'ROI: predicted track and matched reference',tid,(left,top,right,bottom)),(600*j,390))
            path=image_dir/f'flag_P{tid}_{a}_{b}.jpg'; sheet.save(path,quality=90)
            event_files[tid,a,b]=str(path.relative_to(out))
            raw=Image.open(base/'img1'/f'{b:06d}.jpg').convert('RGB').crop((left,top,right,bottom))
            scale=min(280/raw.width,250/raw.height)
            raw=raw.resize((round(raw.width*scale),round(raw.height*scale)),Image.Resampling.LANCZOS)
            anchor=Image.new('RGB',(600,340),'#101820')
            anchor.paste(raw,(0,65))
            annotated=render(b,'',tid,(left,top,right,bottom)).resize((300,195))
            anchor.paste(annotated,(300,65))
            ad=ImageDraw.Draw(anchor); ad.text((5,5),f'clip {clip} P{tid} {a}->{b}',font=font,fill='white')
            ad.text((5,30),reasons,font=small,fill='yellow')
            anchor_panels.append(anchor)
        atlas=Image.new('RGB',(1800,340*((len(anchor_panels)+2)//3)),'#101820')
        for j,panel in enumerate(anchor_panels): atlas.paste(panel,(600*(j%3),340*(j//3)))
        atlas.save(image_dir/'flag_anchor_atlas.jpg',quality=95)
        # Full per-frame context, not only sparse thumbnails.
        frames_dir=image_dir/'context_frames'; frames_dir.mkdir(exist_ok=True)
        for frame in sorted(scope_frames | {1,2,79,89,90,91,92,93,94,95,96,136,140,169,170} & set(range(1,total+1))):
            frame_reasons=';'.join(sorted({f['reason'] for f in flags if f['previous_frame_id']-2<=frame<=f['frame_id']+2}))
            render(frame,frame_reasons or 'reference issue audit').save(frames_dir/f'{frame:06d}.jpg',quality=90)
        if clip=='01':
            for name, selected, tid in [('id_switch_G5_P28_P33',[89,90,91,92,93,94,95,96],33),
                                        ('unflagged_ghost_P66',[167,168,169,170,171],66),
                                        ('missing_entry_G5',[78,79,83,88,89],28),
                                        ('loose_or_unmatched_G8',[136,139,140,145,152],56)]:
                sheet=Image.new('RGB',(600*min(4,len(selected)),390*((len(selected)+3)//4)),'#101820')
                for j,f in enumerate(selected): sheet.paste(render(f,name,tid),(600*(j%4),390*(j//4)))
                sheet.save(image_dir/f'{name}.jpg',quality=92)
        else:
            sheet=Image.new('RGB',(1800,390),'#101820')
            for j,f in enumerate((1,2,3)): sheet.paste(render(f,'unflagged ghost P4',4),(600*j,0))
            sheet.save(image_dir/'unflagged_ghost_P4.jpg',quality=92)
            sheet=Image.new('RGB',(3000,390),'#101820')
            for j,f in enumerate((55,56,57,58,59)):
                sheet.paste(render(f,'uncertain reference end: G4 ends 56; P7 ends 58',7),(600*j,0))
            sheet.save(image_dir/'uncertain_continuation_P7.jpg',quality=92)

        for index, f in enumerate(flags,1):
            flag_id=f'{clip}-{index:02d}'
            tid,a,b=f['track_id'],f['previous_frame_id'],f['frame_id']
            decision=decisions.get(flag_id,{'label':'UNCERTAIN','note':'Awaiting visual/reference adjudication'})
            assert decision['label'] in LABELS
            current=next(p for p in pt[tid] if p.frame==b)
            best=max(((iou(current,g),g.track_id) for g in gf.get(b,[])),default=(0,None))
            owner=owners[tid].most_common(1)
            missing_ref=[frame for frame in range(a+1,b) if owner and any(g.track_id==owner[0][0] for g in gf.get(frame,[]))]
            missing_unmatched=[frame for frame in missing_ref if (frame,owner[0][0]) not in matched]
            flag_rows.append(dict(flag_id=flag_id,clip_id=clip,**f,label=decision['label'],
                                  gt_track_id=owner[0][0] if owner else None,
                                  anchor_best_reference_iou=round(best[0],6),
                                  matched_gt_ids=json.dumps(dict(owners[tid])),
                                  absent_pred_reference_present_frames=json.dumps(missing_ref),
                                  unmatched_reference_frames=json.dumps(missing_unmatched),
                                  note=decision['note'],visualization=event_files[tid,a,b]))

    assert len(flag_rows)==29
    assert set(decisions)<= {f['flag_id'] for f in flag_rows}
    issue_fields=['clip_id','frame_id','gt_track_id','pred_track_id','error_type','analyzer_flagged','same_track_context','any_review_context','validation_status','note']
    write_csv(out/'flag_labels.csv',flag_rows,list(flag_rows[0]))
    write_csv(out/'reference_issues.csv',issues,issue_fields)
    write_csv(out/'missed_issues.csv',[i for i in issues if not i['analyzer_flagged']],issue_fields)
    write_csv(out/'review_contexts.csv',contexts,list(contexts[0]))
    rules=[]
    for reason in REASONS:
        items=[f for f in flag_rows if f['reason']==reason]; counts=Counter(f['label'] for f in items)
        resolved=len(items)-counts['UNCERTAIN']
        rules.append(dict(reason=reason,flags=len(items),**{k:counts[k] for k in LABELS},
                          preliminary_precision=counts['TRUE_ISSUE']/resolved if resolved else None))
    write_csv(out/'rule_summary.csv',rules,list(rules[0]))
    report={'scope':summary,'rules':rules,'reference_issue_atoms':dict(Counter(i['error_type'] for i in issues)),
            'missed_exact_atoms':dict(Counter(i['error_type'] for i in issues if not i['analyzer_flagged'])),
            'not_in_same_track_context':dict(Counter(i['error_type'] for i in issues if not i['same_track_context'])),
            'not_in_any_context':dict(Counter(i['error_type'] for i in issues if not i['any_review_context'])),
            'input_hashes':hashes,'matching':'CLEAR audit trace matches FP/FN/MOTP; loose boxes match untruncated diagnose criterion',
            'issue_unit':'frame-box diagnostic atoms, overlapping types, NOT independent errors or standard recall',
            'context_policy':'Union of [previous_frame_id-2, frame_id+2], inclusive/clipped; report also 0/5-frame sensitivity'}
    (out/'summary.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    assert all(hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==value for path,value in hashes.items())
    print(json.dumps({k:v for k,v in report.items() if k!='input_hashes'},indent=2))


if __name__=='__main__':
    main()
