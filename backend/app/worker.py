from __future__ import annotations

import asyncio
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

from .config import settings
from .jobs import persist_job_meta
from .models import JobStatus
from .pipeline.factory import build_generator
from .state import job_queue, job_store


def _hash_file(hasher: "hashlib._Hash", path: Path) -> None:
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            hasher.update(chunk)


def _cache_key(image_path: Path, audio_path: Path, options: dict[str, Any]) -> str:
    hasher = hashlib.sha256()
    hasher.update(b"avatar-video:v1\0")
    hasher.update(b"backend\0")
    hasher.update(settings.generator_backend.encode("utf-8"))
    hasher.update(b"\0backend-config\0")
    if settings.generator_backend == "sadtalker":
        backend_cfg = {
            "sadtalker_repo_dir": str(settings.sadtalker_repo_dir),
            "sadtalker_python": str(settings.sadtalker_python) if settings.sadtalker_python else None,
            "sadtalker_size": settings.sadtalker_size,
            "sadtalker_preprocess": settings.sadtalker_preprocess,
            "sadtalker_enhancer": settings.sadtalker_enhancer,
        }
    elif settings.generator_backend == "svd":
        backend_cfg = {
            "svd_model": settings.svd_model,
            "svd_revision": settings.svd_revision,
            "svd_variant": settings.svd_variant,
            "svd_local_files_only": settings.svd_local_files_only,
            "svd_device": settings.svd_device,
            "svd_dtype": settings.svd_dtype,
            "svd_width": settings.svd_width,
            "svd_height": settings.svd_height,
            "svd_fps": settings.svd_fps,
            "svd_num_frames": settings.svd_num_frames,
            "svd_num_inference_steps": settings.svd_num_inference_steps,
            "svd_motion_bucket_id": settings.svd_motion_bucket_id,
            "svd_noise_aug_strength": settings.svd_noise_aug_strength,
            "svd_min_guidance_scale": settings.svd_min_guidance_scale,
            "svd_max_guidance_scale": settings.svd_max_guidance_scale,
            "svd_decode_chunk_size": settings.svd_decode_chunk_size,
            "svd_seed": settings.svd_seed,
            "svd_enable_attention_slicing": settings.svd_enable_attention_slicing,
            "svd_enable_vae_slicing": settings.svd_enable_vae_slicing,
            "svd_enable_vae_tiling": settings.svd_enable_vae_tiling,
            "svd_enable_cpu_offload": settings.svd_enable_cpu_offload,
            "svd_extend_to_audio": settings.svd_extend_to_audio,
            "svd_extend_strategy": settings.svd_extend_strategy,
            "svd_auto_downscale": settings.svd_auto_downscale,
            "svd_mps_max_pixels": settings.svd_mps_max_pixels,
        }
    else:
        backend_cfg = {}
    hasher.update(json.dumps(backend_cfg, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    hasher.update(b"image\0")
    _hash_file(hasher, image_path)
    hasher.update(b"\0audio\0")
    _hash_file(hasher, audio_path)
    hasher.update(b"\0options\0")
    hasher.update(json.dumps(options, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    return hasher.hexdigest()


async def worker_loop(stop_event: asyncio.Event) -> None:
    generator = build_generator(settings.generator_backend)
    loop = asyncio.get_running_loop()

    while not stop_event.is_set():
        job_id = await job_queue.dequeue()
        job = await job_store.get(job_id)
        if not job:
            continue

        def progress_cb(progress: float, message: str) -> None:
            asyncio.run_coroutine_threadsafe(
                job_store.update(job_id, progress=progress, message=message), loop
            )

        await job_store.update(job_id, status=JobStatus.running, progress=0.01, message="Starting")
        try:
            if settings.enable_cache:
                cache_dir = settings.storage_dir / settings.cache_dirname
                cache_dir.mkdir(parents=True, exist_ok=True)
                key = _cache_key(job.input_image_path, job.input_audio_path, job.options)
                cached = cache_dir / f"{key}.mp4"
                if cached.exists() and cached.stat().st_size > 0:
                    job.output_video_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(cached, job.output_video_path)
                    await job_store.update(job_id, progress=1.0, message="Ready (cache hit)")
                    await job_store.update(job_id, status=JobStatus.succeeded)
                    continue

            await asyncio.to_thread(
                generator.generate,
                image_path=job.input_image_path,
                audio_path=job.input_audio_path,
                output_video_path=job.output_video_path,
                options=job.options,
                progress_cb=progress_cb,
            )
            if settings.enable_cache and job.output_video_path.exists():
                key = _cache_key(job.input_image_path, job.input_audio_path, job.options)
                cached = (settings.storage_dir / settings.cache_dirname) / f"{key}.mp4"
                cached.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(job.output_video_path, cached)
            await job_store.update(job_id, status=JobStatus.succeeded, progress=1.0, message="Ready")
        except Exception as e:
            await job_store.update(job_id, status=JobStatus.failed, progress=1.0, message="Failed", error=str(e))
        finally:
            latest = await job_store.get(job_id)
            if latest:
                persist_job_meta(latest)
