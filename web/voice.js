/* Speech remains bound to the server snapshot taken before sample collection. */
let recorder=null, voiceBusy=false;
const voiceNote=document.createElement('p');
voiceNote.className='helper';voiceNote.hidden=true;voiceNote.setAttribute('role','status');
$('#sentence').after(voiceNote);
function showVoiceSource(){
  voiceNote.replaceChildren();voiceNote.hidden=!voiceCapture;
  if(!voiceCapture)return;
  voiceNote.append('Speech snapshot locked before recording. Transcript edits keep that same snapshot. ');
  const reset=document.createElement('button');reset.type='button';reset.className='text-button';reset.textContent='Use as a new typed instruction';
  reset.onclick=()=>{voiceCapture=null;showVoiceSource();$('#sentence').dispatchEvent(new Event('input',{bubbles:true}));};
  voiceNote.append(reset);
}
window.addEventListener('iris:voice-source',showVoiceSource);

function encodeVoice(chunks,rate){
  const length=chunks.reduce((n,c)=>n+c.length,0),samples=new Float32Array(length);
  let offset=0;for(const chunk of chunks){samples.set(chunk,offset);offset+=chunk.length;}
  const count=Math.floor(length*24000/rate),buffer=new ArrayBuffer(44+count*2),v=new DataView(buffer);
  const str=(off,s)=>[...s].forEach((c,i)=>v.setUint8(off+i,c.charCodeAt(0)));
  str(0,'RIFF');v.setUint32(4,36+count*2,true);str(8,'WAVE');str(12,'fmt ');v.setUint32(16,16,true);
  v.setUint16(20,1,true);v.setUint16(22,1,true);v.setUint32(24,24000,true);v.setUint32(28,48000,true);
  v.setUint16(32,2,true);v.setUint16(34,16,true);str(36,'data');v.setUint32(40,count*2,true);
  for(let i=0;i<count;i++){
    const position=i*rate/24000,lo=Math.floor(position),mix=position-lo;
    const sample=samples[lo]*(1-mix)+samples[Math.min(lo+1,length-1)]*mix;
    v.setInt16(44+i*2,Math.max(-1,Math.min(1,sample))*32767,true);
  }
  return buffer;
}

async function releaseVoice(r){
  clearTimeout(r.timer);r.source?.disconnect();r.node?.disconnect();
  r.stream?.getTracks().forEach(t=>t.stop());
  if(r.context&&r.context.state!=='closed')await r.context.close();
}
$('#mic').onclick=async()=>{
  if(voiceBusy)return;
  voiceBusy=true;$('#mic').disabled=true;
  try{
    if(recorder){
      const r=recorder;recorder=null;
      await releaseVoice(r);$('#mic').textContent='Transcribing…';
      const res=await fetch('/api/voice',{method:'POST',headers:{'Content-Type':'audio/wav','X-Iris-Capture-ID':r.capture.capture_id},body:encodeVoice(r.chunks,r.context.sampleRate)});
      const result=await res.json();if(!res.ok)throw new Error(result.detail);
      voiceCapture=result;$('#sentence').value=result.sentence;
      $('#sentence').dispatchEvent(new Event('input',{bubbles:true}));showVoiceSource();
      toast('Transcript ready. Review it; permission will use the recording-start versions.');
      await refresh();
    }else{
      if(!state?.meta.configured)throw new Error('Connect MODEL_API_KEY to use Muse Voice Transcribe.');
      const r={chunks:[]};
      try{
        r.stream=await navigator.mediaDevices.getUserMedia({audio:{channelCount:1},video:false});
        r.context=new AudioContext({sampleRate:24000});await r.context.resume();
        await r.context.audioWorklet.addModule('/static/voice-worklet.js');
        r.capture=await api('voice/start',{});
        r.source=r.context.createMediaStreamSource(r.stream);
        r.node=new AudioWorkletNode(r.context,'iris-capture');
        r.node.port.onmessage=e=>r.chunks.push(e.data);
        const silence=r.context.createGain();silence.gain.value=0;
        r.source.connect(r.node);r.node.connect(silence);silence.connect(r.context.destination);
        recorder=r;voiceCapture=null;showVoiceSource();
        $('#sentence').dispatchEvent(new Event('input',{bubbles:true}));
        $('#mic').textContent='■ Stop recording';r.timer=setTimeout(()=>$('#mic').click(),55000);
      }catch(e){await releaseVoice(r);throw e;}
    }
  }catch(e){toast(e.message);}
  finally{
    voiceBusy=false;$('#mic').disabled=false;
    if(!recorder)$('#mic').innerHTML='◉ <span>Speak</span>';
  }
};
window.addEventListener('pagehide',()=>{if(recorder){void releaseVoice(recorder);recorder=null;}});
