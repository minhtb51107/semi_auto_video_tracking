"""Real annotation fixtures + controlled corruptions; never modify source labels."""
import csv
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from motlib import Det, MotFormatError, by_track, clear_mot, parse_mot
from review_tracks import analyze, load_config, load_tracks, review_file
from run_tracker import write_mot


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.config = load_config()

    def test_two_real_annotations_and_mutations(self):
        artifacts = ROOT / 'outputs/standalone_mutations'
        artifacts.mkdir(parents=True, exist_ok=True)
        manifest = []
        for clip, count, ntracks, nframes in [('clip_01', 638, 8, 190), ('clip_02', 242, 7, 60)]:
            with self.subTest(clip=clip):
                source = ROOT / 'annotations' / clip / 'gt.txt'
                original = source.read_bytes()
                dets = load_tracks(source)
                self.assertEqual((len(dets), len(by_track(dets)), len({d.frame for d in dets})),
                                 (count, ntracks, nframes))
                self.assertEqual(dets, parse_mot(source))
                self.assertFalse(any(f['reason'] in ('track_gap', 'track_reappeared')
                                     for f in analyze(dets, self.config)))
                track = max(by_track(dets).values(), key=len)
                middle = len(track) // 2
                target = track[middle]
                tid, frame = target.track_id, target.frame
                new_id = max(d.track_id for d in dets) + 100
                gap_frames = set(range(frame, frame + 6))
                cases = {
                    'delete_frame': ([d for d in dets if d.frame != frame], frame + 1, tid, 'track_gap'),
                    'change_id': ([replace(d, track_id=new_id) if d.track_id == tid and d.frame >= frame else d
                                   for d in dets], frame, new_id, 'possible_fragmentation'),
                    'shift_box': ([replace(d, x=d.x + 10000) if d == target else d for d in dets],
                                  frame, tid, 'large_motion_jump'),
                    'resize_box': ([replace(d, w=d.w * 4, h=d.h * 4) if d == target else d for d in dets],
                                   frame, tid, 'abnormal_size_change'),
                    'create_gap': ([d for d in dets if not (d.track_id == tid and d.frame in gap_frames)],
                                   frame + 6, tid, 'track_reappeared'),
                }
                for name, (changed, expected_frame, expected_id, reason) in cases.items():
                    with self.subTest(mutation=name):
                        output = artifacts / clip / name
                        output.mkdir(parents=True, exist_ok=True)
                        copy = output / 'tracks.txt'
                        write_mot([(d.frame, d.track_id, d.x, d.y, d.w, d.h, d.conf) for d in changed], copy)
                        parsed = load_tracks(copy)
                        self.assertEqual(len(parsed), len(changed))
                        result = review_file(copy, ROOT / 'configs/review_thresholds.json', output)
                        matching = [f for f in result['flags'] if
                                    (f['frame_id'], f['track_id'], f['reason']) == (expected_frame, expected_id, reason)]
                        self.assertTrue(matching, (clip, name, expected_frame, expected_id))
                        event = matching[0]
                        if name == 'delete_frame':
                            self.assertEqual((event['observed_value'], event['threshold']), (1, 1))
                        if name == 'create_gap':
                            self.assertEqual((event['observed_value'], event['threshold']), (6, 5))
                        if name == 'resize_box':
                            self.assertGreater(event['observed_value'], event['threshold'])
                        if name == 'change_id':
                            self.assertEqual(event['related_track_id'], tid)
                            switches = clear_mot(dets, parsed)['switches']
                            self.assertTrue(any(s['frame'] == frame and s['to_track'] == new_id for s in switches))
                        if name == 'shift_box':
                            self.assertTrue(any(f['frame_id'] == frame and f['track_id'] == tid
                                                and f['reason'] == 'low_consecutive_iou' for f in result['flags']))
                        manifest.append(dict(clip=clip, mutation=name, source=str(source.relative_to(ROOT)),
                                             source_sha256=hashlib.sha256(original).hexdigest(),
                                             copy=str(copy.relative_to(ROOT)), expected_event=event, passed=True))
                self.assertEqual(source.read_bytes(), original)
        (artifacts / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')

    def test_reference_files_parse_when_present(self):
        for relative in ('gold/clip_01/gt.txt', 'data/clips/clip_02/gt/gt.txt'):
            p = ROOT / relative
            if p.exists():
                self.assertEqual(load_tracks(p), parse_mot(p))

    def test_smooth_motion_entry_exit_global_renumber(self):
        rows = [Det(f, 7, f, 0, 100, 50) for f in range(4, 15)]
        self.assertEqual(analyze(rows, self.config), [])
        self.assertEqual(analyze([replace(d, track_id=77) for d in rows], self.config), [])

    def test_gap_does_not_apply_adjacent_geometry(self):
        flags = analyze([Det(1, 1, 0, 0, 10, 10), Det(8, 1, 1000, 0, 100, 100)], self.config)
        self.assertEqual({f['reason'] for f in flags}, {'track_gap', 'track_reappeared'})
        self.assertTrue(all(f['observed_value'] == 6 and f['frame_id'] == 8 for f in flags))

    def test_fragmentation_window_and_overlap_exclusion(self):
        rows = [Det(1, 1, 0, 0, 10, 10), Det(2, 1, 0, 0, 10, 10), Det(3, 2, 0, 0, 10, 10)]
        flags = analyze(rows, self.config)
        self.assertEqual(len(flags), 1)
        self.assertEqual((flags[0]['reason'], flags[0]['related_track_id']), ('possible_fragmentation', 1))
        self.assertEqual(analyze(rows + [Det(3, 1, 0, 0, 10, 10)], self.config), [])
        self.assertEqual(analyze(rows[:2] + [replace(rows[2], frame=10)], self.config), [])
        self.assertEqual(analyze(rows[:2] + [replace(rows[2], x=100)], self.config), [])

    def test_threshold_boundaries_config_and_sorted_input(self):
        rows = [Det(1, 1, 0, 0, 10, 10), Det(2, 1, 0, 0, 20, 20)]
        self.assertFalse(any(f['reason'] == 'abnormal_size_change' for f in analyze(rows, self.config)))
        config = dict(self.config, abnormal_size_change_max_ratio=1.9)
        self.assertTrue(any(f['reason'] == 'abnormal_size_change' for f in analyze(rows, config)))
        self.assertEqual(analyze(rows, config), analyze(list(reversed(rows)), config))
        for patch in ({'unknown': 5}, {'fragmentation_max_frame_distance': 1.5},
                      {'low_consecutive_iou_min': 2}, {'large_motion_jump_max_diagonals': float('nan')},
                      {'track_gap_min_missing_frames': True}):
            with self.assertRaises(ValueError):
                analyze(rows, dict(self.config, **patch))

    def test_parser_variants_empty_ignored_and_invalid(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'tracks.txt'
            for suffix in ('', ',1', ',1,1,1', ',0.9,-1,-1,-1'):
                path.write_text('\ufeff# comment\n1,2,0,0,10,20' + suffix + '\n', encoding='utf-8')
                self.assertEqual(len(load_tracks(path)), 1)
            path.write_text('1;2;0;0;10;20;1;1;1\n', encoding='utf-8')
            self.assertEqual(len(load_tracks(path)), 1)
            path.write_text('1,2,0,0,10,20,0,1,1\n', encoding='utf-8')
            self.assertEqual(load_tracks(path), [])
            path.write_text('', encoding='utf-8')
            result = review_file(path, ROOT / 'configs/review_thresholds.json', Path(folder) / 'out')
            self.assertTrue(result['summary']['empty_input'])
            self.assertEqual(result['flags'], [])
            for bad in ('1,2,0,0,0,20', '1.5,2,0,0,10,20', '0,2,0,0,10,20',
                        '1,2,nan,0,10,20', '1,2,inf,0,10,20', '1,2,,0,10,20,1',
                        '1,-2,0,0,10,20', '1,2,0,0,10,20\n1,2,1,1,10,20'):
                path.write_text(bad, encoding='utf-8')
                with self.subTest(bad=bad), self.assertRaises(MotFormatError):
                    load_tracks(path)

    def test_cli_csv_json_contract_and_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'tracks.txt'
            path.write_text('1,1,0,0,10,10\n3,1,0,0,10,10\n', encoding='utf-8')
            out = Path(folder) / 'review'
            command = [sys.executable, str(ROOT / 'tools/review_tracks.py'), '--tracks', str(path), '--out-dir', str(out)]
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            document = json.loads((out / 'review_flags.json').read_text())
            with (out / 'review_flags.csv').open(newline='') as stream:
                csv_rows = list(csv.DictReader(stream))
            self.assertEqual(len(csv_rows), len(document['flags']))
            self.assertEqual(csv_rows[0]['reason'], 'track_gap')
            self.assertEqual(int(csv_rows[0]['frame_id']), document['flags'][0]['frame_id'])
            self.assertEqual(float(csv_rows[0]['observed_value']), document['flags'][0]['observed_value'])
            path.write_text('bad', encoding='utf-8')
            failed = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(failed.returncode, 2)


if __name__ == '__main__':
    unittest.main()
