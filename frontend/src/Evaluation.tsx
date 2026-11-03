import {useEffect,useState} from 'react';
import {AlertTriangle,ArrowLeft,Ban,Check,ShieldCheck,Zap} from 'lucide-react';
import {api} from './api';

type Ratio={count:number;total:number;rate:number};
type SystemMetrics={label:string;unauthorized_saves:Ratio;finished_legitimate:Ratio;false_blocks:Ratio;delay_ms:{median:number;p95:number}};
type TaskSystem={outcome:'authorized_save'|'unauthorized_save'|'no_save';saved:boolean;verdict:string;code:string;detail:string;elapsed_ms:number};
type Task={id:string;label:string;kind:string;expect:string;instruction:string;button_text:string;systems:Record<string,TaskSystem>};
type Results={generated_at:string;git_sha?:string;task_count:number;legitimate_count:number;fault_injection_count:number;systems:Record<string,SystemMetrics>;tasks:Task[]};

const ORDER=['agent_alone','button_only','iris'];
const ATTACKS=[
  {id:'t18',title:'Wrong vendor',blurb:'Pay the wrong payee.'},
  {id:'t07',title:'Protected field',blurb:'Zero out the price on the way through.'},
  {id:'t09',title:'Stale version',blurb:'The record moved after the ask.'},
  {id:'t15',title:'Prompt injection',blurb:'Malicious text hidden inside the record.'},
  {id:'t05',title:'Wrong record',blurb:'Right button, wrong booking.'},
];

// Named easing from Second Self DESIGN.md, mapped to CSS. The glyph reacts to the gate verdict.
function IrisGlyph({state}:{state:'calm'|'allow'|'reject'|'pause'}){
  return <span className={`iris-glyph ${state}`} aria-hidden="true">✳</span>;
}

const outcomeChip=(s:TaskSystem)=>{
  if(s.outcome==='unauthorized_save')return <span className="ev-chip danger"><AlertTriangle size={13}/>Saved the wrong write</span>;
  if(s.outcome==='authorized_save')return <span className="ev-chip ok"><Check size={13}/>Saved the authorized change</span>;
  return <span className="ev-chip safe"><Ban size={13}/>Blocked — nothing saved</span>;
};

function Metric({value,label,tone}:{value:string;label:string;tone?:string}){
  return <div className={`ev-metric ${tone||''}`}><strong>{value}</strong><span>{label}</span></div>;
}

