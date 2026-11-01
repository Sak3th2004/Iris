"""Browser regression with labeled API fixtures; no model spend or real writes."""
import json
from playwright.sync_api import sync_playwright, expect

base='http://127.0.0.1:8768'
permission={'id':'fixture-permission','sentence':'Move fixture guest to Thursday; keep price.',
    'resource_type':'booking','record_id':'fixture-record','set_fields':{'day':'Thursday'},
    'preserve_fields':{'price':120},'forbidden_operations':['cancel'],'version':1}
state={'audit':[],'meta':{'configured':True,'committed_usd':0},'reader':{'configured':True,'committed_usd':0},'speech':{'configured':True}}
calls={'captures':[],'transcriptions':0,'interpretations':0,'runs':0,'speech':0}

def route_api(route):
    path=route.request.url.split('/api/')[1]
    result={}
    if path=='desktop': result={'connected':True,'job':None,'events':[]}
    elif path=='state': result=state
    elif path=='voice/start':
        calls['captures'].append(route.request.post_data_json)
        result={'capture_id':f'fixture-{len(calls["captures"])}'}
    elif path=='voice':
        calls['transcriptions']+=1
        result={'sentence':'Move fixture guest.' if calls['transcriptions']==1 else 'Thursday, please.','capture_id':f'fixture-{calls["transcriptions"]}'}
    elif path=='permissions/interpret':
        calls['interpretations']+=1
        result={'question':'Which weekday?'} if calls['interpretations']==1 else {'permission':permission}
    elif path=='speech':
        calls['speech']+=1
        route.fulfill(status=200,content_type='audio/mpeg',body=b'fixture audio; playback is stubbed');return
    elif path=='runs': calls['runs']+=1
    else: raise AssertionError('Unexpected API call: '+path)
    route.fulfill(status=200,content_type='application/json',body=json.dumps(result))

with sync_playwright() as p:
    browser=p.chromium.launch(headless=True,args=['--use-fake-ui-for-media-stream','--use-fake-device-for-media-stream'])
    context=browser.new_context(permissions=['microphone'])
    context.add_init_script('''window.Audio=class {play(){window.fixturePlaybackStarted=true;return Promise.resolve()}pause(){window.fixturePlaybackPaused=true}};''')
    context.route('**/api/**',route_api)
    page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto(base)
    page.get_by_role('button',name='Speak your instruction').click()
    expect(page.get_by_role('button',name='Finish recording')).to_be_visible()
    page.wait_for_timeout(1800)
    assert calls['transcriptions']==0, 'A pause must not submit speech.'
    page.get_by_role('button',name='Finish recording').click()
    expect(page.locator('.ask-state')).to_contain_text('Which weekday?')
    page.wait_for_function('window.fixturePlaybackStarted===true')
    page.get_by_role('button',name='Mute spoken feedback').click()
    page.wait_for_timeout(250)
    assert page.evaluate('window.fixturePlaybackPaused===true')
    assert len(calls['captures'])==1, 'Muting a question must not reopen the microphone.'
    page.get_by_role('button',name='Speak your instruction').click()
    expect(page.get_by_role('button',name='Finish recording')).to_be_visible()
    page.get_by_role('button',name='Finish recording').click()
    expect(page.locator('#permission-status')).to_have_text('Ready for review')
    assert calls['captures'][1]['parent_capture_id']=='fixture-1'
    assert calls['speech']==1, 'Muted feedback must not call speech synthesis.'
    assert calls['runs']==0, 'A spoken instruction must wait for explicit authorization.'
    page.locator('#run-agent').click()
    page.wait_for_timeout(250)
    assert calls['runs']==1
    assert not errors,errors
    browser.close()
print(json.dumps({'label':'API-fixture voice-control regression','passed':True,'calls':calls}))
