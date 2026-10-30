"""Polly neural replies, bounded separately from model spending."""
import os
import math
from uuid import uuid4


class Speech:
    def __init__(self,store):
        self.store=store
        limit=float(os.getenv('IRIS_VOICE_ALLOWANCE_USD','2'))
        if not math.isfinite(limit) or not 0<=limit<=10: raise ValueError('Voice allowance must be between $0 and $10.')
        self.limit=limit
        with store.connect() as db: db.execute('CREATE TABLE IF NOT EXISTS voice_spend(id TEXT PRIMARY KEY,reserved REAL,characters INTEGER)')

    def status(self):
        with self.store.connect() as db: reserved=db.execute('SELECT COALESCE(SUM(reserved),0) FROM voice_spend').fetchone()[0]
        return {'configured':bool(os.getenv('AWS_ACCESS_KEY_ID') and os.getenv('AWS_SECRET_ACCESS_KEY')),'provider':'Amazon Polly','voice':'Joanna','engine':'neural','reserved_allowance_usd':round(reserved,6),'limit_usd':self.limit}

    def synthesize(self,text):
        if not self.status()['configured']: raise ValueError('Configure the local AWS credentials to enable spoken replies.')
        if not 1<=len(text)<=2500: raise ValueError('Spoken replies must contain 1 to 2500 characters.')
        # Conservative allowance, not a provider invoice: $100 per million characters.
        # Intentionally keeps headroom and does not assume credits/free-tier eligibility.
        reserve=len(text)*.0001
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            spent=db.execute('SELECT COALESCE(SUM(reserved),0) FROM voice_spend').fetchone()[0]
            if spent+reserve>self.limit: raise ValueError('The voice development allowance is reached.')
            db.execute('INSERT INTO voice_spend VALUES(?,?,?)',(str(uuid4()),reserve,len(text)))
        import boto3
        from botocore.config import Config
        from botocore.exceptions import BotoCoreError, ClientError
        try:
            client=boto3.client('polly',region_name=os.getenv('AWS_REGION','us-east-1'),config=Config(connect_timeout=8,read_timeout=30,retries={'total_max_attempts':1}))
            response=client.synthesize_speech(Text=text,TextType='text',VoiceId='Joanna',Engine='neural',OutputFormat='mp3',SampleRate='24000')
            with response['AudioStream'] as stream: return stream.read()
        except (BotoCoreError,ClientError):
            raise ValueError('Polly could not produce this reply. Check AWS access and region; no automatic retry.') from None
