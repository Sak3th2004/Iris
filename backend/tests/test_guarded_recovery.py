import asyncio
from iris.agent import Jobs
from iris.models import Proposal
from iris.store import Store


def setup(tmp_path):
    store=Store(tmp_path/'recovery.sqlite');jobs=Jobs(store)
    permission=store.lock('Set Alice order quantity to 4; keep the price.','order','or-alice',{'quantity':4},1)
    job=jobs.create(permission.id);jobs.claim()
    return store,jobs,permission,job['id']


def test_wrong_record_can_recover_under_same_permission(tmp_path):
    store,jobs,permission,id=setup(tmp_path)
    bob=store.get('order','or-bob').model_dump()
    result=jobs.allow_fill(id,'quantity',4,'local',bob)
    assert not result['ok'] and result['code']=='wrong_record'
    assert jobs.get(id)['state']=='running'
    assert store.permission(permission.id)
    alice=store.get('order','or-alice').model_dump()
    assert jobs.allow_fill(id,'quantity',4,'local',alice)['ok']
    alice['fields']['quantity']=4
    assert not jobs.hold(id,alice,'local')['hold']
    class Reader:
        async def json(self,system,data,purpose): return data['form']
    result=asyncio.run(jobs.submit(id,alice,Reader()))
    assert result['decision']['verdict']=='allow'
    assert store.get('order','or-bob').model_dump()==bob
    assert store.get('order','or-alice').version==2
    assert jobs.guards(id)[0]['form']==bob


def test_stale_database_stops_even_if_open_form_version_looks_current(tmp_path):
    store,jobs,permission,id=setup(tmp_path)
    form=store.get('order','or-alice').model_dump();form['fields']['quantity']=4
    other=store.lock('Owner quantity correction','order','or-alice',{'quantity':2},1)
    store.submit(Proposal(permission_id=other.id,resource_type='order',record_id='or-alice',fields={'quantity':2},version=1))
    result=jobs.hold(id,form,'local')
    assert result['hold'] and result['code']=='stale_version' and not result['recoverable']
    assert 'new permission' in result['reason']
    assert jobs.get(id)['state']=='paused' and store.permission(permission.id) is None
    assert store.get('order','or-alice').fields['quantity']==2


def test_missing_protected_fields_and_wrong_values_never_click(tmp_path):
    store,jobs,permission,id=setup(tmp_path)
    form=store.get('order','or-alice').model_dump();form['fields']['quantity']=4
    del form['fields']['price']
    assert jobs.hold(id,form,'local')['hold']
    form['fields']['price']=0
    result=jobs.hold(id,form,'local')
    assert result['hold'] and result['code']=='protected_form_field' and result['recoverable']
    assert not jobs.allow_fill(id,'price',0,'local',form)['ok']
    assert store.get('order','or-alice').fields['price']==48


def test_owner_discard_revokes_permission_and_running_task(tmp_path):
    store,jobs,permission,id=setup(tmp_path)
    store.revoke(permission.id)
    assert jobs.get(id)['state']=='stopped'
    assert store.permission(permission.id) is None
    result=store.submit(Proposal(permission_id=permission.id,resource_type='order',record_id='or-alice',fields={'quantity':4},version=1),job_id=id,worker_id='local')
    assert result['decision']['verdict']=='pause'
    assert store.get('order','or-alice').version==1


def test_legacy_booking_upgrade_invalidates_old_permission_atomically(tmp_path):
    path=tmp_path/'legacy.sqlite';store=Store(path);jobs=Jobs(store)
    row=store.create_record('booking',{'name':'Legacy invented guest','day':'Tuesday','price':120})
    permission=store.lock('Thursday','booking',row.record_id,{'day':'Thursday'},1)
    job=jobs.create(permission.id)
    upgraded=Store(path)
    assert upgraded.get('booking',row.record_id).version==2
    assert upgraded.permission(permission.id) is None
    assert jobs.get(job['id'])['state']=='paused'
    assert Store(path).get('booking',row.record_id).version==2
