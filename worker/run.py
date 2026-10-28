"""Run INSIDE a Linux virtual machine. No host desktop APIs, shell tools, or external navigation."""
import asyncio
import os
import platform
import subprocess
from pathlib import Path
import httpx
from playwright.async_api import async_playwright

async def main():
    if platform.system()!='Linux': raise SystemExit('The agent runs only inside a Linux VM, never the Windows host.')
    virtual=subprocess.run(['systemd-detect-virt','--vm'],capture_output=True,text=True)
    if virtual.returncode: raise SystemExit('No supported virtual machine detected. Refusing to start the agent.')
    token=os.environ['IRIS_WORKER_TOKEN']
    base='http://127.0.0.1:8766'  # SSH reverse-forward ONLY the restricted gateway.
    headers={'Authorization':f'Bearer {token}'}
    async with httpx.AsyncClient(base_url=base,headers=headers,timeout=100) as client:
        response=await client.post('/claim');response.raise_for_status();job=response.json()
        if not job: print('No queued permission.');return
        async with async_playwright() as p:
            browser=await p.chromium.launch(headless=False)
            context=await browser.new_context(extra_http_headers=headers,viewport={'width':1280,'height':900},record_video_dir='recordings')
            # Browser cannot navigate to owner services or third-party websites.
            await context.route('**/*',lambda route:route.continue_() if route.request.url.startswith(base+'/') else route.abort())
            page=await context.new_page()
            try:
                await page.goto(base+'/')
                await page.locator('[data-record]').first.wait_for()
                await page.evaluate('(id)=>job=id',job['id'])
                for step in range(12):
                    observation=await page.evaluate('({records,open_form:capture()})')
                    response=await client.post(f"/jobs/{job['id']}/step",json=observation);response.raise_for_status();action=response.json()
                    kind=action.get('action')
                    if kind=='open':
                        id=action['record_id']
                        if id not in [r['record_id'] for r in observation['records']]: raise ValueError('Unknown record selected.')
                        await page.locator('[data-record]').filter(has_text=id).click()
                    elif kind=='fill':
                        field=action['field']
                        if not observation['open_form'] or field not in observation['open_form']['fields']: raise ValueError('Unknown field selected.')
                        await page.get_by_label(field,exact=True).fill(str(action['value']))
                    elif kind=='save':
                        async with page.expect_response(lambda r:'/write' in r.url) as result:
                            await page.get_by_role('button',name='Save',exact=True).click()
                        answer=await (await result.value).json()
                        if answer.get('decision',{}).get('verdict') in ('allow','pause'): break
                    else:
                        await client.post(f"/jobs/{job['id']}/pause");break
                    Path('recordings').mkdir(exist_ok=True)
                    await page.screenshot(path=f'recordings/{job["id"]}-{step}.png')
                else: await client.post(f"/jobs/{job['id']}/pause")
            except Exception:
                await client.post(f"/jobs/{job['id']}/pause")
                raise
            finally:
                await context.close();await browser.close()

asyncio.run(main())
