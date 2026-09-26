#!/usr/bin/env python3
"""KITTI-aware preprocessing plus project metrics; not an official KITTI score."""
from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from motlib import (DEFAULT_IOU, EPS, Det, by_frame, clear_mot, hota, identity,
                    iou, maximise, parse_mot)


@dataclass(frozen=True)
class KittiGT:
    frame: int
    track_id: int
    kind: str
    truncated: int
    occluded: int
    box: Det
    source_line: int


def parse_kitti_tracking(path: Path) -> list[KittiGT]:
    rows = []
    for number, raw in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
        if not raw.strip():
            continue
        parts = raw.split()
        if len(parts) != 17:
            raise ValueError(f'{path}:{number}: expected 17 KITTI GT fields, got {len(parts)}')
        try:
            source_frame, source_id = int(parts[0]), int(parts[1])
            truncated, occluded = int(parts[3]), int(parts[4])
            values = [float(value) for value in parts[5:]]
        except ValueError as exc:
            raise ValueError(f'{path}:{number}: invalid numeric value ({exc})') from exc
        if source_frame < 0 or not all(map(math.isfinite, values)):
            raise ValueError(f'{path}:{number}: invalid frame or non-finite value')
        left, top, right, bottom = values[1:5]
        if right <= left or bottom <= top:
            raise ValueError(f'{path}:{number}: invalid LTRB box')
        kind = parts[2]
        track_id = source_id + 1 if source_id >= 0 else source_id
        rows.append(KittiGT(source_frame + 1, track_id, kind, truncated, occluded,
                            Det(source_frame + 1, track_id, left, top,
                                right - left, bottom - top), number))
    return rows


def intersection_over_prediction(pred: Det, region: Det) -> float:
    px1, py1, px2, py2 = pred.corners
    rx1, ry1, rx2, ry2 = region.corners
    area = max(0.0, min(px2, rx2) - max(px1, rx1)) * max(0.0, min(py2, ry2) - max(py1, ry1))
    return area / (pred.w * pred.h) if pred.w > 0 and pred.h > 0 else 0.0


