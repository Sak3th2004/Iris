import asyncio
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from iris.api import create_app
from iris.speech import Speech
from iris.store import Store
from iris.stream import together
from iris.worker_api import create_worker_app


@pytest.mark.parametrize('origin', ['', 'https://untrusted.example'])
def test_desktop_stream_requires_same_origin(tmp_path, monkeypatch, origin):
    monkeypatch.setenv('IRIS_WORKER_TOKEN', 't' * 40)
    client = TestClient(create_app(tmp_path / 'owner.sqlite'))
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect('/api/desktop/stream', headers={'origin': origin}):
            pass
    assert exc.value.code == 1008


def test_gateway_stream_requires_worker_token(tmp_path, monkeypatch):
    monkeypatch.setenv('IRIS_WORKER_TOKEN', 't' * 40)
    monkeypatch.setenv('IRIS_DB', str(tmp_path / 'worker.sqlite'))
    with pytest.raises(WebSocketDisconnect) as exc:
        with TestClient(create_worker_app()).websocket_connect('/desktop/stream'):
            pass
    assert exc.value.code == 1008


def test_relay_disconnect_cancels_other_direction():
    async def scenario():
        cancelled = asyncio.Event()
        async def pending():
            try:
                await asyncio.sleep(100)
            finally:
                cancelled.set()
        async def ended():
            await asyncio.sleep(0)
        await together(pending(), ended())
        assert cancelled.is_set()
    asyncio.run(scenario())


def test_speech_limit_is_atomic_and_no_provider_retry(tmp_path, monkeypatch):
    import boto3
    monkeypatch.setenv('AWS_ACCESS_KEY_ID', 'test-only')
    monkeypatch.setenv('AWS_SECRET_ACCESS_KEY', 'test-only')
    monkeypatch.setenv('IRIS_VOICE_ALLOWANCE_USD', '.01')
    calls = []
    class Polly:
        def synthesize_speech(self, **kwargs):
            calls.append(kwargs)
            return {'AudioStream': BytesIO(b'audio')}
    monkeypatch.setattr(boto3, 'client', lambda *args, **kwargs: Polly())
    speech = Speech(Store(tmp_path / 'speech.sqlite'))
    def request():
        try:
            return speech.synthesize('x' * 100)
        except ValueError:
            return 'blocked'
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: request(), range(2)))
    assert results.count(b'audio') == results.count('blocked') == 1
    assert len(calls) == 1
    assert calls[0]['TextType'] == 'text'
    assert speech.status()['reserved_allowance_usd'] == .01


def test_speech_failure_retains_reservation_and_sanitizes_error(tmp_path, monkeypatch):
    import boto3
    from botocore.exceptions import ClientError
    monkeypatch.setenv('AWS_ACCESS_KEY_ID', 'test-only')
    monkeypatch.setenv('AWS_SECRET_ACCESS_KEY', 'test-only')
    class FailingPolly:
        def synthesize_speech(self, **kwargs):
            raise ClientError({'Error': {'Code': 'Denied', 'Message': 'private-provider-detail'}}, 'SynthesizeSpeech')
    monkeypatch.setattr(boto3, 'client', lambda *args, **kwargs: FailingPolly())
    speech = Speech(Store(tmp_path / 'speech.sqlite'))
    with pytest.raises(ValueError, match='Polly could not') as exc:
        speech.synthesize('Hello')
    assert 'private-provider-detail' not in str(exc.value)
    assert speech.status()['reserved_allowance_usd'] == .0005
