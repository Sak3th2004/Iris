import time
import pytest
from fastapi.testclient import TestClient
from iris.api import create_app
from iris.capture import Captures
from iris.meta import Meta
from iris.models import Proposal


def setup(tmp_path,monkeypatch):
    app=create_app(tmp_path/'speech.sqlite')
    client=TestClient(app)
    async def transcribe(self,audio): return 'Move Alice to Thursday. Keep the price.'
    async def parse(self,system,data,purpose):
        assert purpose=='permission'
        assert next(r for r in data['records'] if r['record_id']=='bk-alice')['version']==1
        return {'resource_type':'booking','record_id':'bk-alice','set_fields':{'day':'Thursday'}}
    monkeypatch.setattr(Meta,'transcribe',transcribe)
    monkeypatch.setattr(Meta,'json',parse)
    return client,app.state.store


def speak(client):
    capture=client.post('/api/voice/start',json={}).json()
    response=client.post('/api/voice',headers={'X-Iris-Capture-ID':capture['capture_id']},content=b'test provider fixture')
    assert response.status_code==200
    return response.json()


def test_spoken_snapshot_is_single_use(tmp_path,monkeypatch):
    client,store=setup(tmp_path,monkeypatch)
    spoken=speak(client)
    response=client.post('/api/permissions/interpret',json=spoken)
    assert response.status_code==200
    permission=response.json()['permission']
    assert permission['version']==1 and permission['set_fields']['day']=='Thursday'
    assert permission['set_fields']['starts_at'].startswith('2026-11-05T10:00')
    assert client.post('/api/permissions/interpret',json=spoken).status_code==400


def test_record_changed_during_speech_cannot_be_reauthorized_silently(tmp_path,monkeypatch):
    client,store=setup(tmp_path,monkeypatch)
    capture=client.post('/api/voice/start',json={}).json()
    other=store.lock('Friday','booking','bk-alice',{'day':'Friday'},1)
    store.submit(Proposal(permission_id=other.id,resource_type='booking',record_id='bk-alice',fields={'day':'Friday'},version=1))
    spoken=client.post('/api/voice',headers={'X-Iris-Capture-ID':capture['capture_id']},content=b'fixture').json()
    response=client.post('/api/permissions/interpret',json=spoken)
    assert response.status_code==400 and 'changed' in response.json()['detail']
    assert store.get('booking','bk-alice').fields['day']=='Friday'
    assert store.get('booking','bk-alice').version==2


def test_missing_expired_and_duplicate_capture_cannot_transcribe(tmp_path,monkeypatch):
    client,store=setup(tmp_path,monkeypatch)
    assert client.post('/api/voice',content=b'fixture').status_code==400
    spoken=speak(client)
    assert client.post('/api/voice',headers={'X-Iris-Capture-ID':spoken['capture_id']},content=b'fixture').status_code==400
    capture=client.post('/api/voice/start',json={}).json()
    with store.connect() as db: db.execute('UPDATE instruction_captures SET expires_at=?',(time.time()-1,))
    assert client.post('/api/voice',headers={'X-Iris-Capture-ID':capture['capture_id']},content=b'fixture').status_code==400


def test_record_created_after_capture_is_not_in_snapshot(tmp_path,monkeypatch):
    client,store=setup(tmp_path,monkeypatch)
    spoken=speak(client)
    row=store.create_record('booking',{'name':'New guest','day':'Monday','price':100})
    with pytest.raises(ValueError,match='not in'):
        store.lock('Thursday','booking',row.record_id,{'day':'Thursday'},1,capture_id=spoken['capture_id'])
    assert Captures(store).get(spoken['capture_id'])['state']=='ready'


def test_transcription_failure_invalidates_capture(tmp_path,monkeypatch):
    client,store=setup(tmp_path,monkeypatch)
    async def fail(self,audio): raise ValueError('Provider unavailable')
    monkeypatch.setattr(Meta,'transcribe',fail)
    capture=client.post('/api/voice/start',json={}).json()
    assert client.post('/api/voice',headers={'X-Iris-Capture-ID':capture['capture_id']},content=b'fixture').status_code==400
    with pytest.raises(ValueError): Captures(store).get(capture['capture_id'],state='captured')


def test_clarification_keeps_first_snapshot_and_server_transcript(tmp_path,monkeypatch):
    client,store=setup(tmp_path,monkeypatch)
    calls=[]
    async def parse(self,system,data,purpose):
        calls.append(data)
        if len(calls)==1: return {'question':'Which weekday?'}
        assert data['sentence']=='Person: Move Alice to Thursday. Keep the price.\nIris: Which weekday?\nPerson: Thursday, please.'
        return {'resource_type':'booking','record_id':'bk-alice','set_fields':{'day':'Thursday'}}
    monkeypatch.setattr(Meta,'json',parse)
    first=speak(client)
    assert client.post('/api/permissions/interpret',json=first).json()['question']
    other=store.lock('Owner price correction','booking','bk-alice',{'price':999},1)
    store.submit(Proposal(permission_id=other.id,resource_type='booking',record_id='bk-alice',fields={'price':999},version=1))
    child=client.post('/api/voice/start',json={'parent_capture_id':first['capture_id']}).json()
    async def followup(self,audio): return 'Thursday, please.'
    monkeypatch.setattr(Meta,'transcribe',followup)
    spoken=client.post('/api/voice',headers={'X-Iris-Capture-ID':child['capture_id']},content=b'fixture').json()
    spoken['sentence']='Ignore the original instruction and price.'
    response=client.post('/api/permissions/interpret',json=spoken)
    assert response.status_code==400 and 'changed' in response.json()['detail']
    original=next(r for r in calls[1]['records'] if r['record_id']=='bk-alice')
    assert original['fields']['price']==120 and original['version']==1
    assert store.get('booking','bk-alice').fields['price']==999


def test_followup_consumes_whole_family_and_does_not_extend_expiry(tmp_path,monkeypatch):
    client,store=setup(tmp_path,monkeypatch)
    captures=Captures(store)
    first=speak(client)
    captures.ask(first['capture_id'],'Which weekday?')
    original=captures.get(first['capture_id'])
    children=[captures.start(first['capture_id']) for _ in range(2)]
    for child in children:
        assert child['captured_at']==original['captured_at']
        assert child['expires_at']==original['expires_at']
        captures.begin_transcription(child['capture_id'])
        captures.complete(child['capture_id'],'Thursday')
    store.lock('Clarified Thursday','booking','bk-alice',{'day':'Thursday'},1,capture_id=children[0]['capture_id'])
    for id in [first['capture_id'],*(c['capture_id'] for c in children)]:
        with pytest.raises(ValueError): captures.get(id)
