/* Shared pure pilot accounting. No synthetic value is a human result. */
(function(root){
  function validateSession(s){
    if(s.schema_version!==1 || s.kind!=='human_recorded' || s.status!=='completed') throw Error('Chỉ nhận phiên human_recorded đã hoàn tất; loại practice/QA/draft.');
    if(!['A','B'].includes(s.mode)||!s.session_id||!s.reviewer||!Array.isArray(s.findings)||!Array.isArray(s.events)||!Array.isArray(s.viewed_frames)||!Array.isArray(s.frame_displays)||!s.event_verdicts) throw Error('Session thiếu trường bắt buộc.');
    const wall=Date.parse(s.ended_at)-Date.parse(s.started_at);
    if(!Number.isFinite(wall)||wall<=0||!Number.isFinite(s.active_ms)||s.active_ms<=0||s.active_ms>wall+1000) throw Error('Timing không hợp lệ; kiểm đồng hồ/gián đoạn.');
    if(s.viewed_frames.some(f=>!Number.isInteger(f)||f<1||f>s.total_frames)) throw Error('Frame ngoài sequence.');
    if(new Set(s.findings.map(f=>f.finding_id)).size!==s.findings.length) throw Error('Finding IDs bị trùng.');
    if(s.mode==='A'&&new Set(s.viewed_frames).size!==s.total_frames)throw Error('Baseline chưa xem hết frame.');
    if(s.mode==='A'&&[...new Set(s.frame_displays.map(d=>d.frame))].some((f,i)=>f!==i+1))throw Error('Baseline first-pass không tuần tự.');
    if(!Number.isInteger(s.correction_actions)||s.correction_actions<0)throw Error('Correction count không hợp lệ.');
    if(s.mode==='B'&&s.events.some(e=>!['TRUE_ISSUE','BENIGN_EVENT','FALSE_ALERT','UNCERTAIN'].includes(s.event_verdicts[e.event_id]?.verdict)))throw Error('Thiếu event verdict hợp lệ.');
    return wall;
  }
  function summarize(s,decisions,references){
    const wall=validateSession(s), rows=s.findings.map(f=>decisions[s.session_id+':'+f.finding_id]);
    const validVerdicts=['TRUE_ISSUE','BENIGN_EVENT','FALSE_ALERT','UNCERTAIN'];
    const refs=new Set(references.filter(r=>r.sequence===s.sequence).map(r=>r.reference_issue_id));
    const complete=rows.every(d=>d&&validVerdicts.includes(d.verdict)&&
      (d.verdict!=='TRUE_ISSUE'||(d.canonical_id&&(refs.has(d.canonical_id)||d.canonical_id.startsWith('NEW-'))&&typeof d.note==='string'&&d.note.trim())));
    const found=complete?new Set(rows.filter(d=>d.verdict==='TRUE_ISSUE').map(d=>d.canonical_id)):null;
    const known=found?[...found].filter(id=>refs.has(id)):null;
    const rated=Object.values(s.event_verdicts||{}).map(v=>v.verdict);
    const resolved=rated.filter(v=>['TRUE_ISSUE','BENIGN_EVENT','FALSE_ALERT'].includes(v));
    const ratio=(a,b)=>b>0?a/b:null;
    const scope=new Set();for(const e of s.events)for(let f=e.context_start;f<=e.context_end;f++)scope.add(f);
    return {session_id:s.session_id,reviewer:s.reviewer,sequence:s.sequence,mode:s.mode,
      order_group:s.order_group,session_number:s.session_number,familiarity:s.familiarity,
      started_at:s.started_at,ended_at:s.ended_at,active_seconds:s.active_ms/1000,wall_seconds:wall/1000,
      reviewed_frames:new Set(s.viewed_frames).size,frame_displays:s.frame_displays.length,
      findings_reported:s.findings.length,correction_actions_self_reported:s.correction_actions,
      adjudication_complete:complete,confirmed_issues_found:found?found.size:null,
      known_issues_found:known?known.length:null,known_reference_count:refs.size,
      missed_confirmed_issues:known?refs.size-known.length:null,
      missed_reference_ids:known?[...refs].filter(id=>!known.includes(id)):null,
      issues_per_minute:found?ratio(found.size,s.active_ms/60000):null,
      frames_per_confirmed_issue:found?ratio(new Set(s.viewed_frames).size,found.size):null,
      recall_partial_reference:known?ratio(known.length,refs.size):null,
      reviewer_rated_event_precision:ratio(resolved.filter(v=>v==='TRUE_ISSUE').length,resolved.length),
      uncertain_events:rated.filter(v=>v==='UNCERTAIN').length,event_active_ms:s.event_active_ms,
      context_expansion_actions:(s.actions||[]).filter(a=>a.action==='expand_context').length,
      ui_action_count:(s.actions||[]).length,
      tool_metrics:{available_events:s.mode==='B'?s.events.length:null,candidate_context_frames:s.mode==='B'?scope.size:null,total_frames:s.total_frames},
      interpretation:'human self-recorded workflow; partial historical reference; not controlled-study proof'};
  }
  function paired(rows){
    const groups={};for(const r of rows){const k=r.reviewer+':'+r.sequence;(groups[k]||=[]).push(r);}
    return Object.entries(groups).map(([key,rs])=>{
      const a=rs.filter(r=>r.mode==='A'),b=rs.filter(r=>r.mode==='B');
      if(a.length!==1||b.length!==1)return {pair:key,status:'NEEDS_EXACTLY_ONE_A_AND_ONE_B; choose repeat sessions explicitly'};
      return {pair:key,status:'PAIRED_DESCRIPTIVE_ONLY',baseline:a[0],assisted:b[0],
        active_seconds_difference_A_minus_B:a[0].active_seconds-b[0].active_seconds,
        adjudication_complete:a[0].adjudication_complete&&b[0].adjudication_complete};
    });
  }
  const api={validateSession,summarize,paired};root.PilotMetrics=api;
  if(typeof module!=='undefined')module.exports=api;
})(typeof globalThis!=='undefined'?globalThis:this);
