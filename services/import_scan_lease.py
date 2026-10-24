"""Internal scanner fencing; manual imports do not create or accept a claim.

Expiry is a hard boundary, not a hint: an expired token cannot renew itself.
The writer lock and both ownership checks span the entire business transaction.
"""

import logging
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import timedelta


class ScanLeaseLost(RuntimeError):
    code = 'SCAN_LEASE_LOST'


class LeaseKeeper:
    """Renew during hashing/parsing; serialize our heartbeat with our writer."""

    def __init__(self, renew, interval):
        self.renew = renew
        self.interval = interval
        self.lock = threading.RLock()
        self.stop = threading.Event()
        self.failure = None
        self.thread = None

    def check(self):
        if self.failure:
            raise ScanLeaseLost(self.failure)

    def pulse(self):
        with self.lock:
            self.check()
            try:
                if not self.renew():
                    raise ScanLeaseLost('scan lease expired or changed owner')
            except Exception as error:
                self.failure = f'SCAN_LEASE_LOST: renewal failed: {error}'
                logging.getLogger(__name__).warning(self.failure)
                raise ScanLeaseLost(self.failure) from error

    def _run(self):
        while not self.stop.wait(self.interval):
            try:
                self.pulse()
            except ScanLeaseLost:
                return

    def start(self):
        self.thread = threading.Thread(target=self._run, name='import-scan-lease', daemon=True)
        self.thread.start()
        return self

    def close(self):
        self.stop.set()
        if self.thread:
            self.thread.join()


@dataclass(frozen=True)
class ScanClaim:
    job_id: int
    file_id: int
    token: str
    shop_id: str
    source_hash: str
    preview_id: str
    keeper: LeaseKeeper
    clock: object
    lease_seconds: int

    def validate(self, connection, batch):
        self.keeper.check()
        now = self.clock().replace(microsecond=0)
        row = connection.execute(
            '''SELECT f.source_hash, f.lease_token AS file_token, f.status AS file_status,
                      f.batch_id, f.source_filename, j.lease_token AS job_token,
                      j.lease_until, j.enabled, j.shop_id, j.source_type
               FROM import_scan_files f JOIN import_scan_jobs j ON j.id=f.job_id
               WHERE f.id=? AND j.id=?''', (self.file_id, self.job_id),
        ).fetchone()
        if (row is None or not self.token or not row['enabled']
                or row['job_token'] != self.token or row['file_token'] != self.token
                or row['file_status'] != 'importing' or row['batch_id'] is not None
                or not row['lease_until'] or row['lease_until'] <= now.isoformat()
                or str(row['shop_id']) != self.shop_id
                or str(batch.get('shop_id') or 'default') != self.shop_id
                or row['source_hash'] != self.source_hash or batch['source_hash'] != self.source_hash
                or row['source_type'] != batch['source_type']
                or row['source_filename'] != batch['source_filename']):
            raise ScanLeaseLost('SCAN_LEASE_LOST: job/file claim is expired, superseded or mismatched')
        # This renewal is part of the business transaction. No competing writer
        # can take the job between validation and commit (BEGIN IMMEDIATE).
        connection.execute('UPDATE import_scan_jobs SET lease_until=?, updated_at=? WHERE id=?',
                           ((now + timedelta(seconds=self.lease_seconds)).isoformat(), now.isoformat(), self.job_id))
        connection.execute('UPDATE import_scan_files SET updated_at=? WHERE id=?',
                           (now.isoformat(), self.file_id))

    @contextmanager
    def transaction(self, connection, batch):
        with self.keeper.lock:
            try:
                connection.execute('BEGIN IMMEDIATE')
                self.validate(connection, batch)
                yield
            except BaseException:
                connection.rollback()
                raise

    def finish(self, connection, batch):
        self.validate(connection, batch)
        # Batch + fact + file terminal marker are one durable commit. A crash
        # after commit can lose the run counter, but cannot duplicate this file.
        connection.execute(
            """UPDATE import_scan_files SET status='imported', batch_id=?, preview_id=?,
               imported_at=?, updated_at=?, error_code=NULL, error_message=NULL WHERE id=?""",
            (batch['id'], self.preview_id, self.clock().isoformat(), self.clock().isoformat(), self.file_id),
        )
