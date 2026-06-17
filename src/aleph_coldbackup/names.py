from __future__ import annotations

import os
import re

_INVALID = re.compile(r"[\x00-\x1f/\\]")
_RESERVED = {"", ".", ".."}
_MAX = 255


def safe_component(name: str | None, fallback: str) -> str:
    cleaned = _INVALID.sub("_", (name or "")).strip()
    if cleaned in _RESERVED:
        cleaned = fallback
    return cleaned[:_MAX]


def _split_ext(name: str) -> tuple[str, str]:
    stem, ext = os.path.splitext(name)
    if not stem:  # dotfile like ".DS_Store" -> treat whole thing as stem
        return name, ""
    return stem, ext


class PathAllocator:
    """Tracks used names per directory and disambiguates collisions."""

    def __init__(self) -> None:
        self._used: dict[str, set[str]] = {}

    def allocate(self, parent_rel: str, name: str, disambiguator: str) -> tuple[str, bool]:
        used = self._used.setdefault(parent_rel, set())
        if name not in used:
            used.add(name)
            return name, False
        stem, ext = _split_ext(name)
        suffix = disambiguator[:8]
        candidate = f"{stem}-{suffix}{ext}"
        counter = 1
        while candidate in used:
            candidate = f"{stem}-{suffix}-{counter}{ext}"
            counter += 1
        used.add(candidate)
        return candidate, True
