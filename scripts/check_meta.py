"""One paid live interpretation check, using the local key without printing it."""
import sys
import argparse
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from fastapi.testclient import TestClient
from iris.api import app

parser=argparse.ArgumentParser()
parser.add_argument('--sentence',default="Move Alice Morgan's booking to Thursday. Keep the price. Leave Bob unchanged.")
args=parser.parse_args()

with TestClient(app) as client:
    response = client.post('/api/permissions/interpret', json={'sentence':args.sentence})
    print(response.status_code)
    print(response.text)
