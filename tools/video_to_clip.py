"""Decode a local video to a NEW MOT image-sequence directory for run_tracker.py."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path


def video_to_clip(video: Path, out: Path):
    import cv2

    video, out = Path(video), Path(out)
    if not video.is_file():
        raise ValueError(f'Video not found: {video}')
    if out.exists():
        raise ValueError(f'Output already exists; choose a new directory: {out}')
    capture = cv2.VideoCapture(str(video))
    try:
        if not capture.isOpened():
            raise ValueError(f'Cannot open video: {video}')
        fps = capture.get(cv2.CAP_PROP_FPS)
        declared = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        if not math.isfinite(fps) or fps <= 0:
            raise ValueError('Video FPS is missing or invalid')
        index = 0
        width = height = 0
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            if index == 0:
                height, width = frame.shape[:2]
                (out / 'img1').mkdir(parents=True, exist_ok=False)
            elif frame.shape[:2] != (height, width):
                raise ValueError('Video resolution changed during decoding')
            index += 1
            if not cv2.imwrite(str(out / 'img1' / f'{index:06d}.jpg'), frame,
                               [cv2.IMWRITE_JPEG_QUALITY, 95]):
                raise ValueError(f'Cannot write frame {index}')
        if not index or (declared > 0 and declared != index):
            raise ValueError(f'Incomplete decode: decoded {index}, declared {declared}; do not run tracker')
    finally:
        capture.release()
    (out / 'seqinfo.ini').write_text(
        f'[Sequence]\nname={out.name}\nimDir=img1\nframeRate={fps:g}\nseqLength={index}\n'
        f'imWidth={width}\nimHeight={height}\nimExt=.jpg\n', encoding='utf-8')
    metadata = dict(source=str(video.resolve()), source_sha256=hashlib.sha256(video.read_bytes()).hexdigest(),
                    decoded_frames=index, fps=fps, width=width, height=height, frame_index_base=1,
                    opencv=cv2.__version__, jpeg_quality=95,
                    note='Decode order, no sampling. JPEG re-encoding; not pixel-identical to original lab JPEGs.')
    (out / 'source.json').write_text(json.dumps(metadata, indent=2) + '\n', encoding='utf-8')
    return metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--video', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(video_to_clip(args.video, args.out)))
    except (OSError, ValueError) as exc:
        parser.exit(2, f'ERROR: {exc}\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
