"""Real paid end-to-end task against the isolated Docker worker; no scripted actions."""
import argparse
import json
import time
from pathlib import Path
from uuid import uuid4
import httpx

parser=argparse.ArgumentParser()
parser.add_argument('--resource',choices=['booking','order'],default='booking')
parser.add_argument('--require-open-reader',action='store_true')
args=parser.parse_args()
base='http://127.0.0.1:8768'
with httpx.Client(base_url=base,timeout=100) as client:
    def post(path,data):
        response=client.post(path,json=data)
        response.raise_for_status()
        return response.json()
    assert client.get('/api/desktop').json()['connected'], 'Start the Docker worker first.'
    initial=client.get('/api/state').json()
    if args.require_open_reader:
        assert initial['reader']['configured'] and initial['reader']['provider']=='Baseten', 'Configure Baseten before this paid check.'
    name='Mira '+uuid4().hex[:6]
    row=post('/api/records',{'resource_type':args.resource,'name':name,'detail':'Studio consultation' if args.resource=='booking' else 'Handmade notebook','price':137})
    target='Thursday' if args.resource=='booking' else 4
    sentence=f"Move {name}'s booking to Thursday. Keep the price and all other records unchanged." if args.resource=='booking' else f"Set {name}'s order quantity to 4. Keep the price and all other records unchanged."
    parsed=post('/api/permissions/interpret',{'sentence':sentence})
    assert parsed.get('permission'),parsed
    permission=parsed['permission']
    assert permission['record_id']==row['record_id'],parsed
    started=time.monotonic()
    job=post('/api/runs',{'permission_id':permission['id']})
    for _ in range(180):
        snapshot=client.get('/api/desktop').json()
        current=snapshot['job']
        if current['state'] not in ('queued','running'): break
        time.sleep(1)
    else:
        post(f"/api/runs/{job['id']}/stop",{})
        raise RuntimeError('Task exceeded three minutes; stopped and permission revoked.')
    state=client.get('/api/state').json()
    final=next(r for r in state['records'] if r['record_id']==row['record_id'])
    trace={'sentence':sentence,'permission':permission,'job':current,'events':snapshot['events'],'before':row,'after':final,'audit':[a for a in state['audit'] if a['proposal']['permission_id']==permission['id']],'seconds':time.monotonic()-started,'meta':state['meta'],'reader':state.get('reader'),'reader_checks':snapshot.get('reader_checks',[])}
    Path('artifacts').mkdir(exist_ok=True)
    path=Path('artifacts')/f"docker-{args.resource}-{job['id']}.json"
    path.write_text(json.dumps(trace,indent=2),encoding='utf-8')
    print(json.dumps({'job':current,'before':row,'after':final,'seconds':trace['seconds'],'trace':str(path),'meta':state['meta']},indent=2))
    assert current['state']=='complete',current
    assert final['fields']['day' if args.resource=='booking' else 'quantity']==target
    assert final['fields']['price']==137 and final['version']==2

    if args.require_open_reader:
        assert trace['reader_checks'], 'No independent read was recorded.'
        assert all(c['provider']=='Baseten' and c['model']=='meta-models/muse-spark-open-1026' and c['outcome']=='agree' for c in trace['reader_checks'])
