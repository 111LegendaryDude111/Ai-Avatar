from __future__ import annotations

from .jobs import JobQueue, JobStore

job_store = JobStore()
job_queue = JobQueue()

