"""Persistent browser worker inside the dedicated Linux container only."""
import asyncio
import base64
import contextlib
import os
import platform
import signal
import subprocess
from uuid import uuid4
from pathlib import Path
import httpx
from playwright.async_api import async_playwright

async def main(runtime='docker'):
    if platform.system() == 'Linux':
        asyncio.get_running_loop().add_signal_handler(signal.SIGTERM,asyncio.current_task().cancel)
    if platform.system() != 'Linux':
        raise SystemExit('The worker must run inside Linux isolation, never the Windows host.')
    if runtime == 'docker':
        if not Path('/.dockerenv').exists(): raise SystemExit('Run inside the dedicated Iris Docker container.')
        base = 'http://gateway:8766'
    elif runtime == 'vm':
        if subprocess.run(['systemd-detect-virt','--vm'],capture_output=True).returncode:
            raise SystemExit('No supported Linux virtual machine detected.')
        base = 'http://127.0.0.1:8766'
    else: raise SystemExit('Unsupported worker runtime.')
    # This volume belongs exclusively to Iris. Hold a process lock before clearing
    # Chromium's stale cross-container symlinks; never follow or touch their targets.
    import fcntl
    profile=Path('/home/pwuser/iris-profile')
    profile.mkdir(parents=True,exist_ok=True)
    profile_lock=(profile/'.iris-worker.lock').open('a')
    fcntl.flock(profile_lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    for name in ('SingletonLock','SingletonSocket','SingletonCookie'):
        stale=profile/name
        if stale.is_symlink(): stale.unlink()
    headers = {'Authorization':f"Bearer {os.environ['IRIS_WORKER_TOKEN']}",'X-Iris-Worker-ID':str(uuid4())}
    async with httpx.AsyncClient(base_url=base,headers=headers,timeout=100) as client:
        async with async_playwright() as p:
            context = await p.chromium.launch_persistent_context(str(profile),headless=False,extra_http_headers=headers,no_viewport=True,timeout=30000,args=['--window-size=1480,880','--window-position=60,55','--no-first-run','--password-store=basic','--hide-crash-restore-bubble'])
            browser = context.browser
            async def restrict(route):
                if route.request.url.startswith(base+'/'): await route.continue_()
                else: await route.abort()
            await context.route('**/*',restrict)
            page = context.pages[0] if context.pages else await context.new_page()
            for attempt in range(30):
                try:
                    response=await client.get('/records',timeout=5)
                    response.raise_for_status()
                    break
                except httpx.HTTPError: await asyncio.sleep(2)
            else: raise RuntimeError('Gateway did not become ready.')
            await page.goto(base+'/')
            await page.locator('[data-record]').first.wait_for()
            async def frames():
                while True:
                    try:
                        frame = await page.screenshot(type='jpeg',quality=85)
                        response = await client.post('/desktop/frame',content=frame,headers={'Content-Type':'image/jpeg'},timeout=8)
                        response.raise_for_status()
                    except Exception as exc: print(f'Frame delivery interrupted: {type(exc).__name__}',flush=True)
                    await asyncio.sleep(2)
            async def event(id,action,detail):
                response = await client.post(f'/jobs/{id}/events',json={'action':action,'detail':str(detail)[:300]})
                response.raise_for_status()
            async def heartbeat(id,lost):
                while True:
                    try:
                        response=await client.post(f'/jobs/{id}/heartbeat',timeout=5)
                        response.raise_for_status()
                    except httpx.HTTPError:
                        lost.set()
                        return  # Never resume an uncertain task on reconnection.
                    await asyncio.sleep(3)
            async def aim(locator):
                await page.evaluate("document.querySelectorAll('[data-iris-active]').forEach(el=>el.removeAttribute('data-iris-active'))")
                await locator.evaluate("el=>el.setAttribute('data-iris-active','true')")
                await locator.scroll_into_view_if_needed()
                box = await locator.bounding_box()
                chrome = await page.evaluate('({x:screenX,y:screenY,top:outerHeight-innerHeight})')
                target_x=round(chrome['x']+box['x']+box['width']/2)
                target_y=round(chrome['y']+chrome['top']+box['y']+box['height']/2)
                position=await asyncio.create_subprocess_exec('xdotool','getmouselocation','--shell',stdout=asyncio.subprocess.PIPE)
                output,_=await position.communicate()
                coordinates=dict(line.split('=',1) for line in output.decode().splitlines() if '=' in line)
                start_x,start_y=int(coordinates.get('X',0)),int(coordinates.get('Y',0))
                for i in range(1,17):
                    t=1-(1-i/16)**3
                    move=await asyncio.create_subprocess_exec('xdotool','mousemove',str(round(start_x+(target_x-start_x)*t)),str(round(start_y+(target_y-start_y)*t)))
                    await move.wait();await asyncio.sleep(.015)
                await page.mouse.move(box['x']+box['width']/2,box['y']+box['height']/2)
            async def click(locator):
                await aim(locator)
                await locator.click()
            stream = asyncio.create_task(frames())
            print('Isolated browser ready; streaming real frames. Waiting for permission.',flush=True)
            try:
                while True:
                    try:
                        response = await client.post('/claim',timeout=5); response.raise_for_status(); job = response.json()
                    except httpx.HTTPError:
                        await asyncio.sleep(2); continue  # Polling is safe; model/write requests are never retried.
                    if not job:
                        await asyncio.sleep(1); continue
                    id = job['id']
                    lost=asyncio.Event()
                    pulse=asyncio.create_task(heartbeat(id,lost))
                    try:
                        await page.reload()
                        await page.locator('[data-record]').first.wait_for()
                        await page.evaluate('(id)=>job=id',id)
                        for step in range(12):
                            if lost.is_set(): raise ValueError('Worker connection lost.')
                            status = await client.get(f'/jobs/{id}'); status.raise_for_status()
                            if status.json()['state'] != 'running': break
                            observation = await page.evaluate('({records,open_form:capture()})')
                            await event(id,'observing','Reading the current browser form.')
                            response = await client.post(f'/jobs/{id}/step',json=observation);response.raise_for_status();action=response.json()
                            if lost.is_set(): raise ValueError('Worker connection lost during model call.')
                            status = await client.get(f'/jobs/{id}');status.raise_for_status()
                            if status.json()['state'] != 'running': break
                            kind = action.get('action')
                            if kind == 'open':
                                record = action['record_id']
                                if record not in [r['record_id'] for r in observation['records']]: raise ValueError('Unknown record selected.')
                                resource = next(r['resource_type'] for r in observation['records'] if r['record_id']==record)
                                tab = page.locator(f'[data-desk="{resource}"]')
                                if await tab.get_attribute('aria-pressed') != 'true':
                                    await click(tab)
                                    await event(id,'desk',f'Switched to the {resource} desk.')
                                await click(page.locator('[data-record]').filter(has_text=record))
                                await event(id,'opened',f'Opened record {record}.')
                            elif kind == 'fill':
                                field = action['field']
                                if not observation['open_form'] or field not in observation['open_form']['fields']: raise ValueError('Unknown field selected.')
                                locator = page.get_by_label(field,exact=True)
                                await click(locator)
                                await locator.fill(str(action['value']))
                                await event(id,'filled',f'Set {field} to {action["value"]}.')
                            elif kind == 'save':
                                button=page.get_by_role('button',name='Save',exact=True)
                                await aim(button)
                                await event(id,'visual review','Pointer paused at Save. Spark Open is reading the screen pixels and button before any click.')
                                captured=await page.evaluate('capture()')
                                screen=await page.screenshot(type='jpeg',quality=90)
                                crop=await button.screenshot(type='jpeg',quality=95)
                                response=await client.post(f'/jobs/{id}/preflight',json={'form':captured,'screen':base64.b64encode(screen).decode(),'button':base64.b64encode(crop).decode()})
                                response.raise_for_status();review=response.json()
                                await event(id,'visual '+review['verdict'],review['reason'])
                                if review['verdict']!='allow': break
                                if lost.is_set() or await page.evaluate('capture()')!=captured:
                                    raise ValueError('The form changed during visual review.')
                                status=await client.get(f'/jobs/{id}');status.raise_for_status()
                                if status.json()['state']!='running': break
                                await event(id,'reviewing','Independent reader is inspecting the form before the write gate.')
                                async with page.expect_response(lambda r:'/write' in r.url,timeout=100000) as result:
                                    await button.click()
                                answer = await (await result.value).json()
                                verdict = answer.get('decision',{})
                                await event(id,verdict.get('verdict','error'),verdict.get('reason',answer.get('detail','Write failed.')))
                                if verdict.get('verdict') in ('allow','pause'): break
                            else:
                                await event(id,'paused',action.get('question','Agent needs clarification.'))
                                await client.post(f'/jobs/{id}/pause');break
                        else: await client.post(f'/jobs/{id}/pause')
                    except Exception as exc:
                        print(f'Task stopped: {type(exc).__name__}',flush=True)
                        with contextlib.suppress(httpx.HTTPError):
                            await event(id,'error',f'{type(exc).__name__}: worker stopped; no automatic model retry.')
                            await client.post(f'/jobs/{id}/pause',timeout=5)
                    finally:
                        pulse.cancel()
                        with contextlib.suppress(asyncio.CancelledError): await pulse
            finally:
                stream.cancel()
                with contextlib.suppress(asyncio.CancelledError): await stream
                await context.close();await browser.close()

if __name__ == '__main__': asyncio.run(main())
