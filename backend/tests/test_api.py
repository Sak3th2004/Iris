from fastapi.testclient import TestClient
from iris.api import create_app

def test_new_person_entire_flow(tmp_path):
    client = TestClient(create_app(tmp_path/'api.sqlite'))
    response = client.post('/api/records',json={'resource_type':'booking','name':'Mira Patel','detail':'Architecture review','price':245})
    assert response.status_code == 200
    row = response.json()
    p = client.post('/api/permissions/manual',json={'resource_type':'booking','record_id':row['record_id'],'field':'day','value':'Saturday','version':1}).json()
    proposal = {'permission_id':p['id'],'resource_type':'booking','record_id':row['record_id'],'fields':{'day':'Saturday'},'version':1}
    result = client.post('/api/writes',json=proposal).json()
    assert result['decision']['verdict'] == 'allow'
    assert result['after']['fields']['name'] == 'Mira Patel'
    assert result['after']['fields']['price'] == 245
    assert result['after']['fields']['day'] == 'Saturday'
    assert client.post('/api/writes',json=proposal).json()['decision']['verdict'] == 'pause'

def test_missing_key_is_explicit(tmp_path,monkeypatch):
    monkeypatch.delenv('MODEL_API_KEY',raising=False)
    client = TestClient(create_app(tmp_path/'api.sqlite'))
    result = client.post('/api/permissions/interpret',json={'sentence':'Move someone later'})
    assert result.status_code == 400
    assert 'MODEL_API_KEY' in result.json()['detail']
    assert not client.get('/api/state').json()['audit']

def test_cross_origin_write_blocked(tmp_path):
    client = TestClient(create_app(tmp_path/'api.sqlite'))
    assert client.post('/api/writes',headers={'Origin':'https://evil.example'},json={}).status_code == 403
