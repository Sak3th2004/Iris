import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from uuid import uuid4
from .gate import decide
from .models import Decision, Permission, Proposal, Record
from .lifecycle import recover_jobs, owns_lease
from .capture import Captures
from .schedule import move_to_weekday, overlaps, interval

def booking(name, day, time, service, price):
    fields = {"name": name, "day": day, "time": time, "service": service, "price": price, "host": "Studio", "status": "confirmed", "duration_minutes": 60}
    fields.update(move_to_weekday(fields, day))
    return fields

SEED = [
    ("booking", "bk-alice", booking("Alice Morgan", "Tuesday", "10:00", "Design consultation", 120)),
    ("booking", "bk-bob", booking("Bob Chen", "Wednesday", "14:30", "Strategy session", 180)),
    ("booking", "bk-priya", booking("Priya Shah", "Friday", "11:00", "Portfolio review", 90)),
    ("order", "or-alice", {"name": "Alice Morgan", "item": "Ceramic pour-over", "quantity": 1, "price": 48}),
    ("order", "or-bob", {"name": "Bob Chen", "item": "Studio mug", "quantity": 2, "price": 64}),
    ("order", "or-priya", {"name": "Priya Shah", "item": "Linen journal", "quantity": 1, "price": 28}),
    ("transfer", "tr-amit", {"name": "Amit Sharma", "amount": 4000, "memo": "October retainer", "method": "ACH", "status": "pending"}),
    ("transfer", "tr-neha", {"name": "Neha Verma", "amount": 1875, "memo": "Invoice 4471", "method": "ACH", "status": "pending"}),
    ("transfer", "tr-ravi", {"name": "Ravi Kumar", "amount": 950, "memo": "Design sprint", "method": "Wire", "status": "pending"}),
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
                CREATE TABLE IF NOT EXISTS capture_threads(capture_id TEXT PRIMARY KEY, root_id TEXT NOT NULL, messages TEXT NOT NULL);
            ''')
            db.execute('BEGIN IMMEDIATE')
            for resource, id, fields in SEED:
                db.execute("INSERT OR IGNORE INTO records VALUES(?,?,?,1)", (resource, id, json.dumps(fields)))
            for row in db.execute("SELECT id, fields FROM records WHERE resource='booking'"):
                fields = json.loads(row["fields"])
                if "starts_at" not in fields and fields.get("day"):
                    fields.update(move_to_weekday(fields, fields["day"]))
                    fields.setdefault("host", "Studio")
                    fields.setdefault("status", "confirmed")
                    fields.setdefault("duration_minutes", 60)
                    db.execute("UPDATE records SET fields=?,version=version+1 WHERE resource='booking' AND id=?", (json.dumps(fields), row["id"]))
                    for saved in db.execute('SELECT id,body FROM permissions WHERE active=1').fetchall():
                        permission=Permission.model_validate_json(saved['body'])
                        if permission.resource_type=='booking' and permission.record_id==row['id']:
                            db.execute('UPDATE permissions SET active=0 WHERE id=?',(saved['id'],))
                            db.execute("UPDATE jobs SET state='paused',detail='Booking fields changed during an upgrade. A new permission is required.' WHERE permission_id=? AND state IN ('queued','running')",(saved['id'],))

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
            db.execute('BEGIN IMMEDIATE')
            if resource == 'booking':
                interval(fields)
                if any(overlaps(fields,json.loads(r['fields'])) for r in db.execute("SELECT fields FROM records WHERE resource='booking'")):
                    raise ValueError('That appointment overlaps an existing booking on this host.')
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

    def revoke(self,id):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('UPDATE permissions SET active=0 WHERE id=?',(id,))
            db.execute("UPDATE jobs SET state='stopped',detail='Permission discarded by owner.' WHERE permission_id=? AND state IN ('queued','running')",(id,))

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
            if decision.verdict == "allow" and proposal.resource_type == "booking":
                merged = before.fields | proposal.fields
                try:
                    interval(merged)
                    for other in db.execute("SELECT fields FROM records WHERE resource='booking' AND id!=?", (proposal.record_id,)):
                        if overlaps(merged,json.loads(other['fields'])):
                            decision = Decision(verdict="reject", code="slot_taken", reason="That appointment overlaps an existing booking on this host. Nothing was saved.")
                            break
                except (ValueError,TypeError):
                    decision = Decision(verdict='reject',code='invalid_schedule',reason='The booking has an invalid time or duration. Nothing was saved.')
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
