"""Live local workspace check. Uses invented records and real paid model calls."""
import json
import time
from pathlib import Path
from uuid import uuid4

import httpx
from playwright.sync_api import sync_playwright, expect

base = 'http://127.0.0.1:8768'
artifacts = Path('artifacts')
artifacts.mkdir(exist_ok=True)
with httpx.Client(base_url=base, timeout=100) as client, sync_playwright() as p:
    assert client.get('/api/desktop').json()['connected'], 'Desktop worker is not ready.'
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={'width': 1600, 'height': 1150})
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto(base)
    expect(page.locator('.stream-state')).to_have_text('Live', timeout=30000)
    expect(page.locator('.desktop-footer')).to_contain_text('1600', timeout=10000)
    page.screenshot(path=str(artifacts/'workspace-ready.png'), full_page=True)
    results = []
    for resource, field, value in [('booking', 'day', 'Saturday'), ('order', 'quantity', 4)]:
        name = 'Iris Test ' + uuid4().hex[:7]
        response = client.post('/api/records', json={'resource_type': resource, 'name': name, 'detail': 'Invented review' if resource == 'booking' else 'Ceramic cup', 'price': 173})
        response.raise_for_status()
        before = response.json()
        sentence = f"Set {name}'s {resource} {field} to {value}. Keep the price and every other field and record unchanged."
        page.locator('#sentence').fill(sentence)
        page.locator('#interpret').click()
        expect(page.locator('#permission-status')).to_have_text('Ready for review', timeout=100000)
        expect(page.get_by_label('Permission card')).to_contain_text(before['record_id'])
        expect(page.get_by_label('Permission card')).to_contain_text('173')
        page.locator('#run-agent').click()
        expect(page.locator('.desktop-shell')).to_have_class('desktop-shell working', timeout=15000)
        if resource == 'booking':
            page.close()  # The agent must finish after the owner leaves.
        for _ in range(180):
            status = client.get('/api/desktop').json()
            if status['job']['state'] not in ('queued', 'running'):
                break
            time.sleep(1)
        else:
            client.post(f"/api/runs/{status['job']['id']}/stop", json={})
            raise AssertionError('Stopped timed-out test task.')
        detail = client.get(f"/api/runs/{status['job']['id']}").json()
        (artifacts/f"workspace-run-{status['job']['id']}.json").write_text(json.dumps({'before':before,'result':detail},indent=2),encoding='utf-8')
        assert status['job']['state'] == 'complete', status['job']
        after = detail['receipt']['after']
        assert after['fields'][field] == value and after['fields']['price'] == 173
        assert after['version'] == before['version'] + 1
        assert detail['reader_checks'][-1]['provider'] == 'Baseten'
        assert detail['visual_checks'][0]['verdict'] == 'allow'
        assert detail['visual_checks'][0]['provider'] == 'Baseten'
        if resource == 'booking':
            page = browser.new_page(viewport={'width': 1600, 'height': 1150})
            page.on('pageerror', lambda e: errors.append(str(e)))
            page.goto(base)
        expect(page.locator('#permission-status')).to_have_text('Allowed & verified', timeout=15000)
        expect(page.locator('#receipt')).to_contain_text(name)
        expect(page.locator('.stream-state')).to_have_text('Live', timeout=15000)
        page.screenshot(path=str(artifacts/f'workspace-{resource}.png'), full_page=True)
        results.append({'before': before, 'result': detail})
    page.get_by_role('button', name='Reconnect desktop').click()
    expect(page.locator('.stream-state')).to_have_text('Live', timeout=15000)
    page.set_viewport_size({'width': 390, 'height': 844})
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    page.screenshot(path=str(artifacts/'workspace-mobile.png'), full_page=True)
    assert not errors, errors
    browser.close()
    (artifacts/'workspace-check.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
    print(json.dumps({'passed': ['live desktop', 'booking while owner away', 'store order', 'Baseten blind reads', 'database read-back', 'reconnect', 'mobile layout'], 'jobs': [r['result']['job']['id'] for r in results]}))
