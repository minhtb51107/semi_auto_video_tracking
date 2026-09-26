import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from build_review_package import payload,render,build
from motlib import Det


class HumanReviewTests(unittest.TestCase):
    def setUp(self):
        self.event=dict(event_id='E1',track_id=1,related_track_ids=[],start_frame=1,end_frame=2,anchor_frame=2,reasons=['track_gap'],raw_flag_ids=['F1'],context_start=1,context_end=2)
        self.images={'1':'images/1.jpg','2':'images/2.jpg'}
        self.tracks=[Det(1,1,0,0,10,10),Det(2,1,1,0,10,10)]

    def test_baseline_omits_events_and_gt_and_stable_payload(self):
        a=payload('test','A',self.tracks,[self.event],self.images,2,{})
        self.assertEqual(a['events'],[])
        self.assertNotIn('track_gap',json.dumps(a))
        self.assertEqual(a,payload('test','A',self.tracks,[self.event],self.images,2,{}))
        self.assertEqual(set(a['boxes']['1'][0]),{'id','x','y','w','h'})

    def test_assisted_retains_context_but_not_extra_adjudication(self):
        e=dict(self.event,gt_track_id=99,verdict='TRUE_ISSUE')
        b=payload('test','B',self.tracks,[e],self.images,2,{})
        self.assertNotIn('gt_track_id',b['events'][0]);self.assertNotIn('verdict',b['events'][0])
        self.assertEqual(b['events'][0]['context_end'],2)

    def test_bad_frame_or_context_rejected(self):
        with self.assertRaises(ValueError):payload('x','B',self.tracks,[dict(self.event,context_end=3)],self.images,2,{})
        with self.assertRaises(ValueError):payload('x','A',self.tracks,[],{},2,{})
        with self.assertRaises(ValueError):payload('x','A',[Det(3,1,0,0,1,1)],[],self.images,2,{})

    def test_embedded_payload_safe_and_existing_output_refused(self):
        text=render('<script>__PAYLOAD__</script>',{'x':'</script>'})
        self.assertEqual(text.count('</script>'),1)
        with self.assertRaises(ValueError):build(ROOT/'outputs')

    def test_accounting_javascript_contract(self):
        # Synthetic unit fixtures only: never exported as collected human sessions.
        js=r'''
const assert=require('node:assert/strict');
const M=require('./tools/human_review/metrics.js');
const refs=[{sequence:'s',reference_issue_id:'r1'},{sequence:'s',reference_issue_id:'r2'}];
const session={schema_version:1,kind:'human_recorded',status:'completed',mode:'B',session_id:'UNIT_TEST_ONLY',reviewer:'TEST',sequence:'s',total_frames:2,started_at:'2020-01-01T00:00:00Z',ended_at:'2020-01-01T00:02:00Z',active_ms:60000,viewed_frames:[1,1,2],frame_displays:[{},{},{}],findings:[{finding_id:'i1'},{finding_id:'i2'}],events:[{event_id:'e'}],event_verdicts:{e:{verdict:'TRUE_ISSUE'}},event_active_ms:{e:60000},correction_actions:0};
assert.equal(M.summarize(session,{},refs).confirmed_issues_found,null);
const ds={'UNIT_TEST_ONLY:i1':{verdict:'TRUE_ISSUE',canonical_id:'r1',note:'test evidence'},'UNIT_TEST_ONLY:i2':{verdict:'TRUE_ISSUE',canonical_id:'r1',note:'same synthetic issue'}};
const r=M.summarize(session,ds,refs);assert.equal(r.confirmed_issues_found,1);assert.equal(r.missed_confirmed_issues,1);assert.equal(r.recall_partial_reference,.5);assert.equal(r.reviewed_frames,2);assert.equal(r.issues_per_minute,1);assert.equal(r.frames_per_confirmed_issue,2);assert.equal(r.wall_seconds,120);
assert.throws(()=>M.validateSession({...session,kind:'practice'}));assert.throws(()=>M.validateSession({...session,status:'paused'}));assert.throws(()=>M.validateSession({...session,active_ms:999999}));
assert.equal(M.paired([r])[0].status.startsWith('NEEDS'),true);
assert.equal(M.paired([r,{...r,mode:'A'}])[0].active_seconds_difference_A_minus_B,0);
const zero={...session,findings:[],events:[],event_verdicts:{}};assert.equal(M.summarize(zero,{},refs).frames_per_confirmed_issue,null);
console.log('Synthetic accounting unit checks PASS; no human result');
'''
        result=subprocess.run(['node','-e',js],cwd=ROOT,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)


if __name__=='__main__':unittest.main()
