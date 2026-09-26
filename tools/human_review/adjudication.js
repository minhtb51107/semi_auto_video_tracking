'use strict';
const references=JSON.parse(document.getElementById('referenceData').textContent),$=id=>document.getElementById(id);
let sessions=[],decisions={};const storage='pilot-adjudication-v1';
try{decisions=JSON.parse(localStorage.getItem(storage)||'{}');}catch(e){}
const verdicts=['','TRUE_ISSUE','BENIGN_EVENT','FALSE_ALERT','UNCERTAIN'];
function save(){try{localStorage.setItem(storage,JSON.stringify(decisions));}catch(e){$('error').textContent='Không lưu được draft adjudication. Export CSV khi hoàn tất.';}}
function field(label,el){const box=document.createElement('label');box.append(document.createTextNode(label+' '),el);return box;}
function renderDecisions(){
  $('decisions').replaceChildren();
  for(const s of sessions){
    const h=document.createElement('h3');h.textContent=`${s.reviewer} · ${s.sequence} · Mode ${s.mode} · ${s.session_id}`;$('decisions').append(h);
    if(!s.findings.length){const p=document.createElement('p');p.textContent='Reviewer ghi 0 findings. Known-reference misses vẫn được tính sau khi import.';$('decisions').append(p);}
    for(const f of s.findings){
      const key=s.session_id+':'+f.finding_id,d=decisions[key]||{verdict:'',canonical_id:'',note:''};decisions[key]=d;
      const div=document.createElement('div');div.className='finding';const p=document.createElement('p');p.textContent=`${f.finding_id} · frame ${f.start_frame}–${f.end_frame} · track ${f.tracks}: ${f.fix_type} — ${f.note}`;div.append(p);
      const v=document.createElement('select');for(const text of verdicts){const op=document.createElement('option');op.value=text;op.textContent=text||'Chưa adjudicate';v.append(op);}v.value=d.verdict;
      const id=document.createElement('input'),list=document.createElement('datalist');list.id='list-'+key.replaceAll(':','-');id.setAttribute('list',list.id);id.placeholder='Reference ID hoặc NEW-...';id.value=d.canonical_id;
      for(const r of references.filter(r=>r.sequence===s.sequence)){const op=document.createElement('option');op.value=r.reference_issue_id;op.label=r.issue_type+' '+r.note;list.append(op);}
      const note=document.createElement('input');note.value=d.note;note.placeholder='Reference/ảnh/context xác nhận hoặc lý do chưa rõ';
      for(const el of [v,id,note])el.onchange=()=>{decisions[key]={verdict:v.value,canonical_id:id.value.trim(),note:note.value};save();renderSummary();};
      div.append(field('Verdict',v),field('Canonical issue',id),list,field('Evidence note',note));$('decisions').append(div);
    }
  }
}
function metrics(){return sessions.map(s=>PilotMetrics.summarize(s,decisions,references));}
function renderSummary(){
  $('empty').hidden=!!sessions.length;$('summary').replaceChildren();$('pairs').textContent='';
  if(!sessions.length)return;
  const rows=metrics(),fields=['reviewer','sequence','mode','active_seconds','wall_seconds','reviewed_frames','findings_reported','confirmed_issues_found','missed_confirmed_issues','issues_per_minute','frames_per_confirmed_issue','recall_partial_reference','reviewer_rated_event_precision','uncertain_events','correction_actions_self_reported'];
  const table=document.createElement('table'),head=document.createElement('tr');for(const k of fields){const th=document.createElement('th');th.textContent=k;head.append(th);}table.append(head);
  for(const r of rows){const tr=document.createElement('tr');for(const k of fields){const td=document.createElement('td');td.textContent=r[k]===null?'N/A (pending / undefined)':typeof r[k]==='number'?String(Math.round(r[k]*1000)/1000):r[k];tr.append(td);}table.append(tr);}$('summary').append(table);
  $('pairs').textContent=JSON.stringify(PilotMetrics.paired(rows),null,2);
}
$('files').onchange=async()=>{
  $('error').textContent='';for(const file of $('files').files){try{const s=JSON.parse(await file.text());PilotMetrics.validateSession(s);if(!references.some(r=>r.sequence===s.sequence))throw Error('Sequence ngoài pilot package.');if(sessions.some(x=>x.session_id===s.session_id))throw Error('Session ID đã được nhập; không cộng hai lần.');sessions.push(s);}catch(e){$('error').textContent+=file.name+': '+e.message+'\n';}}
  renderDecisions();renderSummary();
};
$('clear').onclick=()=>{sessions=[];$('files').value='';renderDecisions();renderSummary();};
function download(name,text,type){const a=document.createElement('a'),u=URL.createObjectURL(new Blob([text],{type}));a.href=u;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(u),1000);}
function canExport(){if(!$('adjudicator').value.trim()||!sessions.length){$('error').textContent='Nhập adjudicator ID và ít nhất một human session.';return false;}if(metrics().some(r=>!r.adjudication_complete)){$('error').textContent='Hoàn thành verdict/canonical ID/evidence cho mọi finding trước khi xuất kết quả cuối.';return false;}return true;}
$('exportSummary').onclick=()=>{if(!canExport())return;const rows=metrics();download('human_review_comparison.json',JSON.stringify({schema_version:1,generated_at:new Date().toISOString(),adjudicator:$('adjudicator').value,independence:$('independence').value,reference_scope:'historical_partial_v1',references,summaries:rows,pairs:PilotMetrics.paired(rows),decisions},null,2),'application/json');};
$('exportAdjudication').onclick=()=>{if(!canExport())return;const keys=['session_id','sequence','finding_id','verdict','canonical_id','note','adjudicator','independence'];const rows=sessions.flatMap(s=>s.findings.map(f=>({session_id:s.session_id,sequence:s.sequence,finding_id:f.finding_id,...decisions[s.session_id+':'+f.finding_id],adjudicator:$('adjudicator').value,independence:$('independence').value})));
  const q=v=>{let t=String(v??'');if(/^[=+@-]/.test(t))t="'"+t;return '"'+t.replaceAll('"','""')+'"';};download('human_review_adjudication.csv',[keys.join(','),...rows.map(r=>keys.map(k=>q(r[k])).join(','))].join('\r\n'),'text/csv;charset=utf-8');};
$('references').textContent=JSON.stringify(references,null,2);renderSummary();
