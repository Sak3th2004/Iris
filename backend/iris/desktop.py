"""Latest authenticated VM browser frame, shared by the two server processes."""
import time
from .models import Model
from pydantic import Field

class WorkerEvent(Model):
    action: str = Field(max_length=40)
    detail: str = Field(max_length=300)

class Desktop:
    STALE_SECONDS = 5
    MAX_FRAME_BYTES = 1_500_000

    def __init__(self, store):
        self.store = store
        with store.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS desktop(id INTEGER PRIMARY KEY CHECK(id=1), frame BLOB NOT NULL, received REAL NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS worker_events(id INTEGER PRIMARY KEY AUTOINCREMENT, job_id TEXT, action TEXT, detail TEXT, received REAL)')

    def publish(self, frame):
        if not 4 <= len(frame) <= self.MAX_FRAME_BYTES or not frame.startswith(b'\xff\xd8') or not frame.endswith(b'\xff\xd9'):
            raise ValueError('Expected a bounded JPEG browser frame.')
        with self.store.connect() as db:
            db.execute('INSERT INTO desktop VALUES(1,?,?) ON CONFLICT(id) DO UPDATE SET frame=excluded.frame,received=excluded.received',(frame,time.time()))

    def status(self):
        with self.store.connect() as db:
            row = db.execute('SELECT received FROM desktop WHERE id=1').fetchone()
        age = max(0,time.time()-row['received']) if row else None
        return {'connected':age is not None and age < self.STALE_SECONDS,'age_seconds':round(age,1) if age is not None else None,'source':'VM browser viewport','received_at':row['received'] if row else None}

    def frame(self):
        with self.store.connect() as db:
            row = db.execute('SELECT frame,received FROM desktop WHERE id=1').fetchone()
        if not row or time.time()-row['received'] >= self.STALE_SECONDS: return None
        return bytes(row['frame'])

    def event(self, job_id, action, detail):
        with self.store.connect() as db:
            db.execute('INSERT INTO worker_events(job_id,action,detail,received) VALUES(?,?,?,?)',(job_id,action,detail,time.time()))

    def events(self, job_id):
        with self.store.connect() as db:
            return [dict(r) for r in db.execute('SELECT * FROM worker_events WHERE job_id=? ORDER BY id DESC LIMIT 40',(job_id,))]
