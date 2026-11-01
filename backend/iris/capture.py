"""Server-side record snapshot taken before microphone capture, never client supplied."""
import json
import time
from uuid import uuid4

CAPTURE_SECONDS = 600


class Captures:
    def __init__(self, store):
        self.store = store

    def start(self, parent_id=None):
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            id, now = str(uuid4()), time.time()
            root, messages, expires = id, [], now+CAPTURE_SECONDS
            if parent_id:
                parent = self.get(parent_id,db=db)
                root, messages = self._thread(parent_id,db)
                if not messages or messages[-1]['role'] != 'assistant':
                    raise ValueError('A follow-up must answer an Iris clarification question.')
                if len(messages) >= 12:
                    raise ValueError('Too many clarification turns. Start a fresh instruction.')
                rows, now, expires = parent['records'], parent['captured_at'], parent['expires_at']
            else:
                rows = [dict(resource_type=r['resource'], record_id=r['id'], fields=json.loads(r['fields']), version=r['version'])
                        for r in db.execute('SELECT * FROM records ORDER BY resource,id')]
            db.execute('INSERT INTO instruction_captures VALUES(?,?,?,?,?,NULL)', (id,json.dumps(rows),now,expires,'captured'))
            db.execute('INSERT INTO capture_threads VALUES(?,?,?)',(id,root,json.dumps(messages)))
            return {'capture_id':id, 'captured_at':now, 'expires_at':expires}

    def _thread(self,id,db):
        row=db.execute('SELECT root_id,messages FROM capture_threads WHERE capture_id=?',(id,)).fetchone()
        if row: return row['root_id'],json.loads(row['messages'])
        capture=self.get(id,db=db)
        return id,[{'role':'user','text':capture['transcript']}] if capture['transcript'] else []

    def instruction(self,id):
        with self.store.connect() as db:
            self.get(id,db=db)
            _,messages=self._thread(id,db)
            if len(messages)==1: return messages[0]['text']
            return '\n'.join(('Person' if m['role']=='user' else 'Iris')+': '+m['text'] for m in messages)

    def ask(self,id,question):
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            self.get(id,db=db)
            root,messages=self._thread(id,db)
            if messages and messages[-1]['role']=='assistant': messages.pop()
            messages.append({'role':'assistant','text':question})
            db.execute('INSERT OR REPLACE INTO capture_threads VALUES(?,?,?)',(id,root,json.dumps(messages)))

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
            root,messages=self._thread(id,db)
            messages.append({'role':'user','text':sentence.strip()})
            if sum(len(m['text']) for m in messages)>8000:
                raise ValueError('The instruction is too long. Start a fresh instruction.')
            db.execute('INSERT OR REPLACE INTO capture_threads VALUES(?,?,?)',(id,root,json.dumps(messages)))
            db.execute("UPDATE instruction_captures SET state='ready',transcript=? WHERE id=?",(sentence.strip(),id))
        return {'sentence':sentence.strip(),'capture_id':id}

    def fail(self,id):
        with self.store.connect() as db:
            db.execute("UPDATE instruction_captures SET state='failed' WHERE id=? AND state='transcribing'",(id,))

    def consume(self,id,resource,record_id,version,db):
        capture=self.get(id,db=db)
        if not any(r['resource_type']==resource and r['record_id']==record_id and r['version']==version for r in capture['records']):
            raise ValueError('The record was not in the recording-start snapshot. Record again.')
        root,_=self._thread(id,db)
        db.execute("UPDATE instruction_captures SET state='used' WHERE id=? OR id IN (SELECT capture_id FROM capture_threads WHERE root_id=?)",(root,root))
