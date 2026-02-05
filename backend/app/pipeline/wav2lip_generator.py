from __future__ import annotations

from pathlib import Path
from typing import Any

from .base import ProgressCallback


class Wav2LipAvatarVideoGenerator:
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
            "Wav2Lip backend is not wired up in this repo yet. "
            "A typical approach is: create a base video from the image, "
            "then run Wav2Lip to sync the mouth region to the audio."
        )

