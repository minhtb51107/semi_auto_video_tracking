import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from fetch_kitti_sequence import RemoteZip,selected
from run_external_blind import prepare
from validate_external_sequence import group_flags
import cv2
import numpy as np


class AcquisitionTests(unittest.TestCase):
    def test_gap_and_reappearance_share_event_but_not_different_intervals(self):
        flags=[dict(track_id=4,previous_frame_id=1,frame_id=8,related_track_id=None,reason='track_gap'),
               dict(track_id=4,previous_frame_id=1,frame_id=8,related_track_id=None,reason='track_reappeared'),
               dict(track_id=4,previous_frame_id=10,frame_id=13,related_track_id=None,reason='track_gap')]
        result=group_flags(flags)
        self.assertEqual(len(result),2)
        self.assertEqual(result[0]['flag_ids'],[1,2])
        self.assertEqual(result[0]['reasons'],['track_gap','track_reappeared'])
        self.assertEqual(group_flags([]),[])

    def test_select_only_requested_training_sequence(self):
        names=['training/image_02/0000/000000.png','testing/image_02/0000/000000.png','training/image_02/0001/000000.png','training/label_02/0000.txt']
        infos=[zipfile.ZipInfo(n) for n in names]
        self.assertEqual([i.filename for i in selected(infos,'0000')],[names[0]])
        self.assertEqual([i.filename for i in selected(infos,'0000',True)],[names[-1]])

    def test_range_refuses_whole_archive_and_large_read(self):
        obj=RemoteZip.__new__(RemoteZip);obj.url='https://example.invalid/x';obj.size=100000000;obj.position=0;obj.etag='x';obj.transferred=0
        with self.assertRaises(ValueError):obj.read()
        class Response(io.BytesIO):
            status=200
        with patch('urllib.request.urlopen',return_value=Response(b'bad')):
            with self.assertRaises(ValueError):obj.read(10)

    def test_preparation_base_size_and_missing_frame(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);images=root/'images';images.mkdir()
            cv2.imwrite(str(images/'000000.png'),np.zeros((30,50,3),dtype=np.uint8))
            rows=prepare(images,root/'clip')
            self.assertEqual((rows[0]['kitti_frame'],rows[0]['mot_frame'],rows[0]['width']),(0,1,50))
            with self.assertRaises(ValueError):prepare(images,root/'clip')
            cv2.imwrite(str(images/'000002.png'),np.zeros((30,50,3),dtype=np.uint8))
            with self.assertRaises(ValueError):prepare(images,root/'other')


if __name__=='__main__':unittest.main()
