'use strict';
const D=JSON.parse(document.getElementById('payload').textContent),$=id=>document.getElementById(id);
const storageKey='review-pilot-v1:'+D.sequence+':'+D.mode+':'+D.package_id;
let S=null,running=false,lastTick=0,frame=1,eventId=D.events[0]?.event_id||null,request=0,range=[1,D.total_frames];
const warn=t=>$('warning').textContent=t;
function accrue(){if(!running)return;const now=performance.now(),delta=Math.max(0,now-lastTick);lastTick=now;S.active_ms+=delta;const k=eventId||'baseline';S.event_active_ms[k]=(S.event_active_ms[k]||0)+delta;}
function record(action,detail={}){if(S)S.actions.push({at:new Date().toISOString(),action,...detail});}
function save(){if(!S)return;accrue();S.last_saved_at=new Date().toISOString();try{localStorage.setItem(storageKey,JSON.stringify(S));}catch(e){warn('Không lưu được draft trong browser. Export JSON checkpoint thường xuyên.');}}
function mutable(){return !!S&&S.status!=='completed';}
function active(){if(!running){warn('Nhấn Start/Resume trước khi review hoặc ghi finding.');return false;}return true;}
function currentEvent(){return D.events.find(e=>e.event_id===eventId);}
function refresh(){
  $('status').textContent=S?(S.status==='completed'?'Đã hoàn tất':running?'Đang đo':'Đã pause'):'Chưa bắt đầu';
  $('timing').textContent=S?`Active ${(S.active_ms/1000).toFixed(1)}s · ${new Set(S.viewed_frames).size}/${D.total_frames} frames · ${S.findings.length} findings`:'';
  $('start').disabled=!!S;$('resume').disabled=!mutable()||running;$('pause').disabled=!running;$('finish').disabled=!running;
  for(const id of ['reviewer','group','sessionNumber','familiarity'])$(id).disabled=!!S;
  if(S){$('reviewer').value=S.reviewer;$('group').value=S.order_group;$('sessionNumber').value=S.session_number;$('familiarity').value=S.familiarity;}
  $('export').disabled=!S;$('csv').disabled=!S;$('viewer').hidden=!running;
  for(const id of ['previous','next','go','expand','saveVerdict','addFinding','event','frame','useFrame'])$(id).disabled=!running;
  for(const id of ['verdict','eventFix','eventNote','findingStart','findingEnd','findingTracks','findingType','findingNote'])$(id).disabled=!running;
  $('corrections').disabled=!mutable();$('sessionNote').disabled=!mutable();
}
function display(f){
  if(!active())return;const target=Math.max(1,Math.min(D.total_frames,Math.trunc(Number(f)||1)));
  if(D.mode==='A'&&target>Math.max(0,...S.viewed_frames)+1){warn('Baseline: lần xem đầu phải tuần tự. Có thể quay lại frame đã xem.');return;}
  accrue();frame=target;const token=++request;
  const img=new Image();img.onload=()=>{
    if(token!==request||!running)return;
    const c=$('canvas');c.width=img.naturalWidth;c.height=img.naturalHeight;const ctx=c.getContext('2d');ctx.drawImage(img,0,0);
    const e=currentEvent();for(const b of D.boxes[String(frame)]||[]){const color=e&&b.id===e.track_id?'#ffb000':e&&e.related_track_ids.includes(b.id)?'#00e8ff':'#ff3030';ctx.strokeStyle=color;ctx.lineWidth=2;ctx.strokeRect(b.x,b.y,b.w,b.h);ctx.font='bold 16px sans-serif';ctx.lineWidth=3;ctx.strokeStyle='#000';ctx.strokeText('P'+b.id,b.x,Math.max(17,b.y));ctx.fillStyle=color;ctx.fillText('P'+b.id,b.x,Math.max(17,b.y));}
    S.viewed_frames.push(frame);S.viewed_frames=[...new Set(S.viewed_frames)];S.frame_displays.push({frame,event_id:eventId,at:new Date().toISOString(),active_ms:S.active_ms});
    $('frame').value=frame;$('frameInfo').textContent=`MOT ${frame}/${D.total_frames} (KITTI ${frame-1})`;$('framePath').textContent='Context image: '+img.getAttribute('src');save();refresh();
  };img.onerror=()=>{pause('image_error');warn('Không đọc được ảnh '+frame+'. Kiểm tra thư mục images; chưa tính frame này.');};img.src=D.images[String(frame)];
}
function selectEvent(id){if(!active())return;accrue();eventId=id;S.current_event=id;const e=currentEvent();range=[e.context_start,e.context_end];const v=S.event_verdicts[id]||{};
  $('verdict').value=v.verdict||'';$('eventFix').value=v.fix_type||'';$('eventNote').value=v.note||'';
  $('eventInfo').textContent=`${id} · P${e.track_id} · related ${e.related_track_ids.join(', ')||'none'}\n${e.reasons.join(' + ')}\nEvent ${e.start_frame}–${e.end_frame}; anchor ${e.anchor_frame}; context ${e.context_start}–${e.context_end}`;
  $('range').textContent=`Context ${range[0]}–${range[1]}`;record('select_event',{event_id:id});display(range[0]);}
