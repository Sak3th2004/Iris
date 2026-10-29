import asyncio
import json
import time
import sqlite3
from concurrent.futures import ThreadPoolExecutor
import pytest
from iris.agent import Jobs
from iris.models import Proposal
from iris.store import Store


def task(tmp_path):
    store=Store(tmp_path/'recovery.sqlite')
    jobs=Jobs(store)
    permission=store.lock('Thursday','booking','bk-alice',{'day':'Thursday'},1)
    job=jobs.create(permission.id)
    return store,jobs,permission,job


def expire(store,job):
    with store.connect() as db:
        db.execute('UPDATE job_leases SET expires_at=? WHERE job_id=?',(time.time()-1,job['id']))


@pytest.mark.parametrize('claim',[False,True])
def test_lost_queue_or_worker_revokes_and_allows_fresh_task(tmp_path,claim):
    store,jobs,permission,job=task(tmp_path)
    if claim: jobs.claim('worker-a')
    expire(store,job)
    assert jobs.recover()==1
    assert jobs.get(job['id'])['state']=='paused'
    assert store.permission(permission.id) is None
    assert store.get('booking','bk-alice').version==1
    assert jobs.claim('worker-b') is None
    fresh=store.lock('Friday','booking','bk-alice',{'day':'Friday'},1)
    assert jobs.create(fresh.id)['state']=='queued'


def test_old_worker_cannot_renew_or_submit(tmp_path):
    store,jobs,permission,job=task(tmp_path)
    jobs.claim('worker-a')
    with pytest.raises(ValueError): jobs.heartbeat(job['id'],'worker-b')
    jobs.heartbeat(job['id'],'worker-a')
    expire(store,job)
    with pytest.raises(ValueError): jobs.heartbeat(job['id'],'worker-a')
    assert jobs.get(job['id'])['state']=='paused'


def test_expiry_during_reader_blocks_late_response(tmp_path):
    store,jobs,permission,job=task(tmp_path);jobs.claim()
    form=store.get('booking','bk-alice').model_dump();form['fields']['day']='Thursday'
    class Reader:
        async def json(self,system,data,purpose):
            expire(store,job)
            return data['form']
    result=asyncio.run(jobs.submit(job['id'],form,Reader()))
    assert result['decision']['verdict']=='pause'
    assert store.get('booking','bk-alice').version==1
    assert jobs.get(job['id'])['state']=='paused'


def test_save_receipt_and_job_are_committed_together(tmp_path):
    store,jobs,permission,job=task(tmp_path);jobs.claim('worker-a')
    proposal=Proposal(permission_id=permission.id,resource_type='booking',record_id='bk-alice',fields={'day':'Thursday'},version=1)
    # No Jobs.finish call: persistence owns completion atomically.
    result=store.submit(proposal,job_id=job['id'],worker_id='worker-a')
    reopened=Jobs(Store(store.path))
    assert reopened.get(job['id'])['state']=='complete'
    assert reopened.receipt(job['id'])==result
    assert store.permission(permission.id) is None
    expire(store,job);reopened.recover()
    assert reopened.get(job['id'])['state']=='complete'
    assert store.get('booking','bk-alice').version==2


def test_owner_http_cannot_bypass_assigned_lease(tmp_path):
    store,jobs,permission,job=task(tmp_path);jobs.claim()
    proposal=Proposal(permission_id=permission.id,resource_type='booking',record_id='bk-alice',fields={'day':'Thursday'},version=1)
    assert store.submit(proposal)['decision']['verdict']=='pause'
    assert store.get('booking','bk-alice').version==1


def test_concurrent_claims_have_one_owner(tmp_path):
    store,jobs,permission,job=task(tmp_path)
    with ThreadPoolExecutor(max_workers=2) as pool:
        claimed=list(pool.map(jobs.claim,['worker-a','worker-b']))
    assert sum(x is not None for x in claimed)==1


def test_recover_legacy_commit_without_replaying(tmp_path):
    store,jobs,permission,job=task(tmp_path);jobs.claim()
    proposal=Proposal(permission_id=permission.id,resource_type='booking',record_id='bk-alice',fields={'day':'Thursday'},version=1)
    store.submit(proposal,job_id=job['id'],worker_id='local')
    with store.connect() as db:
        db.execute("UPDATE jobs SET state='running' WHERE id=?",(job['id'],))
        db.execute('DELETE FROM job_receipts WHERE job_id=?',(job['id'],))
    expire(store,job)
    jobs.recover()
    assert jobs.get(job['id'])['state']=='complete'
    assert store.get('booking','bk-alice').version==2
    assert len(store.audit())==1
    assert jobs.receipt(job['id'])['after']['version']==2


def test_receipt_failure_rolls_back_record_permission_and_job(tmp_path):
    store,jobs,permission,job=task(tmp_path);jobs.claim()
    with store.connect() as db:
        db.execute("CREATE TRIGGER fail_receipt BEFORE INSERT ON job_receipts BEGIN SELECT RAISE(ABORT,'injected storage fault'); END")
    proposal=Proposal(permission_id=permission.id,resource_type='booking',record_id='bk-alice',fields={'day':'Thursday'},version=1)
    with pytest.raises(sqlite3.IntegrityError):
        store.submit(proposal,job_id=job['id'],worker_id='local')
    assert store.get('booking','bk-alice').version==1
    assert store.permission(permission.id) is not None
    assert jobs.get(job['id'])['state']=='running'
    assert jobs.receipt(job['id']) is None and not store.audit()


def test_gateway_sweeps_without_owner_polling(tmp_path,monkeypatch):
    from fastapi.testclient import TestClient
    from iris.worker_api import create_worker_app
    store,jobs,permission,job=task(tmp_path);jobs.claim()
    monkeypatch.setenv('IRIS_DB',store.path)
    monkeypatch.setenv('IRIS_WORKER_TOKEN','test-only-worker-token-123456789012345')
    expire(store,job)
    with TestClient(create_worker_app()):
        until=time.monotonic()+4
        while time.monotonic()<until:
            with store.connect() as db:
                state=db.execute('SELECT state FROM jobs WHERE id=?',(job['id'],)).fetchone()[0]
            if state=='paused':break
            time.sleep(.05)
        assert state=='paused'
    assert store.permission(permission.id) is None
