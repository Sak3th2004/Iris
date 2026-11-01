import {useCallback,useEffect,useRef} from 'react';

// Every playback settles, including a mute, interruption, failed fetch or unmount.
export function useSpeech(enabled:boolean,onError:(message:string)=>void){
  const allowed=useRef(enabled),report=useRef(onError);
  allowed.current=enabled;report.current=onError;
  const current=useRef<{abort:AbortController;player?:HTMLAudioElement;url?:string;finish:(played:boolean)=>void}|null>(null);
  const cancel=useCallback(()=>{
    const playback=current.current;if(!playback)return;
    current.current=null;playback.abort.abort();playback.player?.pause();
    if(playback.url)URL.revokeObjectURL(playback.url);
    playback.finish(false);
  },[]);
  const speak=useCallback(async(text:string):Promise<boolean>=>{
    cancel();if(!allowed.current)return false;
    return new Promise<boolean>(resolve=>{
      const playback:{abort:AbortController;player?:HTMLAudioElement;url?:string;finish:(played:boolean)=>void}={abort:new AbortController(),finish:resolve};
      current.current=playback;
      const finish=(played:boolean)=>{
        if(current.current===playback)current.current=null;
        if(playback.url)URL.revokeObjectURL(playback.url);
        resolve(played);
      };
      void (async()=>{
        try{
          const response=await fetch('/api/speech',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text}),signal:playback.abort.signal});
          if(!response.ok)throw new Error((await response.json()).detail);
          const blob=await response.blob();
          if(current.current!==playback||!allowed.current){finish(false);return;}
          playback.url=URL.createObjectURL(blob);playback.player=new Audio(playback.url);
          playback.player.onended=()=>finish(true);playback.player.onerror=()=>finish(false);
          await playback.player.play();
        }catch(e){
          if(!playback.abort.signal.aborted)report.current((e as Error).message+' Text remains available.');
          finish(false);
        }
      })();
    });
  },[cancel]);
  useEffect(()=>{if(!enabled)cancel();},[enabled,cancel]);
  useEffect(()=>cancel,[cancel]);
  return {speak,cancel};
}
