"""UI acceptance check, not the autonomous agent. Runs against an isolated test DB."""
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
import httpx
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory() as temp:
    env = dict(os.environ, IRIS_DB=str(Path(temp)/'ui.sqlite'), MODEL_API_KEY='')
    server = subprocess.Popen([sys.executable,'-m','uvicorn','iris.api:app','--app-dir','backend','--host','127.0.0.1','--port','8767'],cwd=ROOT,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        for _ in range(40):
            try:
                if httpx.get('http://127.0.0.1:8767/api/state').status_code==200: break
            except httpx.ConnectError: pass
            time.sleep(.25)
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True)
            page=browser.new_page(viewport={'width':1440,'height':1000})
            errors=[]
            page.on('pageerror',lambda error:errors.append(str(error)))
            page.goto('http://127.0.0.1:8767')
            page.locator('#manual-form button').click()
            expect(page.locator('#permission-status')).to_have_text('Permission locked')
            page.locator('[data-record="bk-bob"]').click()
            page.locator('#edit-value').select_option('Thursday')
            page.locator('#editor button[type="submit"]').click()
            expect(page.locator('#receipt')).to_contain_text('REJECT')
            page.locator('[data-record="bk-alice"]').click()
            page.locator('#edit-value').select_option('Thursday')
            page.locator('.danger-zone summary').click()
            page.locator('[data-fault="price"]').click()
            expect(page.locator('#receipt')).to_contain_text('fault_injection')
            page.locator('#edit-value').select_option('Thursday')
            page.locator('#edit-price').press('Enter')
            expect(page.locator('#receipt')).to_contain_text('ALLOW')
            state=httpx.get('http://127.0.0.1:8767/api/state').json()
            assert state['audit'][0]['proposal']['channel']=='enter'
            assert state['audit'][0]['after_row']['version']==2
            assert state['audit'][0]['after_row']['fields']['price']==120
            page.locator('[data-resource="order"]').click()
            page.locator('#add-record').click()
            page.locator('#new-name').fill('Leena Rao')
            page.locator('#new-detail').fill('Paper lamp')
            page.locator('#new-form button[type="submit"]').click()
            page.get_by_text('Leena Rao',exact=True).first.wait_for()
            page.locator('#target').select_option(label=next(x for x in page.locator('#target option').all_text_contents() if 'Leena' in x))
            page.locator('#quantity').fill('4')
            page.locator('#manual-form button').click()
            expect(page.locator('#permission-card')).to_contain_text("Leena Rao's order quantity to 4")
            page.locator('#edit-value').fill('4')
            page.locator('#editor button[type="submit"]').click()
            expect(page.locator('#receipt')).to_contain_text('"quantity":4')
            (ROOT/'artifacts').mkdir(exist_ok=True)
            page.screenshot(path=str(ROOT/'artifacts/verified-desktop.png'),full_page=True)
            page.set_viewport_size({'width':390,'height':844})
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            page.screenshot(path=str(ROOT/'artifacts/verified-mobile.png'),full_page=True)
            assert not errors, errors
            browser.close()
            print('PASS: wrong record, price injection, Enter save, new buyer/order, mobile overflow, browser errors')
    finally:
        server.terminate()
        server.wait(timeout=10)

