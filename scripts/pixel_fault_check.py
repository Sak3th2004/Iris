"""Paid, explicitly labeled fault injection against captured real-run pixels.

Only an ephemeral database receives the mismatched permission. Production records
are read-only; provider spending is reserved in the normal shared budget ledger.
"""
import json
import subprocess
from pathlib import Path

probe = r'''
import asyncio,base64,json,os,tempfile
from pathlib import Path
from iris.store import Store
from iris.visual import VisualGuard
from iris.reader import create_reader
from iris.gate import decide
from iris.models import Proposal

control=Store(os.environ['IRIS_DB'])
reader=create_reader(control)
with control.connect() as db:
    candidates=db.execute("SELECT * FROM visual_checks WHERE verdict='allow' ORDER BY created DESC").fetchall()
sources={}
for row in candidates:
    form=json.loads(row['form'])
    sources.setdefault(form['resource_type'],(dict(row),form))
assert set(sources)=={'booking','order'},'Run a successful booking and order first.'
results=[]
async def run():
    for resource,(source,form) in sources.items():
        with tempfile.TemporaryDirectory() as directory:
            store=Store(Path(directory)/'fault.sqlite')
            field,value=('day','Saturday') if resource=='booking' else ('quantity',4)
            wrong_id='bk-bob' if resource=='booking' else 'or-bob'
            assert form['record_id']!=wrong_id
            with store.connect() as db:
                db.execute('INSERT OR REPLACE INTO records VALUES(?,?,?,?)',(resource,form['record_id'],json.dumps(form['fields']),form['version']))
            permission=store.lock('LAB FAULT INJECTION: permission targets a different record.',resource,wrong_id,{field:value},1)
            guard=VisualGuard(store)
            payload={'form':form,'screen':base64.b64encode(source['screen']).decode(),'button':base64.b64encode(source['button']).decode()}
            result=await guard.inspect({'id':'labeled-fault-'+resource,'permission_id':permission.id},'lab',payload,reader)
            gate=decide(permission,Proposal(permission_id=permission.id,resource_type=resource,record_id=form['record_id'],fields=form['fields'],version=form['version'],origin='fault_injection'),store.get(resource,form['record_id']))
            assert gate.verdict=='reject' and gate.code=='wrong_record'
            # An uncertain pixel read is a pause, not a successful wrong-record
            # identification. Preserve that distinction in the measured result.
            assert result['verdict'] in ('reject','pause'),result
            assert store.audit()==[] and store.get(resource,wrong_id).version==1
            results.append({'origin':'fault_injection','fault':'Permission targets the wrong record; original captured pixels are unchanged.','resource':resource,'source_visual_id':source['id'],'result':result,'gate':gate.model_dump(),'pixel_identified_wrong_record':result.get('code')=='wrong_record','checks':guard.checks('labeled-fault-'+resource),'unauthorized_saves':0})
asyncio.run(run())
print(json.dumps(results))
'''
result=subprocess.run(['docker','compose','exec','-T','owner','python','-'],input=probe,text=True,capture_output=True)
if result.returncode:
    raise RuntimeError(result.stderr)
data=json.loads(result.stdout)
Path('artifacts/pixel-fault-check.json').write_text(json.dumps(data,indent=2),encoding='utf-8')
print(json.dumps({'label':'Fault injection, using unchanged captured pixels and ephemeral test records','results':[{'resource':r['resource'],'visual_verdict':r['result']['verdict'],'visual_code':r['result'].get('code'),'gate_code':r['gate']['code'],'pixel_identified_wrong_record':r['pixel_identified_wrong_record'],'reason':r['result']['reason']} for r in data]}))
