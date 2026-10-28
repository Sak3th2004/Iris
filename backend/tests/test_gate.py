from concurrent.futures import ThreadPoolExecutor
import pytest
from iris.store import Store
from iris.models import Proposal

@pytest.fixture
def store(tmp_path):
    return Store(tmp_path / 'test.sqlite')

def permission(store):
    return store.lock("Move Alice to Thursday. Keep the price.", "booking", "bk-alice", {"day":"Thursday"}, 1)

def proposal(p, **kw):
    return Proposal(**({"permission_id":p.id,"resource_type":"booking","record_id":"bk-alice","fields":{"day":"Thursday"},"version":1} | kw))

def test_wrong_record_unchanged(store):
    p = permission(store)
    before = store.get('booking','bk-bob')
    assert store.submit(proposal(p,record_id='bk-bob'))['decision']['code'] == 'wrong_record'
    assert store.get('booking','bk-bob') == before

def test_preserved_field(store):
    p = permission(store)
    assert store.submit(proposal(p,fields={'day':'Thursday','price':0}))['decision']['verdict'] == 'reject'
    assert store.get('booking','bk-alice').fields['price'] == 120

def test_exact_once_concurrently(store):
    p = permission(store)
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(lambda _: store.submit(proposal(p)), range(4)))
    assert sum(r['decision']['verdict'] == 'allow' for r in results) == 1
    row = store.get('booking','bk-alice')
    assert row.version == 2 and row.fields['day'] == 'Thursday'

def test_stale_invalidates(store):
    p = permission(store)
    other = permission(store)
    store.submit(proposal(other))
    assert store.submit(proposal(p))['decision']['code'] == 'stale_version'
    assert store.permission(p.id) is None

@pytest.mark.parametrize('operation',['delete','message','cancel','email','create'])
def test_forbidden(store, operation):
    p = permission(store)
    assert store.submit(proposal(p,operation=operation))['decision']['verdict'] == 'reject'
    assert store.get('booking','bk-alice').version == 1

def test_missing_permission(store):
    p = permission(store)
    assert store.submit(proposal(p,permission_id=None))['decision']['verdict'] == 'pause'
    assert store.get('booking','bk-alice').version == 1

@pytest.mark.parametrize('channel',['click','enter','http'])
def test_channel_equivalence(store,channel):
    p = permission(store)
    assert store.submit(proposal(p,channel=channel,record_id='bk-bob'))['decision']['code'] == 'wrong_record'

def test_order_same_gate(store):
    p = store.lock('Set quantity to 3','order','or-bob',{'quantity':3},1)
    result = store.submit(Proposal(permission_id=p.id,resource_type='order',record_id='or-bob',fields={'quantity':3},version=1))
    assert result['after']['fields']['quantity'] == 3
    assert result['after']['fields']['price'] == 64

def test_json_type_confusion(store):
    p = store.lock('Set quantity to 3','order','or-alice',{'quantity':3},1)
    q = Proposal(permission_id=p.id,resource_type='order',record_id='or-alice',fields={'quantity':True},version=1)
    assert store.submit(q)['decision']['verdict'] == 'reject'
