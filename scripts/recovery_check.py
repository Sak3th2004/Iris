"""Labeled fault injection: stop the real browser worker, verify expiry, then a fresh task.

Uses real model calls and only the Iris Docker service. Never retries a model/write.
"""
import json
import subprocess
import time
from pathlib import Path
from uuid import uuid4
import httpx

base='http://127.0.0.1:8768'
with httpx.Client(base_url=base,timeout=100) as client:
    def post(path,body):
        r=client.post(path,json=body);r.raise_for_status();return r.json()
    def wait_for(predicate,seconds=60):
        until=time.monotonic()+seconds
        while time.monotonic()<until:
            value=predicate()
            if value:return value
            time.sleep(.2)
        raise AssertionError('Timed out waiting for expected recovery state.')
    initial=client.get('/api/desktop').json()
    assert initial['connected'] and (not initial['job'] or initial['job']['state'] not in ('running','queued'))
    row=post('/api/records',{'resource_type':'order','name':'Recovery '+uuid4().hex[:6],'detail':'Invented paper lamp','price':81})
    def authorize():
        return post('/api/permissions/manual',{'resource_type':'order','record_id':row['record_id'],'field':'quantity','value':3,'version':1})
    p=authorize();job=post('/api/runs',{'permission_id':p['id']})
    try:
        wait_for(lambda: client.get(f"/api/runs/{job['id']}").json()['job']['state']=='running')
        subprocess.run(['docker','compose','stop','-t','1','browser'],check=True,capture_output=True)
        # No owner polling during this interval: the gateway's background sweep must expire the lease.
        time.sleep(24)
        query="import os,sqlite3,sys; db=sqlite3.connect(os.environ['IRIS_DB']); print(db.execute('SELECT state FROM jobs WHERE id=?',(sys.argv[1],)).fetchone()[0])"
        observed=subprocess.run(['docker','compose','exec','-T','gateway','python','-c',query,job['id']],check=True,capture_output=True,text=True).stdout.strip()
        assert observed=='paused','Background sweeper did not expire the task before owner polling.'
        failed=client.get(f"/api/runs/{job['id']}").json()
        assert failed['job']['state']=='paused',failed
        assert failed['receipt'] is None
        stale=post('/api/writes',{'permission_id':p['id'],'resource_type':'order','record_id':row['record_id'],'fields':{'quantity':3},'version':1,'origin':'fault_injection'})
        assert stale['decision']['verdict']=='pause' and stale['after']['version']==1
    finally:
        subprocess.run(['docker','compose','start','browser'],check=True,capture_output=True)
    wait_for(lambda: client.get('/api/desktop').json()['connected'])
    new_permission=authorize();fresh=post('/api/runs',{'permission_id':new_permission['id']})
    def finished():
        detail=client.get(f"/api/runs/{fresh['id']}").json()
        return detail if detail['job']['state'] not in ('running','queued') else None
    recovered=wait_for(finished,120)
    assert recovered['job']['state']=='complete',recovered
    assert recovered['receipt']['after']['fields']['quantity']==3
    assert recovered['receipt']['after']['fields']['price']==81
    assert recovered['receipt']['after']['version']==2
    trace={'label':'Developer fault injection: browser container stopped during live task; not an agent mistake',
        'before':row,'interrupted':failed,'expired_permission_attempt':stale,'fresh_authorization_run':recovered}
    Path('artifacts').mkdir(exist_ok=True)
    Path('artifacts/recovery-check.json').write_text(json.dumps(trace,indent=2),encoding='utf-8')
    print(json.dumps({'interrupted':failed['job'],'fresh_task':recovered['job'],'receipt':recovered['receipt'],'trace':'artifacts/recovery-check.json'},indent=2))
