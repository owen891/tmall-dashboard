import asyncio
from datetime import datetime
from typing import Callable, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from .logger import get_logger

logger = get_logger(__name__)


class TaskScheduler:
    """定时任务调度器"""

    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self._running = False

    def start(self):
        if not self._running:
            self.scheduler.start()
            self._running = True
            logger.info("Task scheduler started")

    def shutdown(self):
        if self._running:
            self.scheduler.shutdown()
            self._running = False
            logger.info("Task scheduler stopped")

    def add_interval_task(
        self,
        func: Callable,
        seconds: int = 60,
        minutes: int = 0,
        hours: int = 0,
        id: Optional[str] = None,
        **kwargs,
    ):
        trigger = IntervalTrigger(seconds=seconds, minutes=minutes, hours=hours)
        self.scheduler.add_job(
            func, trigger=trigger, id=id, kwargs=kwargs, replace_existing=True
        )
        logger.info(f"Added interval task: {id or func.__name__}")

    def add_cron_task(
        self,
        func: Callable,
        cron: str,
        id: Optional[str] = None,
        **kwargs,
    ):
        parts = cron.split()
        if len(parts) != 5:
            raise ValueError("Cron expression must have 5 parts")
        trigger = CronTrigger(
            minute=parts[0],
            hour=parts[1],
            day=parts[2],
            month=parts[3],
            day_of_week=parts[4],
        )
        self.scheduler.add_job(
            func, trigger=trigger, id=id, kwargs=kwargs, replace_existing=True
        )
        logger.info(f"Added cron task: {id or func.__name__}")

    def remove_task(self, id: str):
        self.scheduler.remove_job(id)
        logger.info(f"Removed task: {id}")

    def get_jobs(self):
        return self.scheduler.get_jobs()


# 全局调度器实例
scheduler = TaskScheduler()