def preprocess_car(rows: list[KittiGT], predictions: list[Det], *, threshold: float = 0.5,
                   min_height: float = 25.0, dontcare_ioa: float = 0.5):
    """Mirror TrackEval KITTI Car preprocessing; all predictions are assumed class Car."""
    gt_frames, pred_frames = {}, by_frame(predictions)
    for row in rows:
        gt_frames.setdefault(row.frame, []).append(row)
    kept_gt, kept_pred, pred_audit, gt_audit = [], [], [], []
    frames = sorted(set(gt_frames) | set(pred_frames))

    for frame in frames:
        source = gt_frames.get(frame, [])
        relevant = [row for row in source if row.kind in ('Car', 'Van')]
        dontcare = [row.box for row in source if row.kind == 'DontCare']
        preds = pred_frames.get(frame, [])
        scores = [[iou(row.box, pred) if iou(row.box, pred) >= threshold - EPS else 0.0
                   for pred in preds] for row in relevant]
        pairs = [(i, j) for i, j in maximise(scores) if scores[i][j] > EPS] if relevant and preds else []
        matched_pred = {j: i for i, j in pairs}

        for row in source:
            if row.kind == 'Car' and row.occluded <= 2 and row.truncated <= 0:
                status = 'TARGET_CAR'
                kept_gt.append(row.box)
            elif row.kind == 'Van':
                status = 'DISTRACTOR_VAN'
            elif row.kind == 'Car':
                status = 'IGNORED_CAR_TRUNCATED_OR_OCCLUDED'
            elif row.kind == 'DontCare':
                status = 'DONTCARE_REGION'
            else:
                status = 'EXCLUDED_CLASS'
            gt_audit.append(dict(frame_id=frame, kitti_frame=frame - 1,
                                 kitti_track_id=row.track_id - 1 if row.track_id >= 0 else row.track_id,
                                 mot_track_id=row.track_id if row.track_id >= 0 else '',
                                 type=row.kind, truncated=row.truncated, occluded=row.occluded,
                                 height=row.box.h, status=status, source_line=row.source_line))

        for index, pred in enumerate(preds):
            match_index = matched_pred.get(index)
            matched = relevant[match_index] if match_index is not None else None
            best_index = max(range(len(relevant)), key=lambda i: iou(relevant[i].box, pred)) if relevant else None
            best = relevant[best_index] if best_index is not None else None
            best_iou = iou(best.box, pred) if best is not None else 0.0
            max_ioa = max((intersection_over_prediction(pred, region) for region in dontcare), default=0.0)
            too_small = pred.h <= min_height + EPS
            in_dontcare = max_ioa > dontcare_ioa + EPS
            reasons = []
            if matched is not None:
                if matched.kind == 'Van':
                    reasons.append('MATCHED_VAN_DISTRACTOR')
                elif matched.occluded > 2 or matched.truncated > 0:
                    reasons.append('MATCHED_IGNORED_CAR')
            else:
                if too_small:
                    reasons.append('UNMATCHED_HEIGHT_LE_25')
                if in_dontcare:
                    reasons.append('UNMATCHED_DONTCARE_IOA_GT_0_5')
            status = 'IGNORED_' + '+'.join(reasons) if reasons else 'KEPT'
            if not reasons:
                kept_pred.append(pred)
            pred_audit.append(dict(
                frame_id=frame, kitti_frame=frame - 1, pred_track_id=pred.track_id,
                x=pred.x, y=pred.y, w=pred.w, h=pred.h,
                preprocessing_match_gt_id=matched.track_id if matched is not None else '',
                preprocessing_match_type=matched.kind if matched is not None else '',
                preprocessing_match_iou=scores[match_index][index] if matched is not None else 0.0,
                best_relevant_gt_id=best.track_id if best is not None else '',
                best_relevant_gt_type=best.kind if best is not None else '',
                best_relevant_iou=best_iou,
                max_dontcare_ioa=max_ioa, too_small_unmatched=too_small if matched is None else False,
                status=status))
    return kept_gt, kept_pred, gt_audit, pred_audit


def clear_trace(gt: list[Det], pred: list[Det]):
    gt_frames, pred_frames = by_frame(gt), by_frame(pred)
    previous, previous_frame, output = {}, {}, []
    for frame in sorted(set(gt_frames) | set(pred_frames)):
        gs, ps = gt_frames.get(frame, []), pred_frames.get(frame, [])
        sim = [[iou(g, p) for p in ps] for g in gs]
        score = [[(1000.0 if previous_frame.get(g.track_id) == p.track_id else 0.0) + sim[i][j]
                  if sim[i][j] >= DEFAULT_IOU - EPS else 0.0
                  for j, p in enumerate(ps)] for i, g in enumerate(gs)]
        pairs = [(i, j) for i, j in maximise(score) if score[i][j] > EPS] if gs and ps else []
        current = {}
        for i, j in pairs:
            g, p = gs[i], ps[j]
            output.append(dict(frame_id=frame, kitti_frame=frame - 1, gt_track_id=g.track_id,
                               pred_track_id=p.track_id, iou=sim[i][j],
                               previous_pred_track_id=previous.get(g.track_id, ''),
                               id_switch=previous.get(g.track_id) not in (None, p.track_id)))
            previous[g.track_id] = p.track_id
            current[g.track_id] = p.track_id
        previous_frame = current
    return output


def metrics(gt: list[Det], pred: list[Det]) -> dict:
    clear = clear_mot(gt, pred)
    return {**hota(gt, pred), **identity(gt, pred),
            **{key: value for key, value in clear.items()
               if key not in ('switches', 'matched_per_gt_track')}}


