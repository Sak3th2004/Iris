from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import pytest
from iris.schedule import TZ,move_to_weekday,overlaps
from iris.store import Store
from iris.models import Proposal


def fields(start,**extra):
    return {'name':'Invented guest','price':100,'host':'Test studio','status':'confirmed','duration_minutes':60,'starts_at':start,**extra}


@pytest.mark.parametrize('first,second,expected',[
    ('2030-02-04T10:00:00+05:30','2030-02-04T10:30:00+05:30',True),
    ('2030-02-04T10:00:00+05:30','2030-02-04T11:00:00+05:30',False),
    ('2030-02-04T23:30:00+05:30','2030-02-05T00:00:00+05:30',True),
    ('2030-02-04T10:00:00+05:30','2030-02-04T04:45:00+00:00',True),
])
def test_intervals(first,second,expected):
    assert overlaps(fields(first),fields(second)) is expected
    assert not overlaps(fields(first),fields(second,host='Other studio'))
    assert not overlaps(fields(first),fields(second,status='cancelled'))


def test_weekdays_are_upcoming_and_keep_local_clock():
    now=datetime(2030,2,4,10,30,tzinfo=TZ) # Monday
    assert move_to_weekday({'time':'10:00'},'Monday',now=now)['starts_at']=='2030-02-11T10:00:00+05:30'
    assert move_to_weekday({'time':'11:00'},'Monday',now=now)['starts_at']=='2030-02-04T11:00:00+05:30'
    assert move_to_weekday({'starts_at':'2026-11-03T14:30:00+05:30'},'Thursday',now=now)['starts_at']=='2030-02-07T14:30:00+05:30'


def test_overlap_rejects_without_consuming_permission_or_mutation(tmp_path):
    store=Store(tmp_path/'slots.sqlite')
    first=store.create_record('booking',fields('2030-02-04T10:00:00+05:30'))
    second=store.create_record('booking',fields('2030-02-05T10:00:00+05:30'))
    target={'starts_at':'2030-02-04T10:30:00+05:30'}
    permission=store.lock('Move to the requested slot','booking',second.record_id,target,1)
    result=store.submit(Proposal(permission_id=permission.id,resource_type='booking',record_id=second.record_id,fields=target,version=1))
    assert result['decision']['code']=='slot_taken'
    assert result['before']==result['after'] and store.permission(permission.id)
    assert store.get('booking',first.record_id).version==1


def test_concurrent_creates_cannot_double_book(tmp_path):
    store=Store(tmp_path/'concurrent-slots.sqlite')
    def create(_):
        try: return store.create_record('booking',fields('2030-02-04T10:00:00+05:30')).record_id
        except ValueError: return None
    with ThreadPoolExecutor(max_workers=2) as pool: results=list(pool.map(create,range(2)))
    assert sum(result is not None for result in results)==1
