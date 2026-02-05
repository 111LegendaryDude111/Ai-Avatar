from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from .config import settings
from .models import CreateJobResponse, JobStatus, JobStatusResponse
from .tts_service import ensure_audio_for_request


router = APIRouter(prefix="/api/v1")


def _safe_options(options_raw: str | None) -> dict[str, Any]:
    if not options_raw:
        return {}
    try:
        value = json.loads(options_raw)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid options JSON: {e.msg}") from e
    if not isinstance(value, dict):
        raise HTTPException(status_code=400, detail="Options must be a JSON object")
    return value


@router.post("/jobs", response_model=CreateJobResponse)
async def create_job(
    image: UploadFile = File(...),
    text: str | None = Form(None),
    audio: UploadFile | None = File(None),
    options: str | None = Form(None),
):
    if not image.filename:
        raise HTTPException(status_code=400, detail="Image file is required")

    has_text = bool(text and text.strip())
    has_audio = audio is not None and bool(audio.filename)
    if has_text == has_audio:
        raise HTTPException(status_code=400, detail="Provide exactly one of: text or audio")

    from .state import job_queue, job_store
    from .jobs import ensure_dir, storage_paths_for_job

    job_options = _safe_options(options)
    # Allocate a job id and dedicated folders first.
    from uuid import uuid4

    job_id = str(uuid4())
    paths = storage_paths_for_job(job_id)
    ensure_dir(paths["uploads_dir"])
    ensure_dir(paths["outputs_dir"])

    # Save image.
    image_path = paths["uploads_dir"] / f"image{Path(image.filename).suffix or '.png'}"
    with image_path.open("wb") as f:
        f.write(await image.read())

    # Prepare / save audio.
    audio_path = await ensure_audio_for_request(
        job_id=job_id,
        uploads_dir=paths["uploads_dir"],
        text=(text or "").strip() if has_text else None,
        audio_file=audio if has_audio else None,
    )

    output_video_path = paths["video_path"]

    job = await job_store.create(
        job_id=job_id,
        input_image_path=image_path,
        input_audio_path=audio_path,
        output_video_path=output_video_path,
        options=job_options,
    )

    await job_queue.enqueue(job.job_id)
    return CreateJobResponse(job_id=job.job_id, status=job.status)


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job(job_id: str):
    from .state import job_store

    job = await job_store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    result_url = None
    if job.status == JobStatus.succeeded:
        result_url = f"/api/v1/jobs/{job_id}/result"

    return JobStatusResponse(
        job_id=job.job_id,
        status=job.status,
        generator_backend=settings.generator_backend,
        created_at=job.created_at,
        updated_at=job.updated_at,
        progress=job.progress,
        message=job.message,
        error=job.error,
        result_url=result_url,
    )


@router.get("/jobs/{job_id}/result")
async def get_job_result(job_id: str):
    from .state import job_store

    job = await job_store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != JobStatus.succeeded:
        raise HTTPException(status_code=409, detail=f"Job is not ready (status={job.status})")
    if not job.output_video_path.exists():
        raise HTTPException(status_code=500, detail="Result file is missing on server")

    return FileResponse(
        path=str(job.output_video_path),
        media_type="video/mp4",
        filename=f"{job_id}.mp4",
    )
