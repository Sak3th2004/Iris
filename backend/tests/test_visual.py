import asyncio
import base64
import json

import pytest

from iris.agent import Jobs
from iris.store import Store

JPEG=base64.b64encode(b'\xff\xd8test-fixture\xff\xd9').decode()


class PixelReader:
    provider='test'
    model='test-vision'
    def __init__(self, form, operation='update'):
        self.form=form
        self.operation=operation
    async def json(self, system, data, purpose, *, images=None):
        assert purpose=='visual_preclick'
        assert data=={'images':['current screen','button under cursor']}
        assert len(images)==2
        assert 'permission' not in json.dumps(data) and 'fields' not in json.dumps(data)
        return {'button_text':'Save','operation':self.operation,'record':self.form}


def setup(tmp_path):
    store=Store(tmp_path/'visual.sqlite')
    jobs=Jobs(store)
    permission=store.lock('Move Alice to Thursday; keep the price.','booking','bk-alice',{'day':'Thursday'},1)
    job=jobs.create(permission.id,require_visual=True)
    jobs.claim()
    form=store.get('booking','bk-alice').model_dump()
    form['fields']['day']='Thursday'
    return store,jobs,job,form


def inspect(jobs,job,form,reader):
    return asyncio.run(jobs.preflight(job['id'],{'form':form,'screen':JPEG,'button':JPEG},reader,'local'))


@pytest.mark.parametrize('fault',['wrong_record','price','cancel'])
def test_visual_guard_rejects_before_click(tmp_path,fault):
    store,jobs,job,form=setup(tmp_path)
    if fault=='wrong_record':
        form=store.get('booking','bk-bob').model_dump()
        form['fields']['day']='Thursday'
    if fault=='price': form['fields']['price']=0
    result=inspect(jobs,job,form,PixelReader(form,'cancel' if fault=='cancel' else 'update'))
    assert result['verdict']=='reject'
    assert jobs.get(job['id'])['state']=='paused'
    assert store.get('booking','bk-alice').version==store.get('booking','bk-bob').version==1
    assert store.audit()==[]  # No write even proposed after the pre-click rejection.


def test_visual_disagreement_pauses(tmp_path):
    store,jobs,job,form=setup(tmp_path)
    read=store.get('booking','bk-bob').model_dump()
    assert inspect(jobs,job,form,PixelReader(read))['verdict']=='pause'
    assert store.get('booking','bk-alice').version==1


def test_visual_approval_is_not_a_save_and_cannot_replay(tmp_path):
    store,jobs,job,form=setup(tmp_path)
    assert inspect(jobs,job,form,PixelReader(form))['verdict']=='allow'
    assert store.get('booking','bk-alice').version==1
    assert jobs.visual.consume(job['id'],'local',form)
    assert not jobs.visual.consume(job['id'],'local',form)


@pytest.mark.parametrize('fault',['changed_form','expired','wrong_worker'])
def test_visual_approval_bound_to_form_time_and_worker(tmp_path,fault):
    store,jobs,job,form=setup(tmp_path)
    inspect(jobs,job,form,PixelReader(form))
    if fault=='changed_form': form['fields']['price']=0
    if fault=='expired':
        with store.connect() as db: db.execute('UPDATE visual_checks SET created=0')
    assert not jobs.visual.consume(job['id'],'other' if fault=='wrong_worker' else 'local',form)
    assert store.get('booking','bk-alice').version==1


@pytest.mark.parametrize('channel',['click','enter','http'])
def test_required_visual_cannot_be_bypassed_by_transport(tmp_path,channel):
    store,jobs,job,form=setup(tmp_path)
    class Reader:
        async def json(self,*args): raise AssertionError('No provider call before visual approval.')
    result=asyncio.run(jobs.submit(job['id'],form,Reader(),channel=channel))
    assert result['decision']['verdict']=='pause'
    assert store.get('booking','bk-alice').version==1
