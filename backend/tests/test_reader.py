import asyncio
import json
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest

from iris.agent import Jobs
from iris.meta import Meta
from iris.reader import Baseten, create_reader
from iris.store import Store


def test_baseten_exact_model_content_and_separate_budget(tmp_path, monkeypatch):
    monkeypatch.setenv('BASETEN_API_KEY', 'test-only-key')
    store = Store(tmp_path / 'reader.sqlite')
    reader = Baseten(store)
    form = store.get('booking', 'bk-alice').model_dump()

    async def respond(request):
        assert str(request.url) == 'https://inference.baseten.co/v1/chat/completions'
        assert request.headers['authorization'] == 'Bearer test-only-key'
        body = json.loads(request.content)
        assert body['model'] == 'meta-models/muse-spark-open-1026'
        assert body['max_completion_tokens'] == 4096
        assert json.loads(body['messages'][1]['content']) == {'form': form}
        return httpx.Response(200, json={
            'choices': [{'finish_reason': 'stop', 'message': {
                'content': json.dumps(form), 'reasoning_content': 'Never use this as the answer.'}}],
            'usage': {'prompt_tokens': 100, 'completion_tokens': 200}})

    original = httpx.AsyncClient
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kw: original(transport=httpx.MockTransport(respond), **kw))
    assert asyncio.run(reader.json('Read JSON', {'form': form}, 'blind_reader')) == form
    assert reader.status()['committed_usd'] == .000975
    assert Meta(store).status()['committed_usd'] == 0


def test_budget_reservations_are_atomic_and_reject_invalid_limits(tmp_path, monkeypatch):
    monkeypatch.setenv('BASETEN_API_KEY', 'test-only-key')
    monkeypatch.setenv('IRIS_BASETEN_SPEND_LIMIT_USD', '.03')
    reader = Baseten(Store(tmp_path / 'budget.sqlite'))
    def reserve(_):
        try:
            reader.reserve(.02, 'test')
            return True
        except ValueError:
            return False
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(reserve, range(2))) == [False, True]
    for value in ('nan', 'inf', '-1'):
        monkeypatch.setenv('IRIS_BASETEN_SPEND_LIMIT_USD', value)
        with pytest.raises(ValueError):
            Baseten(reader.store)
    monkeypatch.setenv('IRIS_BASETEN_SPEND_LIMIT_USD', '150')
    assert Baseten(reader.store).limit == 100


@pytest.mark.parametrize('response', ['timeout', 'truncated', 'nonobject', 'http_error', 'malformed', 'bad_envelope', 'bad_choice'])
def test_provider_failures_pause_revoke_and_retain_reservation(tmp_path, monkeypatch, response):
    monkeypatch.setenv('BASETEN_API_KEY', 'test-only-key')
    store = Store(tmp_path / 'failure.sqlite')
    reader = Baseten(store)
    jobs = Jobs(store)
    permission = store.lock('Thursday', 'booking', 'bk-alice', {'day': 'Thursday'}, 1)
    job = jobs.create(permission.id)
    jobs.claim()
    form = store.get('booking', 'bk-alice').model_dump()
    form['fields']['day'] = 'Thursday'

    def respond(request):
        if response == 'timeout':
            raise httpx.ReadTimeout('test', request=request)
        if response == 'http_error':
            return httpx.Response(429, json={'error': 'secret details must not be logged'})
        if response == 'bad_envelope':
            return httpx.Response(200, json=[])
        if response == 'bad_choice':
            return httpx.Response(200, json={'choices':[None]})
        return httpx.Response(200, json={'choices': [{'finish_reason': 'length' if response == 'truncated' else 'stop',
            'message': {'content': '[]' if response == 'nonobject' else 'invalid' if response == 'malformed' else json.dumps(form)}}]})

    original = httpx.AsyncClient
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kw: original(transport=httpx.MockTransport(respond), **kw))
    result = asyncio.run(jobs.submit(job['id'], form, reader))
    assert result['decision']['verdict'] == 'pause'
    assert store.get('booking', 'bk-alice').version == 1
    assert store.permission(permission.id) is None
    assert jobs.get(job['id'])['state'] == 'paused'
    assert reader.status()['committed_usd'] > 0
    check = jobs.checks(job['id'])[0]
    assert (check['provider'], check['model'], check['outcome']) == ('Baseten', reader.model, 'unavailable')


def test_routing_requires_explicit_fallback_and_missing_key_does_not_spend(tmp_path, monkeypatch):
    monkeypatch.delenv('BASETEN_API_KEY', raising=False)
    monkeypatch.delenv('IRIS_READER_PROVIDER', raising=False)
    store = Store(tmp_path / 'route.sqlite')
    reader = create_reader(store)
    assert isinstance(reader, Baseten)
    with pytest.raises(ValueError, match='BASETEN_API_KEY'):
        reader.reserve(.01, 'test')
    assert reader.status()['committed_usd'] == 0
    monkeypatch.setenv('IRIS_READER_PROVIDER', 'meta')
    assert type(create_reader(store)) is Meta


def test_reader_agreement_cannot_authorize_wrong_record(tmp_path):
    store = Store(tmp_path / 'wrong.sqlite')
    jobs = Jobs(store)
    permission = store.lock('Thursday', 'booking', 'bk-alice', {'day': 'Thursday'}, 1)
    job = jobs.create(permission.id)
    jobs.claim()
    class Reader:
        provider = 'Baseten'
        model = Baseten.model
        async def json(self, system, data, purpose):
            assert set(data) == {'form'}
            return data['form']
    form = store.get('booking', 'bk-bob').model_dump()
    form['fields']['day'] = 'Thursday'
    result = asyncio.run(jobs.submit(job['id'], form, Reader()))
    assert result['decision']['verdict'] == 'reject'
    assert store.get('booking', 'bk-bob').version == 1
    assert jobs.checks(job['id'])[0]['outcome'] == 'agree'
