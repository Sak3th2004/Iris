import {useEffect,useRef,useState} from 'react';
import {createRoot} from 'react-dom/client';
import {ArrowRight,Check,History,Mic,Monitor,ShieldCheck,Square,Volume2,VolumeX,X} from 'lucide-react';
import {Desktop} from './Desktop';
import {WriteComparison} from './WriteComparison';
import {api} from './api';
import {startRecording} from './recorder';
import {useSpeech} from './useSpeech';
import './style.css';

type Permission={id:string;sentence:string;resource_type:string;record_id:string;set_fields:Record<string,unknown>;preserve_fields:Record<string,unknown>;forbidden_operations:string[];version:number};
function App(){
  const [input,setInput]=useState(''),[busy,setBusy]=useState(''),[error,setError]=useState(''),[question,setQuestion]=useState('');
  const [snapshot,setSnapshot]=useState<any>(null),[config,setConfig]=useState<any>(null),[permission,setPermission]=useState<Permission|null>(null),[receipt,setReceipt]=useState<any>(null);
  const [voice,setVoice]=useState(true),[recording,setRecording]=useState(false),[capture,setCapture]=useState<string|null>(null);
  const recorder=useRef<Awaited<ReturnType<typeof startRecording>>|null>(null),recordTimer=useRef<ReturnType<typeof setTimeout>|undefined>(undefined);
  const lastJob=useRef(''),busyRef=useRef(false),loaded=useRef(false),parentCapture=useRef<string|null>(null),handsFree=useRef(false),spokenEvent=useRef<number|null>(null),spokenJob=useRef('');
  const openingMic=useRef(false),interaction=useRef(0);
  const {speak,cancel:cancelSpeech}=useSpeech(voice,setError);
  const active=['queued','running'].includes(snapshot?.job?.state);
  const shownPermission=permission||((question||input||recording)?null:snapshot?.permission);
  useEffect(()=>{
    let alive=true,timer:ReturnType<typeof setTimeout>;
    const poll=async()=>{
      try{
        const data=await api('desktop');if(!alive)return;setSnapshot(data);
        const signature=(data.job?.id||'')+(data.job?.state||'')+(data.events?.[0]?.id||'');
        if(signature!==lastJob.current||!loaded.current){
          const [state,detail]=await Promise.all([api('state'),data.job?api('runs/'+data.job.id):Promise.resolve(null)]);
          if(alive){lastJob.current=signature;loaded.current=true;setConfig(state);setReceipt(detail);}
        }
      }catch{if(alive)setError('Workspace connection interrupted. Reconnecting.');}
      finally{if(alive)timer=setTimeout(poll,1000);}
    };
    void poll();return()=>{alive=false;clearTimeout(timer);};
  },[]);
  useEffect(()=>()=>{interaction.current++;clearTimeout(recordTimer.current);void recorder.current?.cancel();},[]);
  function cancelInstruction(){
    interaction.current++;cancelSpeech();handsFree.current=false;parentCapture.current=null;
    if(permission)void api('permissions/'+permission.id+'/revoke',{}).catch(e=>setError(e.message));
    clearTimeout(recordTimer.current);void recorder.current?.cancel();recorder.current=null;
    setRecording(false);setInput('');setCapture(null);setPermission(null);setQuestion('');
  }
  async function openMic(){
    if(recorder.current||openingMic.current||busyRef.current||active)return;
    const turn=interaction.current;openingMic.current=true;cancelSpeech();setError('');handsFree.current=true;setBusy('Opening microphone');
    try{
      const started=await startRecording({parentCaptureId:parentCapture.current});
      if(turn!==interaction.current){await started.cancel();return;}
      recorder.current=started;setRecording(true);
      recordTimer.current=setTimeout(()=>{void toggleMic();},55000);
    }catch(e){if(turn===interaction.current){setError((e as Error).message);setRecording(false);}}
    finally{openingMic.current=false;setBusy('');}
  }
  async function review(){
    if(!input.trim()||busyRef.current||active)return;busyRef.current=true;setBusy('Spark is checking the exact instruction');setError('');setQuestion('');setPermission(null);
    const turn=interaction.current;
    try{
      const data=await api('permissions/interpret',{sentence:input.trim(),capture_id:capture});
      if(turn!==interaction.current){if(data.permission)await api('permissions/'+data.permission.id+'/revoke',{});return;}
      if(data.question){setQuestion(data.question);}
      else{setPermission(data.permission);setCapture(null);parentCapture.current=null;}
      setConfig(await api('state'));
    }catch(e){setError((e as Error).message);}finally{busyRef.current=false;setBusy('');}
  }
  async function delegate(){
    if(!permission||busyRef.current||active)return;busyRef.current=true;setBusy('Handing the permission to the isolated desktop');setError('');
    try{await api('runs',{permission_id:permission.id});setSnapshot(await api('desktop'));setPermission(null);setReceipt(null);setInput('');}
    catch(e){setError((e as Error).message);}finally{busyRef.current=false;setBusy('');}
  }
  async function toggleMic(){
    if(busyRef.current||openingMic.current)return;cancelSpeech();setError('');
    if(!recorder.current){await openMic();return;}
    const current=recorder.current;recorder.current=null;clearTimeout(recordTimer.current);setRecording(false);busyRef.current=true;setBusy('Muse Voice is transcribing');
    const turn=interaction.current;let followup='';
    try{
      const data=await current.stop();if(turn!==interaction.current)return;setInput(data.sentence);setQuestion('');setPermission(null);
      setBusy('Taking the spoken task');
      const compiled=await api('permissions/interpret',{sentence:data.sentence,capture_id:data.capture_id});
      if(turn!==interaction.current){if(compiled.permission)await api('permissions/'+compiled.permission.id+'/revoke',{});return;}
      if(compiled.question){setQuestion(compiled.question);setCapture(data.capture_id);parentCapture.current=data.capture_id;followup=compiled.question;}
      else{
        parentCapture.current=null;setCapture(null);setPermission(compiled.permission);
        setReceipt(null);
        if(voice)void speak('Your permission is ready. Review the protected values, then choose Authorize and start.');
      }
      setConfig(await api('state'));
    }
    catch(e){setError((e as Error).message);}finally{busyRef.current=false;setBusy('');}
    if(followup&&turn===interaction.current&&voice){const played=await speak(followup);if(played&&turn===interaction.current)await openMic();}
  }
  const latest=snapshot?.events?.[0];
  useEffect(()=>{
    if(!voice||!handsFree.current||!latest?.id||latest.id===spokenEvent.current)return;
    if(latest.action!=='held')return;
    spokenEvent.current=latest.id;void speak(latest.detail);
  },[latest?.id]);
  useEffect(()=>{
    const job=receipt?.job?.id;if(!voice||!handsFree.current||!receipt?.receipt||!job||job===spokenJob.current)return;
    spokenJob.current=job;const after=receipt.receipt.after;void speak(`${after.fields.name}. ${after.fields.day||'Quantity '+after.fields.quantity}. Saved.`);
  },[receipt]);
  const held=active && latest?.action==='held';
  const checking=active && latest?.action==='visual review';
  const verdict=permission?'Ready for review':snapshot?.job?.state==='complete'?'Allowed & verified':snapshot?.job?.state==='paused'?'Paused':snapshot?.job?.state==='stopped'?'Stopped':active?'In progress':'Awaiting instruction';
  const audit=(config?.audit||[]).filter((a:any)=>a.proposal?.permission_id===shownPermission?.id);
  return <div className="app">
    <header className="topbar"><a href="/" className="wordmark" aria-label="Iris home">iris<span>PERMISSION AT THE WRITE</span></a><div className="topbar-right"><span className="provider"><i className={config?.meta?.configured&&config?.reader?.configured?'green-dot':'grey-dot'}/>{config?.meta?.configured?'Muse Spark':'Meta not connected'} · {config?.reader?.configured?'Blind reader connected':'Reader not connected'}</span><a className="session-button" href="/classic">Manage invented records<ArrowRight size={14}/></a></div></header>
    <main className="workspace"><section className="permission-column">
      <div className="intro"><span className="eyebrow">YOUR DESK · THEIR MACHINE</span><h1>You leave.<br/>The other machine stays.</h1><p>Lock the change. The agent works on a separate desktop.<br/>The right button on the wrong person does not save.</p></div>
      <form className={`composer ${recording?'recording':''}`} onSubmit={e=>{e.preventDefault();void review();}}>
        <label htmlFor="sentence">Your instruction</label><textarea id="sentence" placeholder={recording?'Listening. Take your time, then choose Finish recording.':'Name the record, the exact change, and what must stay unchanged.'} value={input} onChange={e=>{setInput(e.target.value);setPermission(null);setQuestion('');if(capture)setCapture(null);parentCapture.current=null;}} disabled={recording||active||!!busy}/>
        <div className="composer-tools"><button type="button" className={recording?'mic-active':''} disabled={!!busy||active} aria-label={recording?'Finish recording':'Speak your instruction'} onClick={()=>void toggleMic()}>{recording?<Square size={16}/>:<Mic size={18}/>}<span>{recording?'Finish recording':'Speak to start'}</span></button><button type="button" disabled={!config?.speech?.configured} aria-label={voice?'Mute spoken feedback':'Enable spoken feedback'} aria-pressed={voice} onClick={()=>{setVoice(!voice);cancelSpeech();}}>{voice?<Volume2 size={17}/>:<VolumeX size={17}/>}</button></div>
        <button className="primary" id="interpret" type="submit" disabled={!input.trim()||!!busy||active||recording}>Review permission<ArrowRight size={16}/></button>
      </form>
      {(recording||question||permission||input||busy)&&!active&&<button className="session-button" type="button" disabled={!!busy&&!!permission} onClick={cancelInstruction}>Discard instruction<X size={14}/></button>}
      {capture&&<p className="capture-note">Answer the question by voice. Your original instruction and protected values stay locked to the first recording. Editing starts a new instruction.</p>}
      {busy&&<p className="status" role="status">{busy}</p>}
      {error&&<div className="error" role="alert"><span>{error}</span><button aria-label="Dismiss error" onClick={()=>setError('')}><X size={15}/></button></div>}
      {question&&<section className="ask-state"><span className="eyebrow">PAUSED · ONE DETAIL NEEDED</span><p>{question}</p><small>{capture?'Answer by voice to keep the original snapshot.':'Update the full instruction above.'} Nothing has been saved.</small></section>}
      {shownPermission?<section className="permission" aria-label="Permission card"><div className="permission-title"><ShieldCheck size={19}/><strong>Locked permission</strong><span id="permission-status">{verdict}</span></div><blockquote>{shownPermission.sentence}</blockquote><div className="record-identity">{shownPermission.resource_type} / {shownPermission.record_id}<span>VERSION {shownPermission.version}</span></div><dl>{Object.entries(shownPermission.set_fields).map(([key,value])=><div key={key}><dt>Set {key}</dt><dd>{String(value)}</dd></div>)}{Object.entries(shownPermission.preserve_fields).map(([key,value])=><div key={key} className="preserved"><dt>Keep {key}</dt><dd>{String(value)}</dd></div>)}</dl><div className="forbidden"><span>FORBIDDEN</span><p>{shownPermission.forbidden_operations.join(', ')}; every other record</p></div>{permission&&<button className="primary" id="run-agent" disabled={!!busy||active||!snapshot?.connected} onClick={()=>void delegate()}>Authorize & start<ArrowRight size={16}/></button>}</section>:<div className="empty-permission"><ShieldCheck size={24}/><p>Your permission will appear here.</p><span>No record is writable without it.</span></div>}
      <p className="scope-note">A booking keeps its clock time and its price. Overlapping appointments are refused. Weekdays mean the next occurrence in Asia/Kolkata. The shop counter uses the same gate.</p>
    </section>
    <section className="work-area"><div className="work-heading"><div><span className="eyebrow">THE AGENT DESK</span><h2>A separate place to work.</h2></div><span className="isolation-tag"><ShieldCheck size={13}/>Isolated Linux desktop</span></div><Desktop working={active} held={held} pulse={latest?.id||0}/>
      <div className="task-strip"><div className={`task-symbol ${active?'active':''}`}>{receipt?.receipt?<Check size={21}/>:<Monitor size={21}/>}</div><div><h3>{held?'Click held':checking?'Reading the form pixels':active?'Iris has the cursor':snapshot?.job?.state==='paused'?'Stopped before a save':receipt?.receipt?'Saved. Read back. Verified.':'Ready for an authorized task'}</h3><p>{held?latest.detail:active?latest?.detail||snapshot.job.detail:snapshot?.job?.state==='paused'?snapshot.job.detail:receipt?.receipt?'The receipt below comes from the database after the write.':'Review the permission, then let Iris work on this desktop.'}</p></div>{active&&<button className="stop" onClick={()=>void api('runs/'+snapshot.job.id+'/stop',{}).catch(e=>setError(e.message))}><Square size={12}/>Stop task</button>}</div>
      {receipt?.receipt&&<section className="receipt" id="receipt"><div><span className="eyebrow">DATABASE RECEIPT</span><h3>{receipt.receipt.after.fields.name}</h3><span>{receipt.receipt.after.record_id} · v{receipt.receipt.before.version} → v{receipt.receipt.after.version}</span></div><div className="receipt-changes">{Object.entries(receipt.receipt.after.fields).filter(([key,value])=>value!==receipt.receipt.before.fields[key]).map(([key,value])=><div key={key}><span>{key}</span><s>{String(receipt.receipt.before.fields[key])}</s><ArrowRight size={13}/><strong>{String(value)}</strong></div>)}</div><ShieldCheck size={23}/></section>}
      {shownPermission&&<WriteComparison permission={shownPermission} proposed={snapshot?.permission?.id===shownPermission.id?(snapshot?.visual_checks?.[0]?.answer?.record||snapshot?.reader_checks?.at(-1)?.form||snapshot?.guard_checks?.[0]?.form):undefined} saved={receipt?.job?.permission_id===shownPermission.id?receipt?.receipt?.after:undefined}/>}
      <section className="activity-panel"><div className="section-title"><h3><History size={16}/>Attempt & evidence</h3><span>Live tool events, independent reads, gate verdicts</span></div>
        {(snapshot?.visual_checks||[]).map((check:any)=><section className="visual-evidence" key={check.id}><img src={'/api/visual/'+check.id+'/button'} alt="Actual button captured before the click"/><div><span className="eyebrow">PIXEL REVIEW · {check.verdict}</span><p>{check.reason}</p><small>{check.provider} · {check.elapsed_ms} ms · <a href={'/api/visual/'+check.id+'/screen'} target="_blank" rel="noreferrer">Inspect the captured screen</a></small></div></section>)}
        {!snapshot?.events?.length&&<p className="empty-activity">The first attempt will appear here when a task starts.</p>}
        {(snapshot?.guard_checks||[]).map((check:any)=><div className="activity-row" key={'guard'+check.id}><span className="verdict reject">Held before {check.stage==='before_fill'?'typing':'click'}</span><p>{check.reason}<small>{check.form?.resource_type} / {check.form?.record_id} ? {check.code}</small></p><small>Agent attempt</small></div>)}
        {(snapshot?.reader_checks||[]).map((check:any)=><div className="activity-row" key={'reader'+check.id}><span className="event-kind">Blind read</span><p>{check.provider} · {check.model} · {check.outcome}</p><small>{check.elapsed_ms} ms</small></div>)}
        {audit.map((entry:any)=><div className="activity-row" key={'audit'+entry.id}><span className={'verdict '+entry.decision.verdict}>{entry.decision.verdict}</span><p>{entry.decision.reason}</p><small>{entry.proposal.origin==='fault_injection'?'Fault injection':entry.proposal.origin==='agent'?'Agent attempt':'Manual attempt'}</small></div>)}
        {(snapshot?.events||[]).slice(0,8).map((event:any)=><div className="activity-row" key={event.id}><span className="event-kind">{event.action}</span><p>{event.detail}</p></div>)}
      </section>
    </section></main><footer className="app-footer"><span>IRIS · A READABLE PERMISSION. AN ENFORCED WRITE.</span><span>{config?`Meta $${config.meta.committed_usd.toFixed(3)} · Reader $${config.reader.committed_usd.toFixed(3)}`:'Connecting services'}</span></footer>
  </div>;
}
createRoot(document.getElementById('root')!).render(<App/>);
