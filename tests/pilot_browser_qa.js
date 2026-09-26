/* Inject only into isolated PRACTICE copies. Never run against human sessions. */
(async function(){
  const get=id=>document.getElementById(id),sleep=ms=>new Promise(r=>setTimeout(r,ms));
  const assert=(v,m)=>{if(!v)throw Error(m);};
  async function until(test){for(let i=0;i<80;i++){if(test())return;await sleep(100);}throw Error('UI timeout');}
  try{
    const data=JSON.parse(get('payload').textContent);assert(data.practice,'QA requires practice');
    get('reviewer').value='AUTOMATED_QA_NOT_HUMAN';get('familiarity').value='new_to_me';get('start').click();
    await until(()=>PilotReview.getSession()?.viewed_frames.includes(1));
    get('finish').click();assert(PilotReview.getSession().status!=='completed','Premature completion should be blocked');
    get('next').click();await until(()=>PilotReview.getSession().viewed_frames.includes(2));
    get('findingStart').value=1;get('findingEnd').value=2;get('findingType').value='SYNTHETIC_QA_ONLY';get('findingNote').value='UI exercise, not a real issue';get('addFinding').click();
    assert(PilotReview.getSession().findings.length===1,'Finding not saved');
    if(data.mode==='B'){get('verdict').value='UNCERTAIN';get('eventNote').value='QA ONLY';get('saveVerdict').click();}
    get('pause').click();const active=PilotReview.getSession().active_ms;await sleep(400);assert(PilotReview.getSession().active_ms===active,'Paused time counted');
    get('resume').click();await until(()=>!get('viewer').hidden);await sleep(200);get('finish').click();
    const s=PilotReview.getSession();assert(s.status==='completed','Finish failed');assert(s.kind==='practice','QA leaked into human kind');
    assert(s.ended_at&&s.started_at&&s.active_ms>0,'Timing missing');assert(JSON.parse(window.qaDownload.text).status==='completed','Export failed');
    let rejected=false;try{PilotMetrics.validateSession(s);}catch(e){rejected=true;}assert(rejected,'Summary accepted practice as human');
    get('viewer').hidden=false;const result=document.createElement('pre');result.id='qa-result';result.textContent='QA_ONLY PASS '+data.mode+' — controls/timing/export/practice exclusion';document.body.prepend(result);document.body.dataset.qaStatus='PASS';
  }catch(e){const result=document.createElement('pre');result.id='qa-result';result.textContent='QA_ONLY FAIL '+e.stack;document.body.prepend(result);document.body.dataset.qaStatus='FAIL';}
})();
