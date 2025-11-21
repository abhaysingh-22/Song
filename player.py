"""Audio playback with synchronized lyric rendering."""

from __future__ import annotations

import logging
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Iterable, List

from lrc_parser import LyricLine, LyricWord
from utils import format_time


class PlaybackError(RuntimeError):
    """Raised when no supported audio player is available."""


def play_with_lyrics(
    audio_path: Path,
    lyrics: Iterable[LyricLine],
    *,
    highlight: bool,
    overwrite: bool,
    logger: logging.Logger,
) -> None:
    """Play `audio_path` while rendering `lyrics` in sync with the audio clock."""
    cmd = _pick_audio_player(audio_path)
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError as exc:  # pragma: no cover - depends on host tools
        raise PlaybackError(f"Unable to spawn audio player: {exc}") from exc

    logger.info("Starting playback. Press Ctrl+C to stop.")
    start_time = time.monotonic()

    try:
        for line in lyrics:
            _wait_until(line.timestamp, start_time)
            if overwrite:
                _render_line_karaoke(line, start_time, highlight)
            else:
                _render_timestamped_line(line)

        proc.wait()
    except KeyboardInterrupt:
        logger.info("Stopping playback (Ctrl+C pressed).")
        proc.terminate()
        proc.wait()
    finally:
        if overwrite:
            print()  # ensure cursor moves to next line


def _pick_audio_player(audio_path: Path) -> List[str]:
    """Return a command list to play `audio_path` with ffplay or afplay."""
    ffplay = shutil.which("ffplay")
    if ffplay:
        return [ffplay, "-nodisp", "-autoexit", "-loglevel", "quiet", str(audio_path)]
    afplay = shutil.which("afplay")
    if afplay:
        return [afplay, str(audio_path)]
    raise PlaybackError("ffplay (from ffmpeg) or afplay (macOS) is required for playback.")


def _render_line_karaoke(line: LyricLine, start_time: float, highlight: bool) -> None:
    """Render words from a lyric line progressively on a single terminal line."""
    words = line.words or [LyricWord(timestamp=line.timestamp, text=line.text)]
    displayed: List[str] = []
    for idx, word in enumerate(words):
        _wait_until(word.timestamp, start_time)
        displayed.append(word.text)
        output_tokens = list(displayed)
        if highlight:
            output_tokens[-1] = output_tokens[-1].upper()
        text = " ".join(output_tokens)
        # Clear current line and re-print content.
        sys.stdout.write("\r" + text + " " * 10)
        sys.stdout.flush()
    # After final word, keep the line for a short moment before clearing.
    time.sleep(0.1)


def _render_timestamped_line(line: LyricLine) -> None:
    """Print fallback timestamped line output for terminals without overwrite support."""
    print(f"[{format_time(line.timestamp)}] {line.text}")


def _wait_until(target_timestamp: float, start_time: float) -> None:
    """Busy-wait until `time.monotonic()` reaches the lyric timestamp."""
    while True:
        elapsed = time.monotonic() - start_time
        remaining = target_timestamp - elapsed
        if remaining <= 0:
            break
        time.sleep(min(0.05, remaining))
