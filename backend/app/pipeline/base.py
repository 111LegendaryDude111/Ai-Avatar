from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Protocol

ProgressCallback = Callable[[float, str], None]


class AvatarVideoGenerator(Protocol):
    def generate(
        self,
        *,
        image_path: Path,
        audio_path: Path,
        output_video_path: Path,
        options: dict[str, Any],
        progress_cb: ProgressCallback,
    ) -> None: ...

