"""Argument parsing for the yt-karaoke CLI."""

from __future__ import annotations

import argparse
from typing import Iterable, Optional


def build_parser() -> argparse.ArgumentParser:
    """Return an `ArgumentParser` configured for yt-karaoke."""
    parser = argparse.ArgumentParser(
        prog="yt-karaoke",
        description="Download YouTube audio and display karaoke-synced lyrics.",
    )
    parser.add_argument(
        "query",
        nargs="?",
        default=None,
        help="Song name/search query when --url is not provided.",
    )
    parser.add_argument(
        "--query",
        dest="query_override",
        help="Explicit search query (takes priority over positional value).",
    )
    parser.add_argument(
        "--url",
        help="Direct YouTube video URL; skips search step.",
    )
    parser.add_argument(
        "--lrc",
        dest="lrc_path",
        help="Path to a local .lrc file (skips auto-discovery).",
    )
    parser.add_argument(
        "--cache",
        action="store_true",
        help="Keep downloaded audio instead of deleting it after playback.",
    )
    parser.add_argument(
        "--no-download",
        action="store_true",
        help="Skip yt-dlp. Expect audio already present in cache_dir.",
    )
    parser.add_argument(
        "--highlight",
        action="store_true",
        help="Highlight the active lyric word (default is minimal output).",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable verbose logging for troubleshooting.",
    )
    parser.add_argument(
        "--cache-dir",
        default=None,
        help="Override temporary cache directory location.",
    )
    return parser


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    """Parse CLI arguments and normalize derived fields."""
    parser = build_parser()
    args = parser.parse_args(argv)

    # `--query` should override positional query if provided.
    if getattr(args, "query_override", None):
        args.query = args.query_override
    delattr(args, "query_override")

    if not args.query and not args.url:
        parser.error("Provide a search query (positional or --query) or --url.")

    return args
