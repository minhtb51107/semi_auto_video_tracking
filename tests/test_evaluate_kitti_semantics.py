import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from evaluate_kitti_semantics import (KittiGT, intersection_over_prediction,
                                      parse_kitti_tracking, preprocess_car)
from motlib import Det


def row(frame, tid, kind, box, trunc=0, occ=0, line=1):
    x, y, w, h = box
    return KittiGT(frame, tid, kind, trunc, occ, Det(frame, tid, x, y, w, h), line)


class KittiSemanticsTests(unittest.TestCase):
    def test_van_invalid_car_small_and_dontcare_are_ignored(self):
        rows = [row(1, 1, 'Car', (0, 0, 40, 40)),
                row(1, 2, 'Van', (50, 0, 40, 40)),
                row(1, 3, 'Car', (100, 0, 40, 40), trunc=1),
                row(1, -1, 'DontCare', (150, 0, 40, 40))]
        pred = [Det(1, 10, 0, 0, 40, 40), Det(1, 11, 50, 0, 40, 40),
                Det(1, 12, 100, 0, 40, 40), Det(1, 13, 150, 0, 40, 40),
                Det(1, 14, 220, 0, 40, 25), Det(1, 15, 280, 0, 40, 26)]
        gt, kept, _, audit = preprocess_car(rows, pred)
        self.assertEqual([d.track_id for d in gt], [1])
        self.assertEqual([d.track_id for d in kept], [10, 15])
        statuses = {r['pred_track_id']: r['status'] for r in audit}
        self.assertEqual(statuses[11], 'IGNORED_MATCHED_VAN_DISTRACTOR')
        self.assertEqual(statuses[12], 'IGNORED_MATCHED_IGNORED_CAR')
        self.assertIn('DONTCARE', statuses[13])
        self.assertIn('HEIGHT', statuses[14])

    def test_matching_precedes_ignore_and_strict_dontcare_boundary(self):
        rows = [row(1, 1, 'Car', (0, 0, 20, 20)),
                row(1, -1, 'DontCare', (0, 0, 20, 20)),
                row(1, -1, 'DontCare', (100, 0, 20, 30))]
        # Matched 20px-high prediction stays. Unmatched exactly 50% DontCare also stays.
        pred = [Det(1, 10, 0, 0, 20, 20), Det(1, 11, 100, 0, 40, 30)]
        _, kept, _, audit = preprocess_car(rows, pred)
        self.assertEqual([d.track_id for d in kept], [10, 11])
        self.assertAlmostEqual(intersection_over_prediction(pred[1], rows[2].box), 0.5)
        self.assertEqual(audit[0]['status'], 'KEPT')

    def test_excluded_truck_and_deterministic_output(self):
        rows = [row(1, 1, 'Truck', (0, 0, 40, 40)), row(1, 2, 'Car', (50, 0, 40, 40))]
        pred = [Det(1, 10, 50, 0, 40, 40)]
        first = preprocess_car(rows, pred)
        second = preprocess_car(rows, pred)
        self.assertEqual(first, second)
        self.assertEqual([d.track_id for d in first[0]], [2])
        self.assertEqual(first[2][0]['status'], 'EXCLUDED_CLASS')

    def test_ioa_greater_than_half_and_hungarian_duplicate(self):
        rows = [row(1, 1, 'Car', (0, 0, 40, 40)),
                row(1, -1, 'DontCare', (100, 0, 21, 30))]
        pred = [Det(1, 10, 0, 0, 40, 40), Det(1, 11, 0, 0, 38, 38),
                Det(1, 12, 100, 0, 40, 30)]
        _, kept, _, audit = preprocess_car(rows, pred)
        # One duplicate remains as FP; DontCare IoA=21/40 removes the third prediction.
        self.assertEqual({d.track_id for d in kept}, {10, 11})
        self.assertEqual(next(r for r in audit if r['pred_track_id'] == 12)['status'],
                         'IGNORED_UNMATCHED_DONTCARE_IOA_GT_0_5')

    def test_parser_rejects_malformed_or_nonfinite_rows(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'labels.txt'
            for value in ('0 0 Car\n',
                          '0 0 Car 0 0 0 nan 0 10 10 1 1 1 1 1 1 0\n',
                          '0 0 Car 0 0 0 10 0 5 10 1 1 1 1 1 1 0\n'):
                path.write_text(value)
                with self.assertRaises(ValueError):
                    parse_kitti_tracking(path)


if __name__ == '__main__':
    unittest.main()
