"""Standard-mode Meta client. No paid calls without a key; no automatic retries."""
import io
import json
import os
import wave
from uuid import uuid4
import httpx


class Meta:
    def __init__(self, store):
        self.store = store
        self.key = os.getenv('MODEL_API_KEY', '')
        self.limit = min(float(os.getenv('IRIS_SPEND_LIMIT_USD', '149.99')), 149.99)

    def status(self):
        with self.store.connect() as db:
            spent = db.execute('SELECT COALESCE(SUM(COALESCE(actual,reserved)),0) FROM spend').fetchone()[0]
        return {'configured': bool(self.key), 'committed_usd': round(spent, 6), 'limit_usd':self.limit, 'model':'muse-spark-1.3', 'mode':'Standard'}

    def reserve(self, amount, purpose):
        if not self.key:
            raise ValueError('Add MODEL_API_KEY to .env and restart to enable Muse Spark and voice.')
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            spent = db.execute('SELECT COALESCE(SUM(COALESCE(actual,reserved)),0) FROM spend').fetchone()[0]
            if spent + amount > self.limit:
                raise ValueError('The configured spending limit has been reached. No model call was made.')
            id = str(uuid4())
            db.execute('INSERT INTO spend VALUES(?,?,NULL,?)', (id, amount, purpose))
            return id

    def settle(self, id, cost):
        with self.store.connect() as db:
            db.execute('UPDATE spend SET actual=? WHERE id=?', (cost, id))

    async def json(self, system, data, purpose):
        messages = [{'role':'system','content':system}, {'role':'user','content':json.dumps(data)}]
        encoded = json.dumps(messages).encode()
        if len(encoded) > 24000:
            raise ValueError('Context is too large. Narrow this task.')
        # Conservative reservation: byte count bounds input tokens, plus fixed output cap.
        reservation = (len(encoded) + 2048) * 1.25 / 1e6 + 4096 * 4.25 / 1e6
        id = self.reserve(reservation, purpose)
        async with httpx.AsyncClient(timeout=90) as client:
            response = await client.post('https://api.meta.ai/v1/chat/completions', headers={'Authorization':f'Bearer {self.key}'}, json={
                'model':'muse-spark-1.3','messages':messages,'max_completion_tokens':4096,'response_format':{'type':'json_object'}})
        if response.status_code != 200:
            raise ValueError(f'Meta returned HTTP {response.status_code}. Nothing was saved; no automatic retry.')
        body = response.json()
        usage = body.get('usage', {})
        if 'prompt_tokens' in usage and 'completion_tokens' in usage:
            self.settle(id, (usage['prompt_tokens'] * 1.25 + usage['completion_tokens'] * 4.25) / 1e6)
        try:
            return json.loads(body['choices'][0]['message']['content'])
        except (KeyError, IndexError, TypeError, json.JSONDecodeError):
            raise ValueError('Muse returned an incomplete response. Please ask again.') from None

    async def transcribe(self, audio):
        try:
            with wave.open(io.BytesIO(audio)) as wav:
                seconds = wav.getnframes() / wav.getframerate()
                if wav.getnchannels() != 1 or wav.getsampwidth() != 2 or wav.getframerate() not in (16000,24000) or not 0 < seconds <= 60:
                    raise ValueError('Record up to 60 seconds of mono, 16-bit WAV at 16 or 24 kHz.')
        except (wave.Error, EOFError):
            raise ValueError('A valid PCM WAV recording is required.') from None
        id = self.reserve(seconds * .18 / 3600, 'voice')
        async with httpx.AsyncClient(timeout=90) as client:
            response = await client.post('https://api.meta.ai/v1/asr/transcribe', headers={'Authorization':f'Bearer {self.key}'}, files={
                'request':(None,json.dumps({'mode':'PUSH_TO_TALK','model':'muse-voice-transcribe-1.0','audioEncoding':'WAV'}),'application/json'),
                'audio':('instruction.wav',audio,'audio/wav')})
        if response.status_code != 200:
            raise ValueError(f'Voice returned HTTP {response.status_code}. No instruction was submitted.')
        self.settle(id, seconds * .18 / 3600)
        return response.json()['transcript']
