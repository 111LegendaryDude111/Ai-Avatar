from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any, Callable

from ..config import settings
from .base import ProgressCallback


class MockAvatarVideoGenerator:
    """
    Demo generator: creates an MP4 by looping the image and muxing the provided audio.

    This is a placeholder for real pipelines (SadTalker/Wav2Lip/SVD+ControlNet).
    """

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
            raise RuntimeError(
                "ffmpeg is required for the demo generator. "
                "Install it and retry (macOS: `brew install ffmpeg`)."
            )

        size = int(options.get("video_size", settings.video_size))
        fps = int(options.get("video_fps", settings.video_fps))

        progress_cb(0.1, "Encoding video")
        output_video_path.parent.mkdir(parents=True, exist_ok=True)

        # Build a simple still-image video with the audio track.
        # We crop to a square to simplify playback; a real model would preserve aspect.
        vf = (
            f"scale={size}:{size}:force_original_aspect_ratio=increase,"
            f"crop={size}:{size},format=yuv420p"
        )

        cmd = [
            ffmpeg,
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-loop",
            "1",
            "-framerate",
            str(fps),
            "-i",
            str(image_path),
            "-i",
            str(audio_path),
            "-vf",
            vf,
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-tune",
            "stillimage",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-shortest",
            str(output_video_path),
        ]

        subprocess.run(cmd, check=True)
        progress_cb(1.0, "Done")
