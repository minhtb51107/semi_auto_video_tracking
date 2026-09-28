#!/usr/bin/env python3
"""Chạy detector + tracker trên một clip và xuất kết quả ra đúng định dạng MOT 1.1.

    # Control: motion + IoU association
    python3 tools/run_tracker.py --clip data/clips/clip_01 \
        --model yolo26n.pt --tracker bytetrack.yaml \
        --out outputs/model_bytetrack_clip_01.txt

Đây chính là "tracking-by-detection" trong slide: YOLO tìm bbox trên từng frame,
tracker nối các bbox đó qua thời gian. ByteTrack dùng Kalman + IoU. File xuất ra đọc được bằng
cùng `tools/evaluate_tracking.py` đã dùng để chấm nhãn tay, nên có thể so sánh
control, treatment và gold mà không đổi định dạng.

Cần `pip install ultralytics`. Chạy được trên CPU, nhưng Colab có GPU sẽ nhanh hơn.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from tracking_runtime import (ByteTrackTracker, TrackBox,
                              UltralyticsYOLODetector)

# COCO không có lớp "van"; van bị model xếp vào car hoặc truck.
# Gold của lab chỉ gán xe bốn bánh, nên KHÔNG lấy motorcycle/bicycle/person.
COCO_VEHICLES = {2: "car", 5: "bus", 7: "truck"}


def track_clip(clip: Path, model_name: str, tracker: str, conf: float, iou: float,
               imgsz: int, classes: list[int], device: str | None = None,
               verbose: bool = True) -> list[tuple[int, int, float, float, float, float, float]]:
    """Trả về list (frame, track_id, x, y, w, h, conf) với frame đánh số từ 1."""
    return track_image_dir(clip / "img1", model_name, tracker, conf, iou, imgsz,
                           classes, device, verbose)


def track_image_dir(image_dir: Path, model_name: str, tracker: str, conf: float,
                    iou: float, imgsz: int, classes: list[int],
                    device: str | None = None, verbose: bool = True
                    ) -> list[tuple[int, int, float, float, float, float, float]]:
    """Backward-compatible 7-column rows over the normalized runtime."""
    return [row.legacy() for row in track_image_dir_normalized(
        image_dir, model_name, tracker, conf, iou, imgsz, classes, device, verbose
    )]


def track_image_dir_normalized(image_dir: Path, model_name: str, tracker: str, conf: float,
                               iou: float, imgsz: int, classes: list[int],
                               device: str | None = None, verbose: bool = True) -> list[TrackBox]:
    images = sorted(Path(image_dir).glob("*.jpg"))
    if not images:
        raise SystemExit(f"Không thấy ảnh trong {image_dir}")
    detector = UltralyticsYOLODetector(model_name, classes, conf, iou, imgsz, device)
    tracker_impl = ByteTrackTracker(tracker)
    rows: list[TrackBox] = []
    for index, image_path in enumerate(images, start=1):
        rows.extend(tracker_impl.update(detector.detect(image_path, index), index))
        if verbose and index % 25 == 0:
            print(f"  frame {index}/{len(images)} · {len(rows)} bbox tích luỹ")

    return rows


def write_mot(rows, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            (f"{row.frame_id},{row.track_id},{row.bbox[0]:.2f},{row.bbox[1]:.2f},"
             f"{row.bbox[2]:.2f},{row.bbox[3]:.2f},{row.confidence:.4f},{row.class_id},-1,-1"
             if isinstance(row, TrackBox) else
             f"{row[0]},{row[1]},{row[2]:.2f},{row[3]:.2f},{row[4]:.2f},{row[5]:.2f},{row[6]:.4f},-1,-1,-1")
            for row in sorted(rows, key=lambda value: (value[0], value[1]))
        ) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--clip", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--model", default="yolo26n.pt")
    parser.add_argument(
        "--tracker", default="bytetrack.yaml",
        help="ByteTrack YAML (tracker_type=bytetrack)",
    )
    parser.add_argument("--conf", type=float, default=0.25, help="ngưỡng confidence của detector")
    parser.add_argument("--iou", type=float, default=0.7, help="ngưỡng NMS")
    parser.add_argument("--imgsz", type=int, default=960)
    parser.add_argument("--device", default=None, help="ví dụ 0 cho GPU, cpu cho CPU")
    parser.add_argument("--classes", default="2,5,7",
                        help=f"class id COCO, mặc định xe bốn bánh {COCO_VEHICLES}")
    args = parser.parse_args()

    classes = [int(c) for c in args.classes.split(",") if c.strip()]
    print(f"Model {args.model} · tracker {args.tracker} · conf {args.conf} · imgsz {args.imgsz}")
    print(f"Lớp COCO dùng: {[COCO_VEHICLES.get(c, c) for c in classes]}")

    rows = track_clip(args.clip, args.model, args.tracker, args.conf, args.iou,
                      args.imgsz, classes, args.device)
    write_mot(rows, args.out)
    tracks = {r[1] for r in rows}
    print(f"Đã ghi {args.out}: {len(rows)} bbox · {len(tracks)} track")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
