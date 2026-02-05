from __future__ import annotations

from .base import AvatarVideoGenerator
from .mock_generator import MockAvatarVideoGenerator
from .sadtalker_generator import SadTalkerAvatarVideoGenerator
from .svd_controlnet_generator import SVDControlNetAvatarVideoGenerator
from .wav2lip_generator import Wav2LipAvatarVideoGenerator


def build_generator(backend_name: str) -> AvatarVideoGenerator:
    name = (backend_name or "mock").strip().lower()
    if name == "mock":
        return MockAvatarVideoGenerator()
    if name == "sadtalker":
        return SadTalkerAvatarVideoGenerator()
    if name == "wav2lip":
        return Wav2LipAvatarVideoGenerator()
    if name in {"svd", "svd+controlnet", "controlnet"}:
        return SVDControlNetAvatarVideoGenerator()
    raise ValueError(f"Unknown generator backend: {backend_name!r}")
