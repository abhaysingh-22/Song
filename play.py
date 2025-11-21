#!/usr/bin/env python3
"""CLI entrypoint tying together downloader, parser, and player."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional, Tuple

from cli import parse_args
from downloader import (
    AudioAcquisitionError,
    LyricsAcquisitionError,
    acquire_audio,
    download_lrc_from_web,
    find_local_lrc,
)
from lrc_parser import ParsedLRC, parse_lrc_file
from player import PlaybackError, play_with_lyrics
from utils import (
    cleanup_path,
    configure_logging,
    ensure_cache_dir,
    ensure_ffmpeg_available,
    prompt_missing_lrc_action,
    terminal_supports_overwrite,
)


def main() -> int:
    args = parse_args()
    logger = configure_logging(args.debug)
    cache_dir, should_cleanup = ensure_cache_dir(args.cache, args.cache_dir)
    logger.debug("Using cache directory %s", cache_dir)

    if not ensure_ffmpeg_available():
        logger.warning(
            "ffmpeg/ffplay not detected in PATH; install ffmpeg for playback and conversions."
        )

    audio = None
    lyrics_cleanup_path: Optional[Path] = None
    lyrics_auto_cleanup = False

    try:
        audio = acquire_audio(
            query=args.query,
            url=args.url,
            cache_dir=cache_dir,
            no_download=args.no_download,
            logger=logger,
        )
        lyrics, lyrics_cleanup_path, lyrics_auto_cleanup = _resolve_lyrics(
            args,
            audio.audio_path,
            audio.metadata,
            cache_dir,
            logger,
        )
        overwrite = terminal_supports_overwrite()
        if not overwrite:
            logger.info("Terminal does not support overwrite; falling back to timestamps.")
        if not lyrics.lines:
            logger.warning("Proceeding without synchronized lyrics.")
        play_with_lyrics(
            audio.audio_path,
            lyrics.lines,
            highlight=args.highlight,
            overwrite=overwrite,
            logger=logger,
        )
    except (AudioAcquisitionError, LyricsAcquisitionError, PlaybackError) as exc:
        logger.error(str(exc))
        return 1
    finally:
        if audio and not args.cache and not args.no_download:
            _cleanup_audio_files(audio.audio_path)
        if lyrics_auto_cleanup and lyrics_cleanup_path and not args.cache:
            _cleanup_generated_lyrics(lyrics_cleanup_path)
        if should_cleanup:
            cleanup_path(cache_dir)
    return 0


def _cleanup_audio_files(audio_path: Path) -> None:
    """Remove downloaded audio and its metadata sidecar."""
    try:
        audio_path.unlink(missing_ok=True)
    except TypeError:  # Python < 3.8 compatibility fallback
        if audio_path.exists():
            audio_path.unlink()
    meta = audio_path.with_suffix(".json")
    if meta.exists():
        meta.unlink()


def _cleanup_generated_lyrics(path: Path) -> None:
    """Delete auto-downloaded lyric files."""
    if path.exists():
        path.unlink()


def _resolve_lyrics(
    args,
    audio_path: Path,
    metadata,
    cache_dir: Path,
    logger,
) -> Tuple[ParsedLRC, Optional[Path], bool]:
    """Find, download, or prompt for lyrics depending on CLI options."""
    provided = getattr(args, "lrc_path", None)
    auto_cleanup = False

    if provided:
        path = Path(provided).expanduser()
        if not path.exists():
            raise LyricsAcquisitionError(f"LRC file not found: {path}")
    else:
        path = find_local_lrc(audio_path, None)
        if not path:
            artist = metadata.get("artist") or metadata.get("artist_name") or metadata.get("uploader")
            duration = metadata.get("duration")
            path = download_lrc_from_web(
                title=metadata.get("title", audio_path.stem),
                artist=artist,
                duration=duration,
                cache_dir=cache_dir,
                logger=logger,
            )
            if path:
                auto_cleanup = True

    while not path:
        choice = prompt_missing_lrc_action()
        if choice == "continue":
            return ParsedLRC(lines=[], tags={}), None, False
        if choice == "abort":
            raise LyricsAcquisitionError("User aborted due to missing lyrics.")
        manual = input("Enter path to .lrc file: ").strip()
        if not manual:
            continue
        candidate = Path(manual).expanduser()
        if candidate.exists():
            path = candidate
            auto_cleanup = False
            break
        logger.warning("%s does not exist", candidate)

    logger.info("Using lyrics file %s", path)
    return parse_lrc_file(str(path)), path, auto_cleanup


if __name__ == "__main__":
    sys.exit(main())
