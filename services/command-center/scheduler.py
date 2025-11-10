# services/command-center/scheduler.py
from datetime import datetime, timedelta


class Job:
    def __init__(self, id, name, paused=False):
        self.id = id
        self.name = name
        self.paused = paused
        self.next_run_time = datetime.utcnow() + timedelta(minutes=15)


_jobs = [
    Job("daily-import", "Daily Import"),
    Job("rebuild-metrics", "Rebuild Metrics", paused=True),
    Job("health-check", "Health Check"),
    Job("data-sync", "Data Synchronization"),
    Job("backup", "Database Backup"),
]


def get_all_jobs():
    return _jobs


def pause_job(job_id: str):
    for j in _jobs:
        if j.id == job_id:
            j.paused = True
            return j
    raise ValueError("Job not found")


def resume_job(job_id: str):
    for j in _jobs:
        if j.id == job_id:
            j.paused = False
            return j
    raise ValueError("Job not found")
