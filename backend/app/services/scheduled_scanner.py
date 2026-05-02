import os
import json
import threading
import time
from datetime import datetime
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core import get_db
from app.services import SmartImportService, SettingService
from app.models import SystemSetting


class ScheduledScanner:
    """定时扫描任务管理器"""
    
    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.jobs = {}
        self.job_history = []
    
    def start(self):
        """启动调度器"""
        if not self.scheduler.running:
            self.scheduler.start()
            print("定时扫描服务已启动")
    
    def stop(self):
        """停止调度器"""
        if self.scheduler.running:
            self.scheduler.shutdown()
            print("定时扫描服务已停止")
    
    def add_scan_job(
        self,
        job_id: str,
        folder_path: str,
        cron_expression: str,
        auto_import: bool = False,
        file_types: list = None
    ) -> Dict[str, Any]:
        """添加定时扫描任务"""
        if self.scheduler.get_job(job_id):
            self.scheduler.remove_job(job_id)
        
        def scan_job():
            self._execute_scan_job(job_id, folder_path, auto_import, file_types)
        
        parts = cron_expression.split()
        if len(parts) != 5:
            raise ValueError("cron表达式格式错误，应为5位：分 时 日 月 周")
        
        trigger = CronTrigger(
            minute=parts[0],
            hour=parts[1],
            day=parts[2],
            month=parts[3],
            day_of_week=parts[4]
        )
        
        job = self.scheduler.add_job(
            scan_job,
            trigger=trigger,
            id=job_id,
            name=f"扫描任务-{job_id}",
            replace_existing=True
        )
        
        job_info = {
            "job_id": job_id,
            "folder_path": folder_path,
            "cron_expression": cron_expression,
            "auto_import": auto_import,
            "file_types": file_types or [],
            "next_run": str(job.next_run_time),
            "created_at": datetime.now().isoformat()
        }
        
        self.jobs[job_id] = job_info
        
        return job_info
    
    def remove_scan_job(self, job_id: str) -> bool:
        """移除定时扫描任务"""
        if self.scheduler.get_job(job_id):
            self.scheduler.remove_job(job_id)
            if job_id in self.jobs:
                del self.jobs[job_id]
            return True
        return False
    
    def get_jobs(self) -> list:
        """获取所有任务"""
        result = []
        for job_id, job_info in self.jobs.items():
            job = self.scheduler.get_job(job_id)
            if job:
                job_info["next_run"] = str(job.next_run_time)
                job_info["status"] = "running"
            result.append(job_info)
        return result
    
    def get_job_history(self, job_id: str = None, limit: int = 50) -> list:
        """获取任务执行历史"""
        if job_id:
            return [h for h in self.job_history if h.get("job_id") == job_id][:limit]
        return self.job_history[:limit]
    
    def _execute_scan_job(
        self,
        job_id: str,
        folder_path: str,
        auto_import: bool,
        file_types: list
    ):
        """执行扫描任务"""
        db = next(get_db())
        
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
                self.job_history.insert(0, history_record)
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
        
        finally:
            db.close()
        
        self.job_history.insert(0, history_record)
        
        if len(self.job_history) > 100:
            self.job_history = self.job_history[:100]
    
    def trigger_manual_scan(
        self,
        folder_path: str,
        auto_import: bool = False,
        file_types: list = None
    ) -> Dict[str, Any]:
        """手动触发扫描"""
        job_id = f"manual-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        self._execute_scan_job(job_id, folder_path, auto_import, file_types)
        
        if self.job_history:
            return self.job_history[0]
        return {"status": "unknown"}


scanner = ScheduledScanner()
