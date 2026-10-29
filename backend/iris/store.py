import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from uuid import uuid4
from .gate import decide
from .models import Permission, Proposal, Record
from .lifecycle import recover_jobs, owns_lease
from .capture import Captures

SEED = [
    ("booking", "bk-alice", {"name": "Alice Morgan", "day": "Tuesday", "time": "10:00", "service": "Design consultation", "price": 120}),
    ("booking", "bk-bob", {"name": "Bob Chen", "day": "Wednesday", "time": "14:30", "service": "Strategy session", "price": 180}),
    ("booking", "bk-priya", {"name": "Priya Shah", "day": "Friday", "time": "11:00", "service": "Portfolio review", "price": 90}),
    ("order", "or-alice", {"name": "Alice Morgan", "item": "Ceramic pour-over", "quantity": 1, "price": 48}),
    ("order", "or-bob", {"name": "Bob Chen", "item": "Studio mug", "quantity": 2, "price": 64}),
    ("order", "or-priya", {"name": "Priya Shah", "item": "Linen journal", "quantity": 1, "price": 28}),
]


class Store:
    def __init__(self, path):
        self.path = str(path)
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS records(resource TEXT, id TEXT, fields TEXT NOT NULL, version INTEGER NOT NULL, PRIMARY KEY(resource,id));
                CREATE TABLE IF NOT EXISTS permissions(id TEXT PRIMARY KEY, body TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1);
                CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY AUTOINCREMENT, time TEXT, proposal TEXT, decision TEXT, before_row TEXT, after_row TEXT);
                CREATE TABLE IF NOT EXISTS spend(id TEXT PRIMARY KEY, reserved REAL NOT NULL, actual REAL, purpose TEXT);
                CREATE TABLE IF NOT EXISTS baseten_spend(id TEXT PRIMARY KEY, reserved REAL NOT NULL, actual REAL, purpose TEXT);
                CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, permission_id TEXT, state TEXT, steps INTEGER DEFAULT 0, detail TEXT);
                CREATE TABLE IF NOT EXISTS job_leases(job_id TEXT PRIMARY KEY, worker_id TEXT, expires_at REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS job_receipts(job_id TEXT PRIMARY KEY, body TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS instruction_captures(id TEXT PRIMARY KEY, records TEXT NOT NULL, captured_at REAL NOT NULL, expires_at REAL NOT NULL, state TEXT NOT NULL, transcript TEXT);
            ''')
            for resource, id, fields in SEED:
                db.execute("INSERT OR IGNORE INTO records VALUES(?,?,?,1)", (resource, id, json.dumps(fields)))

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def _get(self, db, resource, id):
        row = db.execute("SELECT * FROM records WHERE resource=? AND id=?", (resource, id)).fetchone()
        return Record(resource_type=row['resource'], record_id=row['id'], fields=json.loads(row['fields']), version=row['version']) if row else None

    def get(self, resource, id):
        with self.connect() as db:
            return self._get(db, resource, id)

    def records(self):
        with self.connect() as db:
            return [self._get(db, row['resource'], row['id']).model_dump() for row in db.execute("SELECT resource,id FROM records ORDER BY resource,id")]

    def create_record(self, resource, fields):
        # Owner-only setup operation; never an agent tool or an edit bypass.
        id = ('bk-' if resource == 'booking' else 'or-') + str(uuid4())[:12]
        with self.connect() as db:
            db.execute('INSERT INTO records VALUES(?,?,?,1)', (resource,id,json.dumps(fields)))
            return self._get(db,resource,id)

    def lock(self, sentence, resource, id, fields, version, *, capture_id=None):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = self._get(db, resource, id)
            if not row or row.version != version:
                raise ValueError("Record changed while interpreting the instruction. Please ask again.")
            if not fields or any(k not in row.fields or type(v) is not type(row.fields[k]) for k,v in fields.items()):
                raise ValueError("The instruction must specify valid fields and values.")
            if capture_id:
                Captures(self).consume(capture_id,resource,id,version,db)
            permission = Permission(id=str(uuid4()), sentence=sentence, resource_type=resource, record_id=id, set_fields=fields,
                preserve_fields={k:v for k,v in row.fields.items() if k not in fields},
                forbidden_operations=["delete", "cancel", "email", "message", "create"], version=version)
            db.execute("INSERT INTO permissions(id,body) VALUES(?,?)", (permission.id, permission.model_dump_json()))
            return permission

    def permission(self, id, active_only=True):
        with self.connect() as db:
            row = db.execute("SELECT body FROM permissions WHERE id=?" + (" AND active=1" if active_only else ""), (id,)).fetchone()
            return Permission.model_validate_json(row['body']) if row else None

    def submit(self, proposal: Proposal, *, job_id=None, worker_id=None):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            recover_jobs(db)
            p = db.execute("SELECT body FROM permissions WHERE id=? AND active=1", (proposal.permission_id,)).fetchone()
            permission = Permission.model_validate_json(p['body']) if p else None
            bound = db.execute('SELECT id FROM jobs WHERE permission_id=? LIMIT 1', (proposal.permission_id,)).fetchone()
            if bound and (bound['id'] != job_id or not owns_lease(db, job_id, worker_id)):
                permission = None  # Every transport must respect an assigned worker lease.
            before = self._get(db, proposal.resource_type, proposal.record_id)
            decision = decide(permission, proposal, before)  # Exactly one decision, inside the write transaction.
            if decision.verdict == "allow":
                db.execute("UPDATE records SET fields=?,version=version+1 WHERE resource=? AND id=?", (json.dumps(before.fields | proposal.fields), proposal.resource_type, proposal.record_id))
                db.execute("UPDATE permissions SET active=0 WHERE id=?", (permission.id,))
            elif decision.code == "stale_version":
                db.execute("UPDATE permissions SET active=0 WHERE id=?", (permission.id,))
            after = self._get(db, proposal.resource_type, proposal.record_id)
            db.execute("INSERT INTO audit(time,proposal,decision,before_row,after_row) VALUES(?,?,?,?,?)", (
                datetime.now(timezone.utc).isoformat(), proposal.model_dump_json(), decision.model_dump_json(),
                before.model_dump_json() if before else 'null', after.model_dump_json() if after else 'null'))
            result = {"decision": decision.model_dump(), "before": before.model_dump() if before else None, "after": after.model_dump() if after else None}
            if job_id and bound and bound['id'] == job_id:
                if decision.verdict == 'allow':
                    db.execute('INSERT INTO job_receipts VALUES(?,?)', (job_id,json.dumps(result)))
                    db.execute("UPDATE jobs SET state='complete',detail=? WHERE id=?", (decision.reason,job_id))
                elif decision.code == 'stale_version':
                    db.execute("UPDATE jobs SET state='paused',detail=? WHERE id=? AND state='running'", (decision.reason,job_id))
            return result

    def audit(self):
        with self.connect() as db:
            return [{"id": r['id'], "time": r['time'], **{k:json.loads(r[k]) for k in ('proposal','decision','before_row','after_row')}} for r in db.execute("SELECT * FROM audit ORDER BY id DESC LIMIT 200")]
