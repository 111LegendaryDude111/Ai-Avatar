from __future__ import annotations

import inspect
import math
import shutil
import subprocess
import tempfile
import wave
from pathlib import Path
from typing import Any

from ..config import settings
from .base import ProgressCallback


def _coerce_bool(value: object, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return default


def _round_down_to_multiple(value: int, multiple: int) -> int:
    if multiple <= 1:
        return max(1, int(value))
    return max(multiple, int(value // multiple) * multiple)


def _get_media_duration_seconds(path: Path) -> float | None:
    ffprobe = shutil.which("ffprobe")
    if ffprobe:
        completed = subprocess.run(
            [
                ffprobe,
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            text=True,
            capture_output=True,
        )
        if completed.returncode == 0:
            raw = (completed.stdout or "").strip()
            try:
                return float(raw)
            except ValueError:
                return None

    if path.suffix.lower() == ".wav":
        try:
            with wave.open(str(path), "rb") as wf:
                frames = wf.getnframes()
                rate = wf.getframerate() or 0
            if rate <= 0:
                return None
            return float(frames) / float(rate)
        except Exception:
            return None

    return None


class StableVideoDiffusionAvatarVideoGenerator:
    """
    Image → Video via Stable Video Diffusion (diffusers).

    Notes:
    - This backend does NOT do lip-sync. The provided audio is only muxed into the output MP4.
    - Model weights are expected to be available locally (or downloadable if network is enabled).
    """

    def __init__(self) -> None:
        self._pipe: object | None = None
        self._pipe_key: tuple[str, str, str] | None = None  # (model_id, device, dtype_str)

    def _select_device(self, options: dict[str, Any]) -> str:
        device_opt = (options.get("svd_device") or settings.svd_device or "auto").strip().lower()
        if device_opt and device_opt != "auto":
            return device_opt

        try:
            import torch
        except Exception:
            return "cpu"

        if torch.cuda.is_available():
            return "cuda"
        if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
            return "mps"
        return "cpu"

    def _select_dtype(self, device: str, options: dict[str, Any]) -> tuple[object, str]:
        dtype_opt = str(options.get("svd_dtype") or settings.svd_dtype or "auto").strip().lower()
        try:
            import torch
        except Exception as e:  # pragma: no cover - torch missing is handled elsewhere
            raise RuntimeError("SVD backend requires torch to be installed") from e

        if dtype_opt in {"float16", "fp16", "half"}:
            return torch.float16, "float16"
        if dtype_opt in {"bfloat16", "bf16"}:
            return torch.bfloat16, "bfloat16"
        if dtype_opt in {"float32", "fp32"}:
            return torch.float32, "float32"

        # auto
        if device == "cuda":
            return torch.float16, "float16"
        if device == "mps":
            # MPS can be finicky; float16 saves memory, float32 may be more compatible.
            # Let users override via AVATAR_SVD_DTYPE=float32 if needed.
            return torch.float16, "float16"
        return torch.float32, "float32"

    def _load_pipe(self, *, model_id: str, device: str, dtype: object, dtype_str: str, options: dict[str, Any], progress_cb: ProgressCallback) -> object:
        pipe_key = (model_id, device, dtype_str)
        if self._pipe is not None and self._pipe_key == pipe_key:
            return self._pipe

        try:
            from diffusers import StableVideoDiffusionPipeline
        except ImportError as e:
            raise RuntimeError(
                "SVD backend requires extra dependencies. Install them with:\n"
                "  pip install -r backend/requirements.svd.txt\n"
                "Then set AVATAR_GENERATOR_BACKEND=svd and configure AVATAR_SVD_MODEL."
            ) from e

        local_only = _coerce_bool(options.get("svd_local_files_only"), settings.svd_local_files_only)
        variant = options.get("svd_variant") or settings.svd_variant
        revision = options.get("svd_revision") or settings.svd_revision

        kwargs: dict[str, Any] = {"torch_dtype": dtype, "local_files_only": local_only}
        if variant:
            kwargs["variant"] = str(variant)
        if revision:
            kwargs["revision"] = str(revision)

        progress_cb(0.08, "SVD: loading model (first run can be slow)")
        try:
            pipe = StableVideoDiffusionPipeline.from_pretrained(model_id, **kwargs)
        except Exception as e:
            raise RuntimeError(
                "Failed to load SVD weights. If you have no network, download weights first and use a local path.\n"
                "Example:\n"
                "  export AVATAR_SVD_MODEL=stabilityai/stable-video-diffusion-img2vid-xt\n"
                "or:\n"
                "  export AVATAR_SVD_MODEL=/abs/path/to/local/model\n"
                f"\nOriginal error: {e}"
            ) from e

        pipe.set_progress_bar_config(disable=True)

        enable_attention_slicing = _coerce_bool(
            options.get("svd_enable_attention_slicing"), settings.svd_enable_attention_slicing
        )
        if enable_attention_slicing:
            if hasattr(pipe, "enable_attention_slicing"):
                try:
                    pipe.enable_attention_slicing()
                except Exception:
                    progress_cb(0.09, "SVD: attention slicing not supported, continuing")
            else:
                unet = getattr(pipe, "unet", None)
                if unet is not None and hasattr(unet, "set_attention_slice"):
                    try:
                        unet.set_attention_slice("auto")
                    except Exception:
                        progress_cb(0.09, "SVD: attention slicing not supported, continuing")

        enable_vae_slicing = _coerce_bool(options.get("svd_enable_vae_slicing"), settings.svd_enable_vae_slicing)
        if enable_vae_slicing:
            if hasattr(pipe, "enable_vae_slicing"):
                try:
                    pipe.enable_vae_slicing()
                except Exception:
                    progress_cb(0.09, "SVD: VAE slicing not supported, continuing")
            else:
                vae = getattr(pipe, "vae", None)
                if vae is not None and hasattr(vae, "enable_slicing"):
                    try:
                        vae.enable_slicing()
                    except Exception:
                        progress_cb(0.09, "SVD: VAE slicing not supported, continuing")

        enable_vae_tiling = _coerce_bool(options.get("svd_enable_vae_tiling"), settings.svd_enable_vae_tiling)
        if enable_vae_tiling:
            if hasattr(pipe, "enable_vae_tiling"):
                try:
                    pipe.enable_vae_tiling()
                except Exception:
                    progress_cb(0.09, "SVD: VAE tiling not supported, continuing")
            else:
                vae = getattr(pipe, "vae", None)
                if vae is not None and hasattr(vae, "enable_tiling"):
                    try:
                        vae.enable_tiling()
                    except Exception:
                        progress_cb(0.09, "SVD: VAE tiling not supported, continuing")

        enable_xformers = _coerce_bool(options.get("svd_enable_xformers"), settings.svd_enable_xformers)
        if enable_xformers and device == "cuda" and hasattr(pipe, "enable_xformers_memory_efficient_attention"):
            try:
                pipe.enable_xformers_memory_efficient_attention()
                progress_cb(0.09, "SVD: xFormers enabled")
            except Exception:
                progress_cb(0.09, "SVD: xFormers not available, continuing")

        enable_cpu_offload = _coerce_bool(options.get("svd_enable_cpu_offload"), settings.svd_enable_cpu_offload)
        if enable_cpu_offload and device == "cuda":
            # Requires `accelerate`. Useful on small GPUs.
            if not hasattr(pipe, "enable_model_cpu_offload"):
                raise RuntimeError(
                    "CPU offload requested, but this diffusers version doesn't support "
                    "`enable_model_cpu_offload()`. Upgrade diffusers/accelerate or disable "
                    "`AVATAR_SVD_ENABLE_CPU_OFFLOAD`."
                )
            pipe.enable_model_cpu_offload()
        else:
            pipe.to(device)

        self._pipe = pipe
        self._pipe_key = pipe_key
        return pipe

    def generate(
        self,
        *,
        image_path: Path,
        audio_path: Path,
        output_video_path: Path,
        options: dict[str, Any],
        progress_cb: ProgressCallback,
    ) -> None:
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            raise RuntimeError("ffmpeg is required for the SVD backend (macOS: `brew install ffmpeg`).")

        model_id = str(options.get("svd_model") or settings.svd_model).strip()
        if not model_id:
            raise RuntimeError("SVD model is not configured. Set `AVATAR_SVD_MODEL` (HF id or local path).")

        device = self._select_device(options)
        dtype, dtype_str = self._select_dtype(device, options)

        pipe = self._load_pipe(
            model_id=model_id,
            device=device,
            dtype=dtype,
            dtype_str=dtype_str,
            options=options,
            progress_cb=progress_cb,
        )

        try:
            import torch
            from PIL import Image, ImageOps
        except ImportError as e:  # pragma: no cover - only if env is broken
            raise RuntimeError("SVD backend missing required runtime deps (torch/Pillow).") from e

        width = int(options.get("svd_width") or settings.svd_width)
        height = int(options.get("svd_height") or settings.svd_height)
        fps = int(options.get("svd_fps") or settings.svd_fps)
        num_frames = int(options.get("svd_num_frames") or settings.svd_num_frames)
        num_inference_steps = int(options.get("svd_num_inference_steps") or settings.svd_num_inference_steps)
        motion_bucket_id = int(options.get("svd_motion_bucket_id") or settings.svd_motion_bucket_id)
        noise_aug_strength = float(options.get("svd_noise_aug_strength") or settings.svd_noise_aug_strength)
        min_guidance_scale = float(options.get("svd_min_guidance_scale") or settings.svd_min_guidance_scale)
        max_guidance_scale = float(options.get("svd_max_guidance_scale") or settings.svd_max_guidance_scale)
        decode_chunk_size_raw = options.get("svd_decode_chunk_size")
        decode_chunk_size = int(decode_chunk_size_raw or settings.svd_decode_chunk_size)
        if device == "mps" and decode_chunk_size_raw is None:
            # MPS often needs smaller decode chunks.
            decode_chunk_size = min(decode_chunk_size, 1)

        seed_opt = options.get("svd_seed", settings.svd_seed)
        seed = int(seed_opt) if seed_opt is not None else None

        extend_to_audio = _coerce_bool(options.get("svd_extend_to_audio"), settings.svd_extend_to_audio)
        extend_strategy = str(options.get("svd_extend_strategy") or settings.svd_extend_strategy).strip().lower()
        if extend_strategy not in {"freeze", "loop"}:
            extend_strategy = "freeze"

        auto_downscale = _coerce_bool(options.get("svd_auto_downscale"), settings.svd_auto_downscale)
        if device == "mps" and auto_downscale:
            max_pixels = int(options.get("svd_mps_max_pixels") or settings.svd_mps_max_pixels or 0)
            if max_pixels > 0 and width * height > max_pixels:
                scale = math.sqrt(max_pixels / float(width * height))
                new_width = _round_down_to_multiple(max(256, int(width * scale)), 8)
                new_height = _round_down_to_multiple(max(256, int(height * scale)), 8)
                if new_width != width or new_height != height:
                    progress_cb(0.17, f"SVD: downscaling for MPS {width}x{height} → {new_width}x{new_height}")
                    width, height = new_width, new_height

        progress_cb(0.18, "SVD: preparing input image")
        image = Image.open(image_path).convert("RGB")
        image = ImageOps.fit(image, (width, height), method=Image.LANCZOS)

        gen = None
        if seed is not None:
            gen = torch.Generator(device=device).manual_seed(seed)

        progress_cb(0.25, "SVD: generating frames")

        call_kwargs: dict[str, Any] = dict(
            image=image,
            num_frames=num_frames,
            num_inference_steps=num_inference_steps,
            min_guidance_scale=min_guidance_scale,
            max_guidance_scale=max_guidance_scale,
            motion_bucket_id=motion_bucket_id,
            noise_aug_strength=noise_aug_strength,
            decode_chunk_size=decode_chunk_size,
        )
        if gen is not None:
            call_kwargs["generator"] = gen

        # Optional progress callback, depending on diffusers version.
        try:
            sig = inspect.signature(pipe.__call__)  # type: ignore[attr-defined]
        except Exception:
            sig = None
        if sig and "height" in sig.parameters:
            call_kwargs["height"] = height
        if sig and "width" in sig.parameters:
            call_kwargs["width"] = width
        if sig and "callback" in sig.parameters and "callback_steps" in sig.parameters:
            call_kwargs["callback_steps"] = 1

            def _cb(step: int, _timestep: int, _latents: object) -> None:
                # 0.25..0.75
                frac = float(step + 1) / float(max(1, num_inference_steps))
                progress_cb(0.25 + 0.5 * frac, f"SVD: denoising {step + 1}/{num_inference_steps}")

            call_kwargs["callback"] = _cb
        elif sig and "callback_on_step_end" in sig.parameters:

            def _cb_on_end(_pipe: object, step: int, _timestep: int, callback_kwargs: dict[str, Any]) -> dict[str, Any]:
                frac = float(step + 1) / float(max(1, num_inference_steps))
                progress_cb(0.25 + 0.5 * frac, f"SVD: denoising {step + 1}/{num_inference_steps}")
                return callback_kwargs

            call_kwargs["callback_on_step_end"] = _cb_on_end

        try:
            with torch.inference_mode():
                result = pipe(**call_kwargs)  # type: ignore[misc]
        except RuntimeError as e:
            msg = str(e)
            msg_lower = msg.lower()
            if "invalid buffer size" in msg_lower or "out of memory" in msg_lower or "mps" in msg_lower:
                raise RuntimeError(
                    "SVD failed due to memory limits (common on Apple Silicon / MPS).\n"
                    "Try:\n"
                    "- Smaller resolution: set `AVATAR_SVD_WIDTH=512` and `AVATAR_SVD_HEIGHT=288` (or 384x216)\n"
                    "- Smaller decode chunks: `AVATAR_SVD_DECODE_CHUNK_SIZE=1`\n"
                    "- Fewer frames: `AVATAR_SVD_NUM_FRAMES=8` (or less)\n"
                    "- If fp16 is unstable on your setup: `AVATAR_SVD_DTYPE=float32`\n"
                    "- As a fallback: `export PYTORCH_ENABLE_MPS_FALLBACK=1`\n"
                    "\n"
                    f"Current settings: device={device}, size={width}x{height}, num_frames={num_frames}, steps={num_inference_steps}\n"
                    "\n"
                    f"Original error: {msg}"
                ) from e
            raise
        frames: list[Any] = list(result.frames[0])  # list[PIL.Image.Image]

        if extend_to_audio and fps > 0 and len(frames) > 0:
            dur = _get_media_duration_seconds(audio_path)
            if dur and dur > 0:
                target_frames = int(math.ceil(dur * fps)) + 1
                if target_frames > len(frames):
                    need = target_frames - len(frames)
                    if extend_strategy == "loop" and len(frames) > 1:
                        loop_src = frames[1:]
                        extra: list[Any] = []
                        while len(extra) < need:
                            extra.extend(loop_src[: max(0, need - len(extra))])
                        frames.extend(extra)
                    else:
                        frames.extend([frames[-1]] * need)

        progress_cb(0.82, "SVD: encoding video")
        output_video_path.parent.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory(prefix="svd_", dir=str(output_video_path.parent)) as tmpdir:
            tmpdir_path = Path(tmpdir)
            frames_dir = tmpdir_path / "frames"
            frames_dir.mkdir(parents=True, exist_ok=True)
            for idx, frame in enumerate(frames):
                frame.save(frames_dir / f"frame_{idx:05d}.png")

            silent_video = tmpdir_path / "video.mp4"
            encode_cmd = [
                ffmpeg,
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-framerate",
                str(fps),
                "-i",
                str(frames_dir / "frame_%05d.png"),
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-preset",
                "veryfast",
                "-movflags",
                "+faststart",
                str(silent_video),
            ]
            subprocess.run(encode_cmd, check=True)

            progress_cb(0.92, "SVD: muxing audio")
            mux_cmd = [
                ffmpeg,
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                str(silent_video),
                "-i",
                str(audio_path),
                "-c:v",
                "copy",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-shortest",
                "-movflags",
                "+faststart",
                str(output_video_path),
            ]
            subprocess.run(mux_cmd, check=True)

        progress_cb(1.0, "Done")
