import os
import threading
from datetime import datetime
from typing import Dict, Any, Optional
from contextlib import contextmanager

from app.core.database import get_db
from app.core.scheduler import scheduler as task_scheduler
from app.core.logger import get_logger
from app.services import SmartImportService, SettingService
from app.models import SystemSetting

logger = get_logger(__name__)


class ScheduledScanner:

    def __init__(self):
        self.jobs = {}
        self.job_history = []
        self._lock = threading.Lock()

    def start(self):
        logger.info("Scheduled scanner initialized (using global scheduler)")

    def stop(self):
        for job_id in list(self.jobs.keys()):
            try:
                task_scheduler.remove_task(f"scan_{job_id}")
            except Exception:
                pass
        logger.info("Scheduled scanner stopped")

    def add_scan_job(
        self,
        job_id: str,
        folder_path: str,
        cron_expression: str,
        auto_import: bool = False,
        file_types: list = None
    ) -> Dict[str, Any]:
        existing = self.jobs.get(job_id)
        if existing:
            try:
                task_scheduler.remove_task(f"scan_{job_id}")
            except Exception:
                pass

        def scan_job():
            self._execute_scan_job(job_id, folder_path, auto_import, file_types)

        task_scheduler.add_cron_task(
            func=scan_job,
            cron=cron_expression,
            id=f"scan_{job_id}"
        )

        jobs = task_scheduler.get_jobs()
        next_run = None
        for job in jobs:
            if job.id == f"scan_{job_id}":
                next_run = str(job.next_run_time) if job.next_run_time else None
                break

        job_info = {
            "job_id": job_id,
            "folder_path": folder_path,
            "cron_expression": cron_expression,
            "auto_import": auto_import,
            "file_types": file_types or [],
            "next_run": next_run,
            "created_at": datetime.now().isoformat()
        }

        self.jobs[job_id] = job_info

        return job_info

    def remove_scan_job(self, job_id: str) -> bool:
        try:
            task_scheduler.remove_task(f"scan_{job_id}")
            if job_id in self.jobs:
                del self.jobs[job_id]
            return True
        except Exception:
            return False

    def get_jobs(self) -> list:
        result = []
        for job_id, job_info in self.jobs.items():
            jobs = task_scheduler.get_jobs()
            for job in jobs:
                if job.id == f"scan_{job_id}":
                    job_info["next_run"] = str(job.next_run_time) if job.next_run_time else None
                    job_info["status"] = "running"
                    break
            result.append(job_info.copy())
        return result

    def get_job_history(self, job_id: str = None, limit: int = 50) -> list:
        with self._lock:
            if job_id:
                return [h for h in self.job_history if h.get("job_id") == job_id][:limit]
            return list(self.job_history[:limit])

    @contextmanager
    def _get_db_session(self):
        db = db
        try:
            yield db
        except Exception:
            db.rollback()
            raise
        finally:
    def _execute_scan_job(
        self,
        job_id: str,
        folder_path: str,
        auto_import: bool,
        file_types: list
    ):
        with self._get_db_session() as db:
            try:
                service = SmartImportService(db)

                history_record = {
                    "job_id": job_id,
                    "folder_path": folder_path,
                    "started_at": datetime.now().isoformat(),
                    "status": "running",
                    "files_found": 0,
                    "files_imported": 0,
                    "errors": []
                }

                if not os.path.exists(folder_path):
                    history_record["status"] = "failed"
                    history_record["errors"].append(f"文件夹不存在: {folder_path}")
                    self._add_history(history_record)
                    return

                files = service.scan_folder(folder_path)

                if file_types:
                    files = [f for f in files if f.get("file_type") in file_types]

                history_record["files_found"] = len(files)

                if auto_import:
                    for file_info in files:
                        if file_info.get("can_import"):
                            try:
                                result = service.smart_import(
                                    file_info["filepath"],
                                    file_info["file_type"]
                                )
                                if result.get("success"):
                                    history_record["files_imported"] += 1
                                else:
                                    history_record["errors"].append(
                                        f"{file_info['filename']}: {result.get('message')}"
                                    )
                            except Exception as e:
                                history_record["errors"].append(
                                    f"{file_info['filename']}: {str(e)}"
                                )

                history_record["status"] = "completed"
                history_record["completed_at"] = datetime.now().isoformat()

            except Exception as e:
                history_record["status"] = "failed"
                history_record["errors"].append(str(e))

            self._add_history(history_record)

    def _add_history(self, record):
        with self._lock:
            self.job_history.insert(0, record)
            if len(self.job_history) > 100:
                self.job_history = self.job_history[:100]

    def trigger_manual_scan(
        self,
        folder_path: str,
        auto_import: bool = False,
        file_types: list = None
    ) -> Dict[str, Any]:
        job_id = f"manual-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        self._execute_scan_job(job_id, folder_path, auto_import, file_types)

        with self._lock:
            if self.job_history:
                return self.job_history[0]
        return {"status": "unknown"}


scanner = ScheduledScanner()