export function Evaluation({onBack}:{onBack:()=>void}){
  const [data,setData]=useState<Results|null>(null),[error,setError]=useState('');
  const [attack,setAttack]=useState<Task|null>(null),[running,setRunning]=useState('');
  const [showAll,setShowAll]=useState(false);
  useEffect(()=>{api<Results>('evaluation').then(setData).catch(e=>setError(e.message));},[]);

  async function fire(id:string){
    setRunning(id);setError('');setAttack(null);
    try{setAttack(await api<Task>('evaluation/attack',{task_id:id}));}
    catch(e){setError((e as Error).message);}finally{setRunning('');}
  }

  const glyph=(s?:TaskSystem):'calm'|'allow'|'reject'|'pause'=>
    !s?'calm':s.outcome==='unauthorized_save'?'allow':s.verdict==='pause'?'pause':'reject';

  return <div className="app evaluation">
    <header className="topbar">
      <a href="/" className="wordmark" aria-label="Iris home">iris<span>PERMISSION AT THE WRITE</span></a>
      <div className="topbar-right"><button className="session-button" onClick={onBack}><ArrowLeft size={14}/>Back to the workspace</button></div>
    </header>
    <main className="evaluation-body">
      <section className="intro">
        <span className="eyebrow">HELD-OUT EVALUATION · THREE SYSTEMS, ONE TASK LIST</span>
        <h1>The right button on the wrong record.<br/>Only the gate stops the save.</h1>
        <p>Identical starting records and tasks, scored three ways: an agent with no reviewer, a
        reviewer that only sees the button, and Iris's deterministic write gate.</p>
        {data&&<small className="ev-provenance">Commit {data.git_sha||'local'} · {data.task_count} held-out tasks · {data.legitimate_count} legitimate · {data.fault_injection_count} labeled fault injection · no API key needed</small>}
      </section>

      {error&&<div className="error" role="alert"><span>{error}</span></div>}
      {!data&&!error&&<p className="status" role="status">Loading held-out results…</p>}

      {data&&<div className="ev-headline">
        <span><strong className="danger">{data.systems.agent_alone.unauthorized_saves.count}</strong> unauthorized saves by the unguarded agent</span>
        <span><strong className="danger">{data.systems.button_only.unauthorized_saves.count}</strong> slipped past button-only review</span>
        <span><strong className="safe">{data.systems.iris.unauthorized_saves.count}</strong> past Iris</span>
      </div>}

      {data&&<section className="scoreboard">
        {ORDER.map(name=>{
          const s=data.systems[name],iris=name==='iris';
          return <article key={name} className={`score-card ${iris?'iris':'baseline'}`}>
            <header>{iris?<ShieldCheck size={18}/>:<AlertTriangle size={18}/>}<h2>{s.label}</h2></header>
            <Metric value={`${s.unauthorized_saves.count} / ${s.unauthorized_saves.total}`} label="Unauthorized saves" tone={s.unauthorized_saves.count?'danger':'safe'}/>
            <div className="ev-metric-row">
              <Metric value={`${s.finished_legitimate.count} / ${s.finished_legitimate.total}`} label="Finished legitimate"/>
              <Metric value={`${s.false_blocks.count} / ${s.false_blocks.total}`} label="False blocks" tone={s.false_blocks.count?'danger':''}/>
            </div>
            <p className="ev-delay">Gate delay {s.delay_ms.median} / {s.delay_ms.p95} ms (median / p95)</p>
          </article>;
        })}
      </section>}

      <section className="attack-lab">
        <div className="section-title"><h3><Zap size={16}/>Fire an attack. Watch who saves it.</h3><span>Each runs live on a disposable copy. The owner database is never touched.</span></div>
        <div className="attack-buttons">
          {ATTACKS.map(a=><button key={a.id} className={`attack-btn ${running===a.id?'running':''} ${attack?.id===a.id?'selected':''}`} disabled={!!running} onClick={()=>void fire(a.id)}>
            <strong>{a.title}</strong><small>{a.blurb}</small></button>)}
        </div>
        {attack&&<div className="attack-result">
          <p className="attack-instruction">“{attack.instruction}” <span className="attack-tag">{attack.kind==='fault_injection'?'LABELED FAULT INJECTION':'NATURAL AGENT ERROR'}</span></p>
          <div className="attack-grid">
            {ORDER.map(name=>{
              const s=attack.systems[name];
              return <div key={name} className={`attack-cell ${s.outcome==='unauthorized_save'?'danger':s.outcome==='no_save'?'safe':'ok'}`}>
                <div className="attack-cell-head">{name==='iris'&&<IrisGlyph state={glyph(s)}/>}<span>{data?.systems[name]?.label||name}</span></div>
                {outcomeChip(s)}
                <p>{s.detail}</p>
              </div>;
            })}
          </div>
          <p className="attack-verdict">{attack.systems.iris.outcome==='no_save'
            ? 'Iris held the write. The unguarded agent saved the wrong change on the same task.'
            : 'This task is a legitimate change — every system correctly saved it.'}</p>
        </div>}
      </section>

      {data&&<section className="task-table">
        <button className="session-button" onClick={()=>setShowAll(v=>!v)}>{showAll?'Hide':'Show'} all {data.task_count} held-out tasks</button>
        {showAll&&<div className="comparison-scroll"><table><thead><tr><th>Task</th><th>Kind</th>{ORDER.map(n=><th key={n}>{data.systems[n].label}</th>)}</tr></thead><tbody>
          {data.tasks.map(t=><tr key={t.id}><th>{t.label.replace(/_/g,' ')}<small>{t.id}</small></th><td>{t.kind==='fault_injection'?'fault injection':'natural'}</td>
            {ORDER.map(n=><td key={n} className={t.systems[n].outcome==='unauthorized_save'?'mismatch':t.systems[n].outcome==='no_save'?'matched':''}>{t.systems[n].outcome==='unauthorized_save'?'saved wrong':t.systems[n].outcome==='authorized_save'?'saved ✓':'blocked'}</td>)}
          </tr>)}
        </tbody></table></div>}
      </section>}
    </main>
  </div>;
}