function pause(reason='manual'){if(!running)return;accrue();running=false;S.status='paused';record('pause',{reason});save();refresh();}
function resume(){if(!mutable())return;running=true;lastTick=performance.now();S.status='running';record('resume');refresh();if(eventId&&!$('eventInfo').textContent)selectEvent(eventId);else display(frame);}
function download(name,text,type='application/json'){if(window.PILOT_QA){window.qaDownload={name,text};return;}const a=document.createElement('a');const u=URL.createObjectURL(new Blob([text],{type}));a.href=u;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(u),1000);}
function exportJSON(){if(!S)return;save();download(`${S.session_id}.json`,JSON.stringify(S,null,2));}
function csvCell(v){let s=typeof v==='object'?JSON.stringify(v):String(v??'');if(/^[=+@-]/.test(s))s="'"+s;return '"'+s.replaceAll('"','""')+'"';}
function exportCSV(){if(!S)return;save();const rows=S.mode==='B'?D.events.map(e=>({...e,...S.event_verdicts[e.event_id]})):S.findings.length?S.findings:[{}];
  const normalized=rows.map(r=>({session_id:S.session_id,kind:S.kind,reviewer:S.reviewer,sequence:S.sequence,mode:S.mode,status:S.status,started_at:S.started_at,ended_at:S.ended_at,active_seconds:S.active_ms/1000,reviewed_frames:new Set(S.viewed_frames).size,findings_reported:S.findings.length,correction_actions_self_reported:S.correction_actions,...r}));
  const keys=[...new Set(normalized.flatMap(Object.keys))];download(S.session_id+'.csv',[keys.join(','),...normalized.map(r=>keys.map(k=>csvCell(r[k])).join(','))].join('\r\n'),'text/csv;charset=utf-8');}
function renderFindings(){const host=$('findings');host.replaceChildren();for(const f of S?.findings||[]){const div=document.createElement('div');div.className='finding';div.textContent=`${f.finding_id}: frames ${f.start_frame}–${f.end_frame}, P${f.tracks}, ${f.fix_type}: ${f.note} `;if(mutable()){const b=document.createElement('button');b.textContent='Xóa finding nhập nhầm';b.onclick=()=>{if(!active())return;S.findings=S.findings.filter(x=>x.finding_id!==f.finding_id);record('remove_finding',{finding_id:f.finding_id});save();renderFindings();refresh();};div.append(b);}host.append(div);}}
$('title').textContent=`${D.practice?'PRACTICE — ':''}${D.sequence} · Mode ${D.mode}`;
$('intro').textContent=D.mode==='A'?'Baseline: xem tuần tự từ đầu đến cuối, tìm vấn đề bằng predicted boxes.':'Assisted: bắt đầu từ event queue; mở rộng context tùy cần. Verdict event và finding là hai bản ghi riêng.';
$('eventPanel').hidden=D.mode!=='B';for(const e of D.events){const op=document.createElement('option');op.value=e.event_id;op.textContent=`${e.event_id} · P${e.track_id} · ${e.start_frame}–${e.end_frame}`;$('event').append(op);}
$('start').onclick=()=>{if(S)return;if(!$('reviewer').value.trim()||$('familiarity').value==='unknown'||!Number.isInteger(Number($('sessionNumber').value))||Number($('sessionNumber').value)<1||Number($('sessionNumber').value)>4)return warn('Nhập reviewer ID, mức độ quen dữ liệu và phiên số1–4.');
  S={schema_version:1,kind:D.practice?'practice':'human_recorded',session_id:'pilot-'+D.sequence+'-'+D.mode+'-'+crypto.randomUUID(),package_id:D.package_id,sequence:D.sequence,mode:D.mode,reviewer:$('reviewer').value.trim(),order_group:$('group').value,session_number:Number($('sessionNumber').value),familiarity:$('familiarity').value,total_frames:D.total_frames,status:'paused',started_at:new Date().toISOString(),ended_at:null,active_ms:0,viewed_frames:[],frame_displays:[],events:D.events,event_verdicts:{},event_active_ms:{},findings:[],next_finding:1,actions:[],correction_actions:0,session_note:'',source_hashes:D.source_hashes};warn('');resume();};
