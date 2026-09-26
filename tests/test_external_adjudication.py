import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from validate_external_sequence import consolidate_events,verify_lock


class AdjudicationTests(unittest.TestCase):
    def event(self,identifier,group,track,flags,verdict='TRUE_ISSUE'):
        return dict(event_id=identifier,review_event_id=group,track_id=track,start_frame=10,end_frame=15,reasons=['track_gap'],flag_ids=flags,verdict=verdict,evidence_image='x.jpg',evidence_note='visible',gt_association='G1',dontcare_status='none')

    def test_explicit_handoff_merges_without_losing_raw_flags(self):
        rows=[self.event('R1','R1',10,[1,2]),self.event('R2','R1',20,[3]),self.event('R3','R3',30,[4])]
        result=consolidate_events(rows)
        self.assertEqual(len(result),2)
        self.assertEqual(result[0]['flag_ids'],[1,2,3])
        self.assertEqual(result[0]['track_ids'],[10,20])
        self.assertEqual(len(rows),3)

    def test_contradictory_verdict_cannot_be_silently_merged(self):
        with self.assertRaises(ValueError):consolidate_events([self.event('R1','R1',1,[1]),self.event('R2','R1',2,[2],'UNCERTAIN')])

    def test_lock_detects_source_tampering_even_if_manifest_unchanged(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);base=root/'data';out=root/'out';(base/'source').mkdir(parents=True);(base/'clip/img1').mkdir(parents=True);out.mkdir()
            sha=lambda b:hashlib.sha256(b).hexdigest()
            (base/'source/a.png').write_bytes(b'png');(base/'clip/img1/a.jpg').write_bytes(b'jpeg')
            (base/'images_download.json').write_text(json.dumps({'files':[dict(path='a.png',sha256=sha(b'png'))]}))
            (base/'frame_manifest.json').write_text(json.dumps([dict(jpeg='a.jpg',jpeg_sha256=sha(b'jpeg'))]))
            (out/'preblind_dataset_protocol.md').write_bytes(b'protocol')
            lock=dict(protected_hashes={},outputs={},round1_hashes={},source_manifest_sha256=sha((base/'images_download.json').read_bytes()),frame_manifest_sha256=sha((base/'frame_manifest.json').read_bytes()),protocol_sha256=sha(b'protocol'))
            (out/'blind_lock.json').write_text(json.dumps(lock))
            self.assertTrue(verify_lock(root,base,out)['all_pass'])
            (base/'source/a.png').write_bytes(b'tampered')
            with self.assertRaises(ValueError):verify_lock(root,base,out)


if __name__=='__main__':unittest.main()
