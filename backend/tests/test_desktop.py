import asyncio
import time
from fastapi.testclient import TestClient
from iris.api import create_app
from iris.worker_api import create_worker_app
from iris.store import Store
from iris.desktop import Desktop
from iris.agent import Jobs

def test_frame_requires_worker_token_and_expires(tmp_path,monkeypatch):
    path=tmp_path/'stream.sqlite'
    monkeypatch.setenv('IRIS_DB',str(path))
    monkeypatch.setenv('IRIS_WORKER_TOKEN','t'*40)
    worker=TestClient(create_worker_app())
    owner=TestClient(create_app(path))
    assert owner.get('/api/desktop/frame').status_code==503
    assert worker.post('/desktop/frame',content=b'\xff\xd8example\xff\xd9').status_code==401
    headers={'Authorization':'Bearer '+'t'*40}
    assert worker.post('/desktop/frame',content=b'not a jpeg',headers=headers).status_code==400
    assert worker.post('/desktop/frame',content=b'\xff\xd8example\xff\xd9',headers=headers).status_code==200
    assert owner.get('/api/desktop').json()['connected']
    assert owner.get('/api/desktop/frame').headers['content-type']=='image/jpeg'
    with Store(path).connect() as db:
        db.execute('UPDATE desktop SET received=?',(time.time()-10,))
    assert not owner.get('/api/desktop').json()['connected']
    assert owner.get('/api/desktop/frame').status_code==503

def test_stop_during_reader_prevents_save(tmp_path):
    store=Store(tmp_path/'stop.sqlite')
    jobs=Jobs(store)
    permission=store.lock('Move to Thursday','booking','bk-alice',{'day':'Thursday'},1)
    job=jobs.create(permission.id);jobs.claim()
    form=store.get('booking','bk-alice').model_dump();form['fields']['day']='Thursday'
    class Reader:
        async def json(self,system,data,purpose):
            jobs.stop(job['id'])
            return data['form']
    result=asyncio.run(jobs.submit(job['id'],form,Reader()))
    assert result['decision']['verdict']=='pause'
    assert store.get('booking','bk-alice').version==1
    assert jobs.get(job['id'])['state']=='stopped'
    assert store.permission(permission.id) is None
