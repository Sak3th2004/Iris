import {memo,useEffect,useRef,useState} from 'react';
import {Maximize2,Monitor,RefreshCw,Wifi} from 'lucide-react';
import RFB from '@novnc/novnc';

export const Desktop=memo(function Desktop({working,held,pulse}:{working:boolean;held:boolean;pulse:number}){
  const target=useRef<HTMLDivElement>(null),shell=useRef<HTMLElement>(null);
  const [connected,setConnected]=useState(false),[generation,setGeneration]=useState(0),[size,setSize]=useState('');
  useEffect(()=>{
    let disposed=false,timer:ReturnType<typeof setTimeout>;
    const rfb=new RFB(target.current!,`${location.protocol==='https:'?'wss':'ws'}://${location.host}/api/desktop/stream`);
    rfb.viewOnly=true;rfb.scaleViewport=true;rfb.resizeSession=false;rfb.qualityLevel=9;rfb.compressionLevel=2;rfb.showDotCursor=false;
    rfb.addEventListener('connect',()=>{setConnected(true);timer=setTimeout(()=>{if(!disposed){const image=rfb.getImageData();setSize(`${image.width} × ${image.height}`);}},1000);});
    rfb.addEventListener('disconnect',()=>{setConnected(false);if(!disposed)timer=setTimeout(()=>setGeneration(n=>n+1),2500);});
    return()=>{disposed=true;clearTimeout(timer);rfb.disconnect();};
  },[generation]);
  return <section className={`desktop-shell ${working?'working':''}`} ref={shell}>
    <header className="desktop-bar"><div className="desktop-title"><Monitor size={16}/><span>The other machine</span><span className="profile-tag">Not your Windows profile</span></div><div className="desktop-actions"><span className={`stream-state ${connected?'connected':''}`}><Wifi size={13}/>{connected?'Live':'Connecting'}</span><button title="Reconnect desktop" aria-label="Reconnect desktop" onClick={()=>setGeneration(n=>n+1)}><RefreshCw size={15}/></button><button title="Expand desktop" aria-label="Expand desktop" onClick={()=>{void shell.current?.requestFullscreen();}}><Maximize2 size={15}/></button></div></header>
    <div className="desktop-stage"><div className="desktop-canvas" ref={target}/>{working&&<span key={pulse} className={`control-glow ${held?'held':''}`} aria-hidden="true"/>}{held&&<p className="held-caption">Click held. This is not the authorized change.</p>}</div>
    {!connected&&<div className="desktop-connecting"><Monitor size={32}/><h3>Connecting to your second workspace</h3><p>The desktop keeps running independently of this page.</p></div>}
    <footer className="desktop-footer"><span><i className={connected?'green-dot':'grey-dot'}/>{connected?'Direct desktop stream':'Waiting for desktop'}</span><span>{size} · View only · Separate browser profile</span></footer>
  </section>;
});
