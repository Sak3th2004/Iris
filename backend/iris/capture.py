"""Server-side record snapshot taken before microphone capture, never client supplied."""
import json
import time
from uuid import uuid4

CAPTURE_SECONDS = 600


class Captures:
    def __init__(self, store):
        self.store = store

    def start(self):
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            rows = [dict(resource_type=r['resource'], record_id=r['id'], fields=json.loads(r['fields']), version=r['version'])
                    for r in db.execute('SELECT * FROM records ORDER BY resource,id')]
            id, now = str(uuid4()), time.time()
            db.execute('INSERT INTO instruction_captures VALUES(?,?,?,?,?,NULL)', (id,json.dumps(rows),now,now+CAPTURE_SECONDS,'captured'))
            return {'capture_id':id, 'captured_at':now, 'expires_at':now+CAPTURE_SECONDS}

    def get(self, id, *, state='ready', db=None):
        if db is None:
            with self.store.connect() as conn: return self.get(id,state=state,db=conn)
        row = db.execute('SELECT * FROM instruction_captures WHERE id=?',(id,)).fetchone()
        if not row or row['state'] != state or row['expires_at'] <= time.time():
            raise ValueError('Recording snapshot expired, was already used, or is not ready. Record a fresh instruction.')
        return dict(row) | {'records':json.loads(row['records'])}

    def begin_transcription(self,id):
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            self.get(id,state='captured',db=db)
            db.execute("UPDATE instruction_captures SET state='transcribing' WHERE id=?",(id,))

    def complete(self,id,sentence):
        if not isinstance(sentence,str) or not 3 <= len(sentence.strip()) <= 2000:
            raise ValueError('No usable instruction was transcribed. Record again.')
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            self.get(id,state='transcribing',db=db)
            db.execute("UPDATE instruction_captures SET state='ready',transcript=? WHERE id=?",(sentence.strip(),id))
        return {'sentence':sentence.strip(),'capture_id':id}

    def fail(self,id):
        with self.store.connect() as db:
            db.execute("UPDATE instruction_captures SET state='failed' WHERE id=? AND state='transcribing'",(id,))

    def consume(self,id,resource,record_id,version,db):
        capture=self.get(id,db=db)
        if not any(r['resource_type']==resource and r['record_id']==record_id and r['version']==version for r in capture['records']):
            raise ValueError('The record was not in the recording-start snapshot. Record again.')
        db.execute("UPDATE instruction_captures SET state='used' WHERE id=?",(id,))
