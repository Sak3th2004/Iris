import asyncio
from iris.agent import Jobs
from iris.store import Store

def test_blind_reader_never_sees_permission(tmp_path):
    store=Store(tmp_path/'agent.sqlite')
    permission=store.lock('Private instruction: Thursday','booking','bk-alice',{'day':'Thursday'},1)
    jobs=Jobs(store);job=jobs.create(permission.id);jobs.claim()
    form=store.get('booking','bk-alice').model_dump();form['fields']['day']='Thursday'
    class Reader:
        async def json(self,system,data,purpose):
            assert purpose=='blind_reader'
            assert set(data)=={'form'}
            assert 'Private instruction' not in str(data)
            return data['form']
    result=asyncio.run(jobs.submit(job['id'],form,Reader()))
    assert result['decision']['verdict']=='allow'
    assert jobs.get(job['id'])['state']=='complete'

def test_reader_disagreement_saves_nothing(tmp_path):
    store=Store(tmp_path/'agent.sqlite')
    permission=store.lock('Thursday','booking','bk-alice',{'day':'Thursday'},1)
    jobs=Jobs(store);job=jobs.create(permission.id);jobs.claim()
    class Reader:
        async def json(self,*args): return {'question':'Which record is open?'}
    result=asyncio.run(jobs.submit(job['id'],store.get('booking','bk-alice').model_dump(),Reader()))
    assert result['decision']['verdict']=='pause'
    assert store.get('booking','bk-alice').version==1

def test_worker_has_no_owner_routes(tmp_path,monkeypatch):
    from fastapi.testclient import TestClient
    from iris.worker_api import create_worker_app
    monkeypatch.setenv('IRIS_WORKER_TOKEN','a'*32)
    monkeypatch.setenv('IRIS_DB',str(tmp_path/'worker.sqlite'))
    client=TestClient(create_worker_app())
    assert client.get('/records').status_code==401
    for route in ('/api/permissions/manual','/api/permissions/interpret','/api/records'):
        assert client.post(route,headers={'Authorization':'Bearer '+'a'*32},json={}).status_code==404
