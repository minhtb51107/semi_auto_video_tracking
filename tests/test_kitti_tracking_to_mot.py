import sys
from pathlib import Path
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from kitti_tracking_to_mot import convert
from motlib import parse_mot


class KittiConversionTests(unittest.TestCase):
    def test_all_classes_and_determinism(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder); (p/'000000.png').touch(); (p/'000001.png').touch()
            kinds=['Car','Van','Truck','Pedestrian','Person_sitting','Cyclist','Tram','Misc','DontCare']
            lines=[f'0 {i if k!="DontCare" else -1} {k} 0 0 0 1.5 2.5 11.5 22.5 1 1 1 1 1 1 0\n' for i,k in enumerate(kinds)]
            lines.append('1 0 Car 1 2 0 2 3 12 23 1 1 1 1 1 1 0\n')
            label=p/'labels.txt'; label.write_text(''.join(lines))
            text,audit=convert(label,p)
            self.assertEqual((text,audit),convert(label,p))
            self.assertEqual(audit['kept_rows'],4)
            self.assertEqual(audit['kept_tracks'],3)
            self.assertEqual({r['type'] for r in audit['records'] if r['kept']},{'Car','Van','Truck'})
            self.assertEqual(text.splitlines()[-1],'2,1,2.000000,3.000000,10.000000,20.000000,1,-1,-1,-1')
            label.write_text(''.join(reversed(lines)))
            self.assertEqual(convert(label,p)[0],text)

    def test_mapping_ignored_regions_and_parser_roundtrip(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder); (p/'000000.png').touch(); label=p/'labels.txt'
            label.write_text('0 0 Car 0 0 0 10 20 30 50 1 1 1 1 1 1 0\n'
                             '0 -1 DontCare -1 -1 -10 0 0 5 5 -1 -1 -1 -1 -1 -1 -1\n'
                             '0 2 Pedestrian 0 0 0 50 50 60 70 1 1 1 1 1 1 0\n')
            text,audit=convert(label,p); out=p/'gt.txt'; out.write_text(text)
            row=parse_mot(out)[0]
            self.assertEqual((row.frame,row.track_id,row.x,row.y,row.w,row.h),(1,1,10,20,20,30))
            self.assertEqual(audit['kept_rows'],1); self.assertEqual(len(audit['records']),3)
            self.assertIsNone(audit['records'][1]['mot_track_id'])

    def test_reject_invalid_or_missing_data(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder); (p/'000000.png').touch(); label=p/'labels.txt'
            good='0 0 Van 0 0 0 10 20 30 50 1 1 1 1 1 1 0\n'
            for bad in [good+good,good.replace('30 50','5 50'),good.replace('10 20','nan 20'),
                        good.replace('0 0 Van','1 0 Van'),'0 0 Car\n','']:
                label.write_text(bad)
                with self.assertRaises(ValueError): convert(label,p)
            label.write_text(good); (p/'000002.png').touch()
            with self.assertRaises(ValueError): convert(label,p)


if __name__=='__main__': unittest.main()
