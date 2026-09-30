import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from motlib import Det
from review_tracks import load_config,review_file,DEFAULT_CONFIG
from review_tracks_v2 import DEFAULT_V2,analyze_v2,duplicate_flags,review_v2,validate_config


class V2Tests(unittest.TestCase):
    def setUp(self):self.c=json.loads(DEFAULT_V2.read_text());self.v1=load_config()
    def pair(self,frames=range(1,5),offset=1):
        return [d for f in frames for d in [Det(f,1,f,0,100,60),Det(f,2,f+offset,0,100,60)]]
    def test_persistent_duplicate_one_flag_and_observations(self):
        fs=duplicate_flags(self.pair(),self.c);self.assertEqual(len(fs),1)
        self.assertEqual((fs[0]['start_frame'],fs[0]['end_frame'],fs[0]['frame_id']),(1,4,2))
        self.assertEqual(fs[0]['related_track_id'],2);self.assertEqual(fs[0]['observed_value']['consecutive_frames'],4)
    def test_nearby_distinct_and_crossing_and_short_overlap(self):
        self.assertEqual(duplicate_flags(self.pair(offset=45),self.c),[])
        crossing=[d for f,x in enumerate([60,30,0,-30,-60],1) for d in [Det(f,1,0,0,100,60),Det(f,2,x,0,100,60)]]
        self.assertEqual(duplicate_flags(crossing,self.c),[])
        self.assertEqual(duplicate_flags(self.pair([3],0),self.c),[])
    def test_temporal_hole_resets_and_entry_exit(self):
        self.assertEqual(duplicate_flags(self.pair([1,3]),self.c),[])
        rows=[Det(f,1,0,0,100,60) for f in range(1,8)]+[Det(f,2,1,0,100,60) for f in [3,4]]
        fs=duplicate_flags(rows,self.c);self.assertEqual((fs[0]['start_frame'],fs[0]['end_frame']),(3,4))
    def test_multiple_runs_and_permutation(self):
        rows=self.pair([1,2,5,6]);self.assertEqual(len(duplicate_flags(rows,self.c)),2)
        self.assertEqual(analyze_v2(rows,self.v1,self.c),analyze_v2(rows[::-1],self.v1,self.c))
    def test_gap_reappearance_lossless_grouping_and_bounds(self):
        rows=[Det(f,t,t*200,0,30,30) for t in [1,2] for f in [1,8]]
        r=analyze_v2(rows,self.v1,self.c,8)
        self.assertEqual(len(r['flags']),4);self.assertEqual(len(r['events']),2)
        self.assertEqual(sorted(x for e in r['events'] for x in e['raw_flag_ids']),sorted(f['raw_flag_id'] for f in r['flags']))
        self.assertTrue(all(e['context_start']==1 and e['context_end']==8 for e in r['events']))
    def test_config_guards_and_empty(self):
        for key,value in [('duplicate_min_consecutive_frames',1),('duplicate_min_iou',float('nan')),('context_padding',True),('duplicate_max_size_ratio',0)]:
            c=dict(self.c);c[key]=value
            with self.assertRaises(ValueError):validate_config(c)
        self.assertEqual(analyze_v2([],self.v1,self.c)['events'],[])
        with self.assertRaises(ValueError):analyze_v2(self.pair(),self.v1,self.c,2)
    def test_exact_boundary_and_size_mismatch(self):
        c=dict(self.c,duplicate_min_iou=1,duplicate_max_center_distance=0,duplicate_max_size_ratio=1)
        self.assertEqual(len(duplicate_flags(self.pair(offset=0),c)),1)
        rows=[d for f in [1,2,3] for d in [Det(f,1,0,0,100,60),Det(f,2,0,0,200,60)]]
        self.assertEqual(duplicate_flags(rows,self.c),[])
    def test_task44_bus_cross_subclass_duplicate_uses_canonical_vehicle(self):
        # Locked task44 observations: CVAT frames 13-14 (MOT 14-15), the
        # same bus was represented by external tracks 3 and 11. Detector
        # subclasses were bus=5 and truck=7, both mapped to CVAT vehicle.
        rows=[
            Det(14,3,430.30,150.39,371.62,278.23,.6547,5),
            Det(14,11,450.80,129.46,331.14,291.19,.6171,7),
            Det(15,3,405.22,138.05,374.24,280.21,.7720,5),
            Det(15,11,424.59,124.41,333.94,292.93,.5710,7),
        ]
        self.assertEqual(duplicate_flags(rows,self.c),[])
        flags=duplicate_flags(rows,self.c,{5:"vehicle",7:"vehicle"})
        self.assertEqual(len(flags),1)
        self.assertEqual((flags[0]["track_id"],flags[0]["related_track_id"]),(3,11))
        self.assertEqual((flags[0]["start_frame"],flags[0]["end_frame"]),(14,15))
        self.assertGreaterEqual(flags[0]["observed_value"]["min_iou"],self.c["duplicate_min_iou"])
        self.assertEqual(duplicate_flags(rows,self.c,{5:"bus",7:"truck"}),[])
    def test_no_reference_cli_compatibility_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp);tracks=d/'prediction.txt'
            tracks.write_text(''.join(f'{b.frame},{b.track_id},{b.x},{b.y},{b.w},{b.h},1,-1,-1,-1\n' for b in self.pair()))
            review_file(tracks,DEFAULT_CONFIG,d/'legacy')
            tool=Path(__file__).resolve().parents[1]/'tools/review_tracks_v2.py'
            subprocess.run([sys.executable,str(tool),'--tracks',str(tracks),'--out-dir',str(d/'compat'),'--compat-v1'],cwd=d,check=True,capture_output=True)
            for ext in ['json','csv']:self.assertEqual((d/f'legacy/review_flags.{ext}').read_bytes(),(d/f'compat/review_flags.{ext}').read_bytes())
            subprocess.run([sys.executable,str(tool),'--tracks',str(tracks),'--out-dir',str(d/'v2')],cwd=d,check=True,capture_output=True)
            self.assertEqual(json.loads((d/'v2/review_flags_v2.json').read_text())['schema_version'],2)
            with self.assertRaises(ValueError):review_v2(tracks,DEFAULT_CONFIG,DEFAULT_V2,d/'v2')
            self.assertFalse(any('gt' in p.name for p in d.iterdir()))


if __name__=='__main__':unittest.main()