$('resume').onclick=resume;$('pause').onclick=()=>pause();$('export').onclick=exportJSON;$('csv').onclick=exportCSV;
$('previous').onclick=()=>{record('previous');display(frame-1);};$('next').onclick=()=>{record('next');display(frame+1);};$('go').onclick=()=>{record('go',{frame:Number($('frame').value)});display($('frame').value);};
$('event').onchange=()=>selectEvent($('event').value);
$('useFrame').onclick=()=>{if(!active())return;$('findingStart').value=frame;$('findingEnd').value=frame;const e=currentEvent();if(e)$('findingTracks').value=[e.track_id,...e.related_track_ids].join(',');record('finding_use_current_frame',{frame});};
$('expand').onclick=()=>{if(!active())return;range=[Math.max(1,range[0]-5),Math.min(D.total_frames,range[1]+5)];record('expand_context',{event_id:eventId,start:range[0],end:range[1]});$('range').textContent=`Expanded ${range[0]}–${range[1]}`;display(range[0]);};
$('saveVerdict').onclick=()=>{if(!active())return;const e=currentEvent();if(!$('verdict').value)return warn('Chọn verdict, có thể UNCERTAIN.');if(!S.frame_displays.some(r=>r.event_id===eventId&&r.frame>=e.context_start&&r.frame<=e.context_end))return warn('Chờ ảnh context hiển thị trước khi lưu verdict.');S.event_verdicts[eventId]={verdict:$('verdict').value,fix_type:$('eventFix').value,note:$('eventNote').value,at:new Date().toISOString()};record('verdict',{event_id:eventId});warn('Đã lưu verdict; nếu có lỗi cần sửa, thêm finding riêng.');save();};
$('addFinding').onclick=()=>{if(!active())return;const a=Number($('findingStart').value),b=Number($('findingEnd').value);if(!Number.isInteger(a)||!Number.isInteger(b)||a<1||b<a||b>D.total_frames||!$('findingType').value.trim())return warn('Nhập range hợp lệ và error/fix type.');S.findings.push({finding_id:'I'+String(S.next_finding++).padStart(4,'0'),start_frame:a,end_frame:b,tracks:$('findingTracks').value,fix_type:$('findingType').value,note:$('findingNote').value,event_id:eventId,at:new Date().toISOString()});record('add_finding');save();renderFindings();refresh();warn('Finding đã lưu. Có thể xóa nếu nhập trùng.');};
$('corrections').onchange=()=>{if(mutable()){S.correction_actions=Math.max(0,Math.trunc(Number($('corrections').value)||0));save();}};
$('sessionNote').onchange=()=>{if(mutable()){S.session_note=$('sessionNote').value;save();}};
$('finish').onclick=()=>{if(!active())return;if(D.mode==='A'&&new Set(S.viewed_frames).size!==D.total_frames)return warn('Baseline cần hiển thị đủ mọi frame.');if(D.mode==='B'&&D.events.some(e=>!S.event_verdicts[e.event_id]))return warn('Cần verdict cho mọi event.');pause('finish');S.status='completed';S.ended_at=new Date().toISOString();S.session_note=$('sessionNote').value;record('finish');save();refresh();renderFindings();exportJSON();warn('Đã hoàn tất. Giữ file JSON tải xuống; sau các phiên mới mở adjudication.');};
$('fresh').onclick=()=>{if(S&&!confirm('Đã export phiên hiện tại? Phiên mới thay draft trong browser, không xóa file đã tải.'))return;try{localStorage.removeItem(storageKey);}catch(e){}S=null;running=false;eventId=D.events[0]?.event_id||null;frame=1;$('eventInfo').textContent='';$('findings').replaceChildren();$('sessionNote').value='';$('corrections').value=0;refresh();};
$('importCheckpoint').onchange=async()=>{pause('import_checkpoint');try{const file=$('importCheckpoint').files[0];if(!file)return;const draft=JSON.parse(await file.text());if(draft.schema_version!==1||draft.package_id!==D.package_id||draft.sequence!==D.sequence||draft.mode!==D.mode||draft.kind!==(D.practice?'practice':'human_recorded')||!['running','paused','completed'].includes(draft.status)||!Array.isArray(draft.findings)||!Array.isArray(draft.frame_displays)||!Number.isFinite(draft.active_ms)||draft.active_ms<0)throw Error('Checkpoint không khớp package hoặc sai format.');if(S&&!confirm('Thay draft hiện tại bằng checkpoint đã chọn?'))return;S=draft;S.events=D.events;if(S.status!=='completed')S.status='paused';eventId=S.current_event||D.events[0]?.event_id||null;frame=S.frame_displays.at(-1)?.frame||1;$('eventInfo').textContent='';$('event').value=eventId||'';$('sessionNote').value=S.session_note;$('corrections').value=S.correction_actions;record('import_checkpoint_paused');save();renderFindings();refresh();warn('Đã khôi phục; thời gian ngoài checkpoint không tự cộng.');}catch(e){warn(e.message);}};
document.addEventListener('visibilitychange',()=>{if(document.hidden)pause('hidden');});window.addEventListener('blur',()=>pause('blur'));window.addEventListener('beforeunload',()=>pause('leave'));
try{const saved=localStorage.getItem(storageKey);if(saved){S=JSON.parse(saved);if(S.package_id!==D.package_id)throw Error('Package mismatch');if(S.status!=='completed')S.status='paused';eventId=S.current_event||D.events[0]?.event_id||null;frame=S.frame_displays.at(-1)?.frame||1;$('corrections').value=S.correction_actions;$('sessionNote').value=S.session_note;record('restore_paused');renderFindings();}}catch(e){S=null;warn('Không đọc được draft; dùng file checkpoint đã export nếu có.');}
setInterval(()=>{if(running){save();refresh();}},1000);refresh();
window.PilotReview={getSession:()=>S,getFrame:()=>frame,pause,display,selectEvent};
