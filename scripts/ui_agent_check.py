"""Paid live UI check: instruct, review, start, leave, return to database receipt."""
import json
import time
from pathlib import Path
from uuid import uuid4
import httpx
from playwright.sync_api import sync_playwright, expect

base='http://127.0.0.1:8768'
with httpx.Client(base_url=base,timeout=100) as client:
    assert client.get('/api/desktop').json()['connected']
    name='Nila '+uuid4().hex[:6]
    response=client.post('/api/records',json={'resource_type':'booking','name':name,'detail':'Architecture review','price':163})
    response.raise_for_status();row=response.json()
    Path('artifacts').mkdir(exist_ok=True)
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        page=browser.new_page(viewport={'width':1600,'height':1100})
        errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(base)
        page.locator('#sentence').fill(f"Move {name}'s booking to Friday. Keep the price and all other records unchanged.")
        page.locator('#interpret').click()
        expect(page.locator('#permission-status')).to_have_text('Permission locked',timeout=100000)
        expect(page.locator('#run-agent')).to_be_enabled()
        page.locator('#run-agent').click()
        expect(page.locator('.desk-panel')).to_have_class('desk-panel is-working',timeout=15000)
        page.screenshot(path='artifacts/task-running.png',full_page=True)
        job=client.get('/api/desktop').json()['job']
        page.close()  # The worker must finish without an owner browser connection.
        for _ in range(180):
            status=client.get('/api/desktop').json()
            if status['job']['state'] not in ('queued','running'): break
            time.sleep(1)
        else:
            client.post(f"/api/runs/{job['id']}/stop",json={})
            raise RuntimeError('Stopped timed-out live UI task.')
        assert status['job']['state']=='complete',status
        page=browser.new_page(viewport={'width':1600,'height':1100})
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(base)
        expect(page.locator('#permission-status')).to_have_text('Completed',timeout=15000)
        expect(page.locator('#activity-message')).to_contain_text('database confirms')
        expect(page.locator('#receipt')).to_contain_text('Friday')
        page.screenshot(path='artifacts/task-returned.png',full_page=True)
        page.locator('#show-readiness').click()
        expect(page.locator('#readiness-dialog')).to_be_visible()
        page.keyboard.press('Escape')
        page.set_viewport_size({'width':390,'height':844})
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        page.screenshot(path='artifacts/task-mobile.png',full_page=True)
        assert not errors,errors
        browser.close()
    state=client.get('/api/state').json()
    final=next(r for r in state['records'] if r['record_id']==row['record_id'])
    assert final['fields']['day']=='Friday' and final['fields']['price']==163 and final['version']==2
    trace={'test':'Live UI: describe, lock, start, close page, return','before':row,'after':final,'job':status['job'],'events':status['events'],'meta':state['meta']}
    Path('artifacts/ui-away-return.json').write_text(json.dumps(trace,indent=2),encoding='utf-8')
    print(json.dumps(trace,indent=2))
