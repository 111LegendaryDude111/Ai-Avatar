from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def synthesize_text_to_wav(text: str, output_wav_path: Path) -> None:
    """
    Minimal, local-only TTS helper.

    Uses macOS `say` if available, otherwise tries `espeak` / `espeak-ng`.
    Requires ffmpeg to convert intermediate formats to WAV.
    """

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError(
            "Text-to-speech requires ffmpeg to convert audio. "
            "Install it and retry (macOS: `brew install ffmpeg`)."
        )

    output_wav_path.parent.mkdir(parents=True, exist_ok=True)

    say = shutil.which("say")
    if say:
        tmp_aiff = output_wav_path.with_suffix(".aiff")
        subprocess.run([say, "-o", str(tmp_aiff), text], check=True)
        subprocess.run(
            [ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-i", str(tmp_aiff), str(output_wav_path)],
            check=True,
        )
        tmp_aiff.unlink(missing_ok=True)
        return

    espeak = shutil.which("espeak") or shutil.which("espeak-ng")
    if espeak:
        tmp_wav = output_wav_path
        subprocess.run([espeak, "-w", str(tmp_wav), text], check=True)
        return

    raise RuntimeError(
        "No local TTS engine found. Provide an audio file instead, or install one of: "
        "macOS: built-in `say`; Linux: `espeak-ng`."
    )

