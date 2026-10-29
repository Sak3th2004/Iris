"""Lease expiry and recovery, always under the caller's SQLite write lock."""
import time
import json

LEASE_SECONDS = 20
QUEUE_SECONDS = 60


def recover_jobs(db, now=None):
    now = time.time() if now is None else now
    expired = db.execute("""SELECT j.id,j.permission_id FROM jobs j
        LEFT JOIN job_leases l ON l.job_id=j.id
        WHERE j.state IN ('queued','running') AND (l.expires_at IS NULL OR l.expires_at<=?)""", (now,)).fetchall()
    for job in expired:
        # Reconcile older builds that committed a save before marking the job complete.
        receipt = db.execute("""SELECT decision,before_row,after_row FROM audit
            WHERE json_extract(proposal,'$.permission_id')=?
            AND json_extract(decision,'$.verdict')='allow' ORDER BY id DESC LIMIT 1""", (job['permission_id'],)).fetchone()
        if receipt:
            db.execute("UPDATE jobs SET state='complete',detail='Recovered committed save from the database receipt. No replay.' WHERE id=?", (job['id'],))
            result={'decision':json.loads(receipt['decision']),'before':json.loads(receipt['before_row']),'after':json.loads(receipt['after_row'])}
            db.execute('INSERT OR IGNORE INTO job_receipts VALUES(?,?)',(job['id'],json.dumps(result)))
        else:
            db.execute("UPDATE jobs SET state='paused',detail='Worker lease expired. Permission revoked; no saved write found. Review and authorize again.' WHERE id=?", (job['id'],))
        db.execute('UPDATE permissions SET active=0 WHERE id=?', (job['permission_id'],))
    return len(expired)


def owns_lease(db, job_id, worker_id):
    return db.execute("""SELECT 1 FROM jobs j JOIN job_leases l ON l.job_id=j.id
        WHERE j.id=? AND j.state='running' AND l.worker_id=? AND l.expires_at>?""",
        (job_id, worker_id, time.time())).fetchone() is not None
