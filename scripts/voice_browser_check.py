"""Paid full voice pipeline with labeled synthesized microphone input, not human speech."""
import io
import json
import subprocess
import time
import wave
from pathlib import Path
import httpx
from playwright.sync_api import sync_playwright, expect

root=Path(__file__).resolve().parents[1]
base='http://127.0.0.1:8768'
with httpx.Client(base_url=base,timeout=100) as client:
    state=client.get('/api/state').json()
    names={r['fields']['name'] for r in state['records']}
    name=next(n for n in ['Nora Vale','Tara Benton','Mina Corwin','Lena Arden','Nia Rowe'] if n not in names)
    response=client.post('/api/records',json={'resource_type':'booking','name':name,'detail':'Invented studio review','price':194})
    response.raise_for_status();before=response.json()
    sentence=f"Move {name}'s booking to Thursday. Keep the price and every other record unchanged."
    subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(root/'scripts/speech_fixture.ps1'),'-Sentence',sentence],check=True)
    fixture=root/'artifacts/synthetic-speech.wav'
    with wave.open(str(fixture),'rb') as wav:
        rate=wav.getframerate();audio=wav.readframes(wav.getnframes())
    # Give the browser time to lock the snapshot before the first spoken word.
    with wave.open(str(fixture),'wb') as wav:
        wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(rate)
        wav.writeframes(b'\0'*(rate*2*2)+audio+b'\0'*(rate*2))
    duration=3+len(audio)/(rate*2)
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,args=['--use-fake-ui-for-media-stream','--use-fake-device-for-media-stream',f'--use-file-for-fake-audio-capture={fixture}'])
        context=browser.new_context(permissions=['microphone'],viewport={'width':1440,'height':1100})
        page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(base)
        expect(page.locator('#model-status')).to_contain_text('Muse Spark')
        page.locator('#mic').click()
        expect(page.locator('#mic')).to_contain_text('Stop recording',timeout=15000)
        page.wait_for_timeout(int(duration*1000))
        page.locator('#mic').click()
        expect(page.locator('#sentence')).to_have_value(__import__('re').compile(name),timeout=100000)
        transcript=page.locator('#sentence').input_value()
        capture=page.evaluate('voiceCapture')
        assert capture and capture['capture_id']
        page.locator('#interpret').click()
        expect(page.locator('#permission-status')).to_have_text('Permission locked',timeout=100000)
        expect(page.locator('#permission-card')).to_contain_text(before['record_id'])
        page.locator('#run-agent').click()
        expect(page.locator('#permission-status')).to_have_text('Completed',timeout=150000)
        page.screenshot(path=str(root/'artifacts/voice-completed.png'),full_page=True)
        assert not errors,errors
        detail=client.get('/api/desktop').json()
        result=client.get(f"/api/runs/{detail['job']['id']}").json()
        assert result['receipt']['after']['fields']['day']=='Thursday'
        assert result['receipt']['after']['fields']['price']==194 and result['receipt']['after']['version']==2
        trace={'label':'Synthesized speech injected through Chromium microphone test device; real AudioWorklet, Meta transcription, parser, planner, Baseten reader, and database write',
            'fixture_sentence':sentence,'transcript':transcript,'capture_id':capture['capture_id'],'before':before,'result':result}
        (root/'artifacts/voice-browser-check.json').write_text(json.dumps(trace,indent=2),encoding='utf-8')
        print(json.dumps({'transcript':transcript,'job':result['job'],'after':result['receipt']['after'],'trace':'artifacts/voice-browser-check.json'},indent=2))
        browser.close()
