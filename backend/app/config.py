from __future__ import annotations

from pathlib import Path
import sys

from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = BACKEND_DIR.parent
SADTALKER_DEFAULT_PYTHON = (
    PROJECT_DIR
    / "third_party"
    / "SadTalker"
    / ".venv"
    / (Path("Scripts") / "python.exe" if sys.platform == "win32" else Path("bin") / "python")
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AVATAR_", env_file=".env", extra="ignore")

    storage_dir: Path = Path("storage")
    uploads_dirname: str = "uploads"
    outputs_dirname: str = "outputs"
    cache_dirname: str = "cache"
    enable_cache: bool = True

    # Frontend dev server defaults (Vite).
    cors_allow_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    # Generator backend selection.
    generator_backend: str = "mock"  # sadtalker | mock | wav2lip | svd

    # Default video settings for the mock generator.
    video_fps: int = 25
    video_size: int = 512

    # SadTalker integration.
    sadtalker_repo_dir: Path = PROJECT_DIR / "third_party" / "SadTalker"
    sadtalker_python: Path | None = SADTALKER_DEFAULT_PYTHON
    sadtalker_size: int = 256
    sadtalker_preprocess: str = "crop"  # crop | full | extfull
    sadtalker_enhancer: str | None = None  # gfpgan | RestoreFormer | None

    # Stable Video Diffusion (diffusers).
    svd_model: str = "stabilityai/stable-video-diffusion-img2vid-xt"  # HF id or local path
    svd_revision: str | None = None
    svd_variant: str | None = "fp16"
    svd_local_files_only: bool = False

    svd_device: str | None = None  # auto | cuda | mps | cpu
    svd_dtype: str = "auto"  # auto | float16 | float32 | bfloat16

    svd_width: int = 1024
    svd_height: int = 576
    svd_fps: int = 7
    svd_num_frames: int = 14
    svd_num_inference_steps: int = 25
    svd_motion_bucket_id: int = 127
    svd_noise_aug_strength: float = 0.02
    svd_min_guidance_scale: float = 1.0
    svd_max_guidance_scale: float = 3.0
    svd_decode_chunk_size: int = 8
    svd_seed: int | None = None
    # x264 constant rate factor (0..51). Lower means better visual quality / larger files.
    svd_encode_crf: int = 18

    svd_enable_attention_slicing: bool = True
    svd_enable_vae_slicing: bool = True
    svd_enable_vae_tiling: bool = False
    svd_enable_cpu_offload: bool = False
    svd_enable_xformers: bool = True

    # Since SVD doesn't use audio for motion, we can extend (freeze/loop) the
    # generated frames to match the audio duration for nicer UX.
    svd_extend_to_audio: bool = True
    svd_extend_strategy: str = "freeze"  # freeze | loop

    # MPS (Apple Silicon) can hit huge attention buffers at the default SVD resolution.
    # If enabled, the backend will automatically downscale when running on MPS.
    svd_auto_downscale: bool = True
    # Default chosen to stay under Metal buffer limits for naive attention on MPS,
    # while preserving acceptable quality.
    svd_mps_max_pixels: int = 512 * 288


settings = Settings()
