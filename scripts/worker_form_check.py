"""Local form-rendering regression; fixtures only, no model calls or writes."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

root=Path(__file__).resolve().parents[1]
row={'resource_type':'booking','record_id':'fixture-long-record','version':1,'fields':{
    'name':'Invented guest with a deliberately long name for pixel readability validation',
    'day':'Thursday','time':'14:30','price':173,
    'service':'A deliberately long service description that must remain completely visible to the independent reader.',
    'starts_at':'2030-02-07T14:30:00+05:30','host':'Studio','status':'confirmed','duration_minutes':60}}
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    page=browser.new_page(viewport={'width':1480,'height':880});errors=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.route('**/records',lambda r:r.fulfill(content_type='application/json',body=json.dumps([row])))
    page.route('**/fixture',lambda r:r.fulfill(content_type='text/html',body=(root/'web/worker.html').read_text(encoding='utf-8')))
    page.goto('http://127.0.0.1:8768/fixture')
    page.locator('#records [data-record]').click()
    expect(page.get_by_label('name',exact=True)).to_have_value(row['fields']['name'])
    assert page.evaluate('capture()')==row
    assert page.locator('#form textarea').evaluate_all('(els)=>els.every(el=>el.scrollHeight<=el.clientHeight+2 && el.scrollWidth<=el.clientWidth+2)')
    changed='An even longer replacement service description. '+row['fields']['service']
    page.get_by_label('service',exact=True).fill(changed)
    assert page.locator('#form textarea').evaluate_all('(els)=>els.every(el=>el.scrollHeight<=el.clientHeight+2)')
    assert page.evaluate('capture().fields.service')==changed
    page.locator('#inspector').screenshot(path=str(root/'artifacts/long-form-fixture.png'))
    assert page.locator('#form textarea').evaluate_all('(els)=>els.every(el=>el.scrollHeight<=el.clientHeight+2)'), 'Screenshot must not clip values after layout settles.'
    assert not errors,errors
    browser.close()
print('PASS: long values remain visible, editable, and identical in the captured form; fixture only.')
