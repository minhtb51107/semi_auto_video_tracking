import json
from pathlib import Path
import sys
import tempfile
import unittest

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from video_to_clip import video_to_clip


class VideoTests(unittest.TestCase):
    def test_decode_order_metadata_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            video = root / 'sample.avi'
            writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*'MJPG'), 10, (64, 48))
            self.assertTrue(writer.isOpened())
            for value in (20, 90, 180):
                writer.write(np.full((48, 64, 3), value, dtype=np.uint8))
            writer.release()
            target = root / 'clip'
            result = video_to_clip(video, target)
            self.assertEqual((result['decoded_frames'], result['width'], result['height']), (3, 64, 48))
            images = sorted((target / 'img1').glob('*.jpg'))
            self.assertEqual([p.name for p in images], ['000001.jpg', '000002.jpg', '000003.jpg'])
            self.assertTrue(all(abs(cv2.imread(str(p)).mean() - v) < 3 for p, v in zip(images, (20, 90, 180))))
            self.assertIn('seqLength=3', (target / 'seqinfo.ini').read_text())
            self.assertEqual(json.loads((target / 'source.json').read_text())['frame_index_base'], 1)
            with self.assertRaises(ValueError):
                video_to_clip(video, target)

    def test_missing_and_invalid_video(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with self.assertRaises(ValueError):
                video_to_clip(root / 'missing.mp4', root / 'out')
            bad = root / 'bad.mp4'
            bad.write_bytes(b'not a video')
            with self.assertRaises(ValueError):
                video_to_clip(bad, root / 'out')
            self.assertFalse((root / 'out/seqinfo.ini').exists())


if __name__ == '__main__':
    unittest.main()