def write_csv(path: Path, rows: list[dict], fields=None):
    fields = fields or list(rows[0])
    with path.open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--labels', required=True, type=Path)
    parser.add_argument('--pred', required=True, type=Path)
    parser.add_argument('--raw-evaluation', required=True, type=Path)
    parser.add_argument('--out-dir', required=True, type=Path)
    args = parser.parse_args()
    rows = parse_kitti_tracking(args.labels)
    predictions = parse_mot(args.pred)
    gt, pred, gt_audit, pred_audit = preprocess_car(rows, predictions)
    adjusted = metrics(gt, pred)
    _, pred_no_dc, _, _ = preprocess_car(rows, predictions, dontcare_ioa=1.0)
    _, pred_no_small, _, _ = preprocess_car(rows, predictions, min_height=-1.0)
    _, pred_no_unmatched_ignore, _, _ = preprocess_car(
        rows, predictions, min_height=-1.0, dontcare_ioa=1.0)
    trace = clear_trace(gt, pred)
    raw = json.loads(args.raw_evaluation.read_text(encoding='utf-8'))
    args.out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(args.out_dir / 'gt_preprocessing_audit.csv', gt_audit)
    write_csv(args.out_dir / 'prediction_preprocessing_audit.csv', pred_audit)
    write_csv(args.out_dir / 'adjusted_clear_matches.csv', trace,
              ['frame_id', 'kitti_frame', 'gt_track_id', 'pred_track_id', 'iou',
               'previous_pred_track_id', 'id_switch'])
    result = dict(
        interpretation='KITTI-aware adjusted audit; not an official KITTI score',
        prediction_class_assumption='All classless MOT predictions are treated as KITTI Car',
        semantics=dict(target='Car', distractor='Van', excluded=['Truck', 'Pedestrian', 'Person_sitting',
                       'Cyclist', 'Tram', 'Misc'], max_occlusion=2, max_truncation=0,
                       unmatched_min_height_inclusive=25, unmatched_dontcare_ioa_strictly_greater_than=0.5,
                       matching='Hungarian IoU>=0.5 during preprocessing; project metrics re-match after filtering'),
        inputs=dict(labels=str(args.labels), labels_sha256=hashlib.sha256(args.labels.read_bytes()).hexdigest(),
                    prediction=str(args.pred), prediction_sha256=hashlib.sha256(args.pred.read_bytes()).hexdigest(),
                    raw_evaluation=str(args.raw_evaluation),
                    raw_evaluation_sha256=hashlib.sha256(args.raw_evaluation.read_bytes()).hexdigest()),
        raw_project_metrics=raw['metrics'], adjusted_project_metrics=adjusted,
        sensitivity=dict(
            without_dontcare_ignore=metrics(gt, pred_no_dc),
            without_small_box_ignore=metrics(gt, pred_no_small),
            without_either_unmatched_ignore=metrics(gt, pred_no_unmatched_ignore)),
        counts=dict(raw_gt_boxes=raw['metrics']['GT_boxes'], raw_pred_boxes=raw['metrics']['PRED_boxes'],
                    adjusted_gt_boxes=len(gt), adjusted_gt_tracks=len({d.track_id for d in gt}),
                    adjusted_pred_boxes=len(pred), adjusted_pred_tracks=len({d.track_id for d in pred}),
                    removed_predictions=len(predictions)-len(pred),
                    prediction_statuses={status: sum(r['status'] == status for r in pred_audit)
                                         for status in sorted({r['status'] for r in pred_audit})},
                    gt_statuses={status: sum(r['status'] == status for r in gt_audit)
                                 for status in sorted({r['status'] for r in gt_audit})}),
        association=dict(clear_matches=len(trace), id_switches=[r for r in trace if r['id_switch']],
                         predicted_ids_matching_multiple_gt={str(pid): sorted({r['gt_track_id'] for r in trace
                         if r['pred_track_id'] == pid}) for pid in sorted({r['pred_track_id'] for r in trace})
                         if len({r['gt_track_id'] for r in trace if r['pred_track_id'] == pid}) > 1}))
    (args.out_dir / 'evaluation.json').write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n',
                                                  encoding='utf-8')
    print(json.dumps(dict(raw=result['raw_project_metrics'], adjusted=result['adjusted_project_metrics'],
                          counts=result['counts'], association=result['association']), indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
