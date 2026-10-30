"""Measure actual cursor-to-canvas updates; includes local Docker command overhead."""
import json
import statistics
import subprocess
import time
from pathlib import Path

import httpx
from playwright.sync_api import sync_playwright, expect

base='http://127.0.0.1:8768'
state=httpx.get(base+'/api/desktop').json()
assert not state['job'] or state['job']['state'] not in ('queued','running'), 'Do not move the pointer during an agent task.'
def docker(*args):
    return subprocess.run(['docker','compose','exec','-T','browser','xdotool',*args],check=True,capture_output=True,text=True).stdout
position=dict(line.split('=',1) for line in docker('getmouselocation','--shell').splitlines())
hash_pixels="""() => {
  const pixels=document.querySelector('.desktop-canvas canvas').getContext('2d').getImageData(10,910,210,80).data;
  let hash=2166136261;for(const value of pixels)hash=Math.imul(hash^value,16777619);return hash;
}"""
times=[]
try:
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        page=browser.new_page(viewport={'width':1440,'height':1050})
        page.goto(base)
        expect(page.locator('.stream-state')).to_have_text('Live',timeout=15000)
        expect(page.locator('.desktop-footer')).to_contain_text('1600',timeout=10000)
        docker('mousemove','30','950')
        page.wait_for_timeout(500)
        for x in (170,40,150):
            before=page.evaluate(hash_pixels)
            started=time.perf_counter()
            docker('mousemove',str(x),'950')
            page.wait_for_function('(previous)=>('+hash_pixels+')()!==previous',arg=before,timeout=4000)
            times.append(round((time.perf_counter()-started)*1000))
        browser.close()
finally:
    docker('mousemove',position['X'],position['Y'])
result={'label':'Actual Linux cursor movement to noVNC canvas update, including Docker command overhead; three local samples, not a network benchmark','milliseconds':times,'median_ms':statistics.median(times)}
Path('artifacts/desktop-stream-timing.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result))
