from __future__ import annotations

from pathlib import Path
from typing import Any

from .base import ProgressCallback


class SVDControlNetAvatarVideoGenerator:
    def generate(
        self,
        *,
        image_path: Path,
        audio_path: Path,
        output_video_path: Path,
        options: dict[str, Any],
        progress_cb: ProgressCallback,
    ) -> None:
        raise RuntimeError(
            "SVD+ControlNet backend is not implemented yet. "
            "Implementing it typically requires `diffusers`, model weights, "
            "and a motion/landmark conditioning stage."
        )

