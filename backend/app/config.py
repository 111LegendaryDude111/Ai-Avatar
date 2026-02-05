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
    generator_backend: str = "sadtalker"  # sadtalker | mock | wav2lip | svd

    # Default video settings for the mock generator.
    video_fps: int = 25
    video_size: int = 512

    # SadTalker integration.
    sadtalker_repo_dir: Path = PROJECT_DIR / "third_party" / "SadTalker"
    sadtalker_python: Path | None = SADTALKER_DEFAULT_PYTHON
    sadtalker_size: int = 256
    sadtalker_preprocess: str = "crop"  # crop | full | extfull
    sadtalker_enhancer: str | None = None  # gfpgan | RestoreFormer | None


settings = Settings()
