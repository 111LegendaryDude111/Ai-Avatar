from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from .config import settings
from .models import JobStatus


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class Job:
    job_id: str
    status: JobStatus
    created_at: datetime
    updated_at: datetime
    progress: float
    message: str | None
    error: str | None
    input_image_path: Path
    input_audio_path: Path
    output_video_path: Path
    options: dict[str, Any]


class JobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = asyncio.Lock()

    async def create(
        self,
        *,
        job_id: str | None = None,
        input_image_path: Path,
        input_audio_path: Path,
        output_video_path: Path,
        options: dict[str, Any],
    ) -> Job:
        job_id = job_id or str(uuid4())
        now = _utcnow()
        job = Job(
            job_id=job_id,
            status=JobStatus.queued,
            created_at=now,
            updated_at=now,
            progress=0.0,
            message="Queued",
            error=None,
            input_image_path=input_image_path,
            input_audio_path=input_audio_path,
            output_video_path=output_video_path,
            options=options,
        )
        async with self._lock:
            self._jobs[job_id] = job
        return job

    async def get(self, job_id: str) -> Job | None:
        async with self._lock:
            return self._jobs.get(job_id)

    async def update(
        self,
        job_id: str,
        *,
        status: JobStatus | None = None,
        progress: float | None = None,
        message: str | None = None,
        error: str | None = None,
    ) -> Job | None:
        async with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            if status is not None:
                job.status = status
            if progress is not None:
                job.progress = float(progress)
            if message is not None:
                job.message = message
            if error is not None:
                job.error = error
            job.updated_at = _utcnow()
            return job


class JobQueue:
    def __init__(self) -> None:
        self._queue: asyncio.Queue[str] = asyncio.Queue()

    async def enqueue(self, job_id: str) -> None:
        await self._queue.put(job_id)

    async def dequeue(self) -> str:
        return await self._queue.get()


def storage_paths_for_job(job_id: str) -> dict[str, Path]:
    base = settings.storage_dir
    uploads = base / settings.uploads_dirname / job_id
    outputs = base / settings.outputs_dirname / job_id
    return {
        "uploads_dir": uploads,
        "outputs_dir": outputs,
        "image_path": uploads / "image",
        "audio_path": uploads / "audio",
        "video_path": outputs / "result.mp4",
        "meta_path": outputs / "job.json",
    }


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def persist_job_meta(job: Job) -> None:
    paths = storage_paths_for_job(job.job_id)
    ensure_dir(paths["outputs_dir"])
    meta = {
        "job_id": job.job_id,
        "status": job.status,
        "created_at": job.created_at.isoformat(),
        "updated_at": job.updated_at.isoformat(),
        "progress": job.progress,
        "message": job.message,
        "error": job.error,
        "input_image_path": str(job.input_image_path),
        "input_audio_path": str(job.input_audio_path),
        "output_video_path": str(job.output_video_path),
        "options": job.options,
    }
    paths["meta_path"].write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
