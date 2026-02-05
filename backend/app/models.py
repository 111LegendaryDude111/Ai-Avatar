from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"


class CreateJobResponse(BaseModel):
    job_id: str
    status: JobStatus


class JobStatusResponse(BaseModel):
    job_id: str
    status: JobStatus
    generator_backend: str
    created_at: datetime
    updated_at: datetime
    progress: float = Field(ge=0.0, le=1.0)
    message: str | None = None
    error: str | None = None
    result_url: str | None = None
