from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from ..config import settings
from .base import ProgressCallback


class SadTalkerAvatarVideoGenerator:
    def generate(
        self,
        *,
        image_path: Path,
        audio_path: Path,
        output_video_path: Path,
        options: dict[str, Any],
        progress_cb: ProgressCallback,
    ) -> None:
        image_path = image_path.resolve()
        audio_path = audio_path.resolve()
        output_video_path = output_video_path.resolve()

        repo_dir = Path(options.get("sadtalker_repo_dir") or settings.sadtalker_repo_dir).resolve()
        inference_py = repo_dir / "inference.py"
        if not inference_py.exists():
            raise RuntimeError(
                "SadTalker repo not found. Expected `inference.py` at: "
                f"{inference_py}. Clone SadTalker into that folder or set "
                "`AVATAR_SADTALKER_REPO_DIR` (or pass `sadtalker_repo_dir` in options)."
            )

        python_path_opt = options.get("sadtalker_python") or settings.sadtalker_python
        python_exec = Path(python_path_opt).expanduser() if python_path_opt else None
        # Important: do NOT call `.resolve()` here — venv `python` is often a symlink to the base
        # interpreter, and resolving it would bypass the venv site-packages (leading to missing torch).
        if python_exec and not python_exec.is_absolute():
            python_exec = (Path.cwd() / python_exec).absolute()
        elif python_exec:
            python_exec = python_exec.absolute()
        if python_exec and not python_exec.exists():
            raise RuntimeError(f"SadTalker python not found: {python_exec}")
        python_cmd = str(python_exec) if python_exec else sys.executable

        size = int(options.get("sadtalker_size") or settings.sadtalker_size)
        preprocess = str(options.get("sadtalker_preprocess") or settings.sadtalker_preprocess)
        enhancer = options.get("sadtalker_enhancer", settings.sadtalker_enhancer)
        still = bool(options.get("sadtalker_still", False))
        use_cpu = bool(options.get("sadtalker_cpu", False))

        result_dir = output_video_path.parent / "sadtalker"
        result_dir.mkdir(parents=True, exist_ok=True)

        progress_cb(0.05, "SadTalker: starting")

        cmd = [
            python_cmd,
            str(inference_py),
            "--driven_audio",
            str(audio_path),
            "--source_image",
            str(image_path),
            "--checkpoint_dir",
            str(repo_dir / "checkpoints"),
            "--result_dir",
            str(result_dir),
            "--size",
            str(size),
            "--preprocess",
            preprocess,
        ]
        if still:
            cmd.append("--still")
        if enhancer:
            cmd += ["--enhancer", str(enhancer)]
        if use_cpu:
            cmd.append("--cpu")

        extra_args = options.get("sadtalker_extra_args")
        if isinstance(extra_args, list) and all(isinstance(x, str) for x in extra_args):
            cmd += extra_args

        env = os.environ.copy()
        # Make sure local SadTalker imports resolve.
        env["PYTHONPATH"] = str(repo_dir) + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")

        progress_cb(0.2, "SadTalker: generating video")
        completed = subprocess.run(cmd, cwd=str(repo_dir), env=env, text=True, capture_output=True)
        if completed.returncode != 0:
            tail = (completed.stderr or completed.stdout or "").strip()
            if len(tail) > 4000:
                tail = tail[-4000:]
            raise RuntimeError(
                f"SadTalker failed with exit code {completed.returncode}"
                + (f"\n\n--- SadTalker output ---\n{tail}" if tail else "")
            )

        progress_cb(0.9, "SadTalker: collecting result")
        candidates = list(result_dir.glob("*.mp4"))
        if not candidates:
            candidates = list(result_dir.rglob("*.mp4"))
        if not candidates:
            raise RuntimeError(f"SadTalker produced no mp4 in {result_dir}")
        newest = max(candidates, key=lambda p: p.stat().st_mtime)

        output_video_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(newest, output_video_path)

        progress_cb(1.0, "Done")
