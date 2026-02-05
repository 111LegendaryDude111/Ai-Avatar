from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from fastapi import HTTPException, UploadFile

from .pipeline.tts import synthesize_text_to_wav


def _maybe_convert_to_wav(input_path: Path, output_path: Path) -> Path:
    if input_path.suffix.lower() == ".wav":
        return input_path

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return input_path

    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(
            [
                ffmpeg,
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                str(input_path),
                "-ac",
                "1",
                "-ar",
                "16000",
                "-c:a",
                "pcm_s16le",
                str(output_path),
            ],
            check=True,
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"ffmpeg audio conversion failed (exit code {e.returncode})") from e
    return output_path


async def ensure_audio_for_request(
    *,
    job_id: str,
    uploads_dir: Path,
    text: str | None,
    audio_file: UploadFile | None,
) -> Path:
    if text:
        audio_path = uploads_dir / "audio.wav"
        try:
            synthesize_text_to_wav(text, audio_path)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"TTS failed: {e}") from e
        return audio_path

    if audio_file and audio_file.filename:
        suffix = Path(audio_file.filename).suffix or ".wav"
        audio_path = uploads_dir / f"audio{suffix}"
        with audio_path.open("wb") as f:
            f.write(await audio_file.read())
        try:
            return _maybe_convert_to_wav(audio_path, uploads_dir / "audio.wav")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Audio preprocessing failed: {e}") from e

    raise HTTPException(status_code=400, detail="Audio is required")
