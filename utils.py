"""Helper utilities shared across yt-karaoke modules."""

from __future__ import annotations

import logging
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Optional, Tuple

LOGGER_NAME = "yt_karaoke"


def configure_logging(debug: bool) -> logging.Logger:
    """Configure the root logger once and return the project logger."""
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="[%(levelname)s] %(message)s" if debug else "%(message)s",
    )
    return logging.getLogger(LOGGER_NAME)


def ensure_cache_dir(keep_cache: bool, override: Optional[str]) -> Tuple[Path, bool]:
    """Return a directory for downloads, and whether it should be auto-cleaned."""
    if override:
        path = Path(override).expanduser()
        path.mkdir(parents=True, exist_ok=True)
        return path, False

    if keep_cache:
        path = Path(tempfile.gettempdir()) / "yt_karaoke_cache"
        path.mkdir(parents=True, exist_ok=True)
        return path, False

    path = Path(tempfile.mkdtemp(prefix="ytk_"))
    return path, True


def cleanup_path(path: Path) -> None:
    """Remove `path` if it exists (best-effort)."""
    if path.exists():
        shutil.rmtree(path, ignore_errors=True)


def format_time(seconds: float) -> str:
    """Format seconds to `MM:SS` text."""
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes:02d}:{secs:02d}"


def slugify(value: str) -> str:
    """Return a filesystem-friendly slug derived from `value`."""
    keep = "abcdefghijklmnopqrstuvwxyz0123456789-_."
    value = value.strip().lower().replace(" ", "-")
    sanitized = "".join(ch for ch in value if ch in keep)
    return sanitized or "ytk-audio"


def terminal_supports_overwrite() -> bool:
    """Best-effort check whether stdout can handle carriage-return updates."""
    if not sys.stdout.isatty():
        return False
    term = os.environ.get("TERM", "")
    return term not in {"dumb", ""}


def friendly_user_agent() -> str:
    """Return a descriptive User-Agent for lyric fetch requests."""
    return "yt-karaoke/1.0 (+https://github.com/yt-karaoke)"


def prompt_missing_lrc_action() -> str:
    """Ask the user how to proceed when lyrics are missing."""
    options = {"c": "continue", "m": "manual", "a": "abort"}
    prompt = "Lyrics not found. [C]ontinue without, [M]anual path, [A]bort? "
    while True:
        choice = input(prompt).strip().lower() or "c"
        if choice in options:
            return options[choice]
        print("Please choose C, M, or A.")


def ensure_ffmpeg_available() -> bool:
    """Check if ffmpeg/ffplay binaries are available in PATH."""
    return any(shutil.which(cmd) for cmd in ("ffmpeg", "ffplay", "afplay"))
