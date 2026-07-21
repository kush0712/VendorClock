"""
Celery application configuration with Beat scheduler for periodic alerts.
"""

from celery import Celery
from celery.schedules import crontab
from app.core.config import settings

celery_app = Celery(
    "vendorclock",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "app.tasks.ingestion_tasks",
        "app.tasks.clock_tasks",
        "app.tasks.alert_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Kolkata",
    enable_utc=True,
    task_track_started=True,
    # Beat schedule — all times in IST (Asia/Kolkata)
    beat_schedule={
        # Daily AP nudge — 9 AM IST
        "daily-ap-nudge": {
            "task": "app.tasks.alert_tasks.send_daily_ap_nudge_task",
            "schedule": crontab(hour=9, minute=0),
        },
        # Weekly CFO report — Monday 8 AM IST
        "weekly-cfo-report": {
            "task": "app.tasks.alert_tasks.send_weekly_cfo_report_task",
            "schedule": crontab(hour=8, minute=0, day_of_week=1),
        },
        # Clock refresh — every hour (recompute days_remaining, update statuses)
        "hourly-clock-refresh": {
            "task": "app.tasks.clock_tasks.refresh_all_clocks",
            "schedule": crontab(minute=0),
        },
        # Annual re-verification check — daily at 7 AM
        "vendor-reverification-check": {
            "task": "app.tasks.clock_tasks.check_vendor_reverification",
            "schedule": crontab(hour=7, minute=0),
        },
    },
)
