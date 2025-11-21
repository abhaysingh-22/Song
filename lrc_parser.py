"""LRC parsing with line-level and inline word-level timestamp support."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

TIMESTAMP_RE = re.compile(r"\[(?P<timestamp>\d{1,2}:\d{1,2}(?:\.\d{1,3})?)\]")
WORD_RE = re.compile(r"<(?P<timestamp>\d{1,2}:\d{1,2}(?:\.\d{1,3})?)>")
TAG_RE = re.compile(r"^\[(?P<tag>[A-Za-z]+):(?P<value>.*)]$")
META_TAGS = {"ti", "ar", "al", "by", "offset", "length"}


@dataclass
class LyricWord:
    """Represents a single karaoke word with absolute timestamp."""

    timestamp: float
    text: str


@dataclass
class LyricLine:
    """Represents a karaoke line with optional inline word timings."""

    timestamp: float
    text: str
    words: List[LyricWord] = field(default_factory=list)


@dataclass
class ParsedLRC:
    """Container for parsed lyric lines plus their metadata tags."""

    lines: List[LyricLine]
    tags: Dict[str, str]


def parse_lrc_file(filepath: str) -> ParsedLRC:
    """Read a file from `filepath` and parse its lyrics."""
    text = Path(filepath).read_text(encoding="utf-8", errors="ignore")
    return parse_lrc_text(text)


def parse_lrc_text(text: str) -> ParsedLRC:
    """Parse raw LRC text into data structures."""
    lines: List[LyricLine] = []
    tags: Dict[str, str] = {}
    offset = 0.0

    for raw in text.splitlines():
        stripped = raw.strip()
        if not stripped:
            continue

        tag_match = TAG_RE.match(stripped)
        if tag_match and tag_match.group("tag").lower() in META_TAGS:
            tag = tag_match.group("tag").lower()
            value = tag_match.group("value").strip()
            tags[tag] = value
            if tag == "offset":
                try:
                    offset = float(value) / 1000.0
                except ValueError:
                    offset = 0.0
            continue

        timestamps = [
            parse_timestamp(match.group("timestamp"))
            for match in TIMESTAMP_RE.finditer(stripped)
        ]
        if not timestamps:
            continue

        content = TIMESTAMP_RE.sub("", stripped).strip()
        words = _parse_inline_words(content)
        plain_text = WORD_RE.sub("", content).strip()

        for ts in timestamps:
            lines.append(
                LyricLine(
                    timestamp=ts + offset,
                    text=plain_text,
                    words=words,
                )
            )

    lines.sort(key=lambda line: line.timestamp)
    return ParsedLRC(lines=lines, tags=tags)


def _parse_inline_words(content: str) -> List[LyricWord]:
    """Extract inline word-level timestamps from a lyric line."""
    words: List[LyricWord] = []
    position = 0
    while True:
        match = WORD_RE.search(content, pos=position)
        if not match:
            break
        ts = parse_timestamp(match.group("timestamp"))
        position = match.end()
        next_match = WORD_RE.search(content, pos=position)
        end = next_match.start() if next_match else len(content)
        word = content[position:end].strip()
        if word:
            words.append(LyricWord(timestamp=ts, text=word))
        position = end
    return words


def parse_timestamp(timestamp_str: str) -> float:
    """Convert an `MM:SS.xx` string to seconds as float."""
    try:
        minute_part, second_part = timestamp_str.split(":", maxsplit=1)
        minutes = int(minute_part)
        seconds = float(second_part)
    except ValueError as exc:
        raise ValueError(f"Invalid timestamp: {timestamp_str}") from exc
    return minutes * 60 + seconds
