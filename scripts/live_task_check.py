"""Run one explicitly authorized change on an existing invented record with real models."""
import argparse
import json
import time
from pathlib import Path
import httpx

parser=argparse.ArgumentParser()
parser.add_argument('resource',choices=['booking','order'])
parser.add_argument('record_id')
parser.add_argument('value')
args=parser.parse_args()
with httpx.Client(base_url='http://127.0.0.1:8768',timeout=100) as client:
    state=client.get('/api/state').json()
    assert not state['agent']['job'] or state['agent']['job']['state'] not in ('queued','running')
    before={(r['resource_type'],r['record_id']):r for r in state['records']}
    target=before[args.resource,args.record_id]
    field='day' if args.resource=='booking' else 'quantity'
    value=args.value if field=='day' else int(args.value)
    sentence=f"Set {target['fields']['name']}'s {args.resource} {field} to {value}. Keep the price and every other field and record unchanged."
    parsed=client.post('/api/permissions/interpret',json={'sentence':sentence})
    parsed.raise_for_status();permission=parsed.json()['permission']
    assert permission['record_id']==args.record_id and permission['set_fields'][field]==value
    response=client.post('/api/runs',json={'permission_id':permission['id']})
    response.raise_for_status();job=response.json();started=time.monotonic()
    try:
        while time.monotonic()-started<180:
            detail=client.get('/api/runs/'+job['id']).json()
            if detail['job']['state'] not in ('queued','running'): break
            time.sleep(1)
        else: raise AssertionError('Live task timed out.')
    except BaseException:
        client.post('/api/runs/'+job['id']+'/stop',json={})
        raise
    Path('artifacts').mkdir(exist_ok=True)
    Path('artifacts/live-task-'+job['id']+'.json').write_text(json.dumps(detail,indent=2),encoding='utf-8')
    assert detail['job']['state']=='complete',detail
    assert detail['receipt']['after']['fields']==target['fields']|permission['set_fields']
    assert detail['receipt']['after']['version']==target['version']+1
    after={(r['resource_type'],r['record_id']):r for r in client.get('/api/state').json()['records']}
    assert all(after[key]==row for key,row in before.items() if key!=(args.resource,args.record_id))
    print(json.dumps({'passed':True,'job':job['id'],'resource':args.resource,'elapsed_seconds':round(time.monotonic()-started,1),'visual_ms':detail['visual_checks'][0]['elapsed_ms'],'after':detail['receipt']['after']}))
