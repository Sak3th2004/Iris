import {api} from './api';
export async function startRecording(){
  const stream=await navigator.mediaDevices.getUserMedia({audio:{channelCount:1},video:false});
  const context=new AudioContext({sampleRate:24000});
  let source:MediaStreamAudioSourceNode|undefined,node:AudioWorkletNode|undefined;
  const cleanup=async()=>{source?.disconnect();node?.disconnect();stream.getTracks().forEach(t=>t.stop());await context.close();};
  try{
    await context.resume();await context.audioWorklet.addModule('/static/voice-worklet.js');
    const capture=await api('voice/start',{}),chunks:Float32Array[]=[];
    source=context.createMediaStreamSource(stream);node=new AudioWorkletNode(context,'iris-capture');
    node.port.onmessage=e=>chunks.push(e.data);
    const gain=context.createGain();gain.gain.value=0;source.connect(node);node.connect(gain);gain.connect(context.destination);
    return {cancel:cleanup,stop:async()=>{
      const rate=context.sampleRate;await cleanup();
      const raw=new Float32Array(chunks.reduce((n,c)=>n+c.length,0));let offset=0;
      for(const chunk of chunks){raw.set(chunk,offset);offset+=chunk.length;}
      const count=Math.floor(raw.length*24000/rate),buffer=new ArrayBuffer(44+count*2),view=new DataView(buffer);
      const text=(p:number,s:string)=>Array.from(s).forEach((c,i)=>view.setUint8(p+i,c.charCodeAt(0)));
      text(0,'RIFF');view.setUint32(4,36+count*2,true);text(8,'WAVE');text(12,'fmt ');view.setUint32(16,16,true);view.setUint16(20,1,true);view.setUint16(22,1,true);view.setUint32(24,24000,true);view.setUint32(28,48000,true);view.setUint16(32,2,true);view.setUint16(34,16,true);text(36,'data');view.setUint32(40,count*2,true);
      for(let i=0;i<count;i++){const p=i*rate/24000,j=Math.floor(p),f=p-j;const sample=raw[j]*(1-f)+raw[Math.min(j+1,raw.length-1)]*f;view.setInt16(44+2*i,Math.max(-1,Math.min(1,sample))*32767,true);}
      const response=await fetch('/api/voice',{method:'POST',headers:{'X-Iris-Capture-ID':capture.capture_id,'Content-Type':'audio/wav'},body:buffer});const data=await response.json();if(!response.ok)throw new Error(data.detail);return data;
    }};
  }catch(error){await cleanup();throw error;}
}
