"""Media and lyric acquisition helpers for yt-karaoke."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple
from urllib.parse import quote_plus

import requests
import yt_dlp

from utils import friendly_user_agent, slugify


class AudioAcquisitionError(RuntimeError):
    """Raised when audio cannot be located or downloaded."""


class LyricsAcquisitionError(RuntimeError):
    """Raised when lyrics cannot be retrieved and user forbids fallback."""


@dataclass
class AudioResult:
    """Return value for successful audio acquisition."""

    title: str
    video_id: str
    audio_path: Path
    metadata: Dict


def _search_youtube(query: str, logger: logging.Logger) -> Dict:
    """Use yt-dlp to return metadata for the top YouTube match."""
    logger.info("Searching YouTube for %s...", query)
    opts = {"quiet": True, "skip_download": True, "default_search": "ytsearch"}
    with yt_dlp.YoutubeDL(opts) as ydl:
        result = ydl.extract_info(f"ytsearch1:{query}", download=False)
    entries = result.get("entries") if result else None
    if not entries:
        raise AudioAcquisitionError("No YouTube results were found for that query.")
    return entries[0]


def _ydl_download(url: str, cache_dir: Path, logger: logging.Logger) -> Tuple[Path, Dict]:
    """Download audio via yt-dlp and return the saved path + metadata."""
    outtmpl = str(cache_dir / "%(id)s.%(ext)s")
    opts = {
        "format": "bestaudio/best",
        "outtmpl": outtmpl,
        "quiet": False,
        "noplaylist": True,
        "ignoreerrors": False,
        "user_agent": friendly_user_agent(),
        "socket_timeout": 30,
        "http_headers": {
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate",
        },
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ],
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)

    ext = info.get("ext", "mp3")
    audio_path = cache_dir / f"{info['id']}.{ext}"
    if not audio_path.exists():  # Work around yt-dlp returning original ext
        converted = cache_dir / f"{info['id']}.mp3"
        if converted.exists():
            audio_path = converted
    logger.info("Downloaded %s", audio_path.name)

    metadata_path = cache_dir / f"{info['id']}.json"
    metadata_path.write_text(json.dumps(info, indent=2), encoding="utf-8")
    return audio_path, info


def acquire_audio(
    *,
    query: Optional[str],
    url: Optional[str],
    cache_dir: Path,
    no_download: bool,
    logger: logging.Logger,
) -> AudioResult:
    """Download or locate audio according to CLI parameters."""
    if no_download:
        logger.info("Skipping download; attempting to reuse local audio cache...")
        audio_path = _pick_cached_audio(cache_dir)
        metadata = _load_cached_metadata(audio_path)
        return AudioResult(
            title=metadata.get("title", audio_path.stem),
            video_id=metadata.get("id", audio_path.stem),
            audio_path=audio_path,
            metadata=metadata,
        )

    if url:
        logger.info("Downloading from explicit URL...")
        audio_path, metadata = _ydl_download(url, cache_dir, logger)
        video_id = metadata.get("id", slugify(metadata.get("title", "ytk")))
        title = metadata.get("title", url)
        return AudioResult(title=title, video_id=video_id, audio_path=audio_path, metadata=metadata)

    if not query:
        raise AudioAcquisitionError("A search query or URL is required to download audio.")

    info = _search_youtube(query, logger)
    url = info.get("webpage_url") or info.get("url")
    if not url:
        raise AudioAcquisitionError("yt-dlp did not return a downloadable URL.")
    audio_path, metadata = _ydl_download(url, cache_dir, logger)
    return AudioResult(
        title=metadata.get("title", query),
        video_id=metadata.get("id", slugify(metadata.get("title", query))),
        audio_path=audio_path,
        metadata=metadata,
    )


def _pick_cached_audio(cache_dir: Path) -> Path:
    """Return the most recently modified audio file from cache_dir."""
    candidates = sorted(
        cache_dir.glob("*.mp3"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise AudioAcquisitionError(
            f"--no-download requested but no .mp3 file found in {cache_dir}"
        )
    return candidates[0]


def _load_cached_metadata(audio_path: Path) -> Dict:
    """Load metadata JSON saved next to an audio file (best effort)."""
    meta_file = audio_path.with_suffix(".json")
    if meta_file.exists():
        try:
            return json.loads(meta_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {"title": audio_path.stem, "id": audio_path.stem}
    return {"title": audio_path.stem, "id": audio_path.stem}


def find_local_lrc(audio_path: Path, provided_path: Optional[str]) -> Optional[Path]:
    """Look for a lyric file next to the audio file or via explicit path."""
    if provided_path:
        path = Path(provided_path).expanduser()
        if path.exists():
            return path
        raise LyricsAcquisitionError(f"Provided LRC path does not exist: {path}")

    candidate = audio_path.with_suffix(".lrc")
    if candidate.exists():
        return candidate

    siblings = list(audio_path.parent.glob("*.lrc"))
    return siblings[0] if siblings else None


def download_lrc_from_web(
    *,
    title: str,
    artist: Optional[str],
    duration: Optional[float],
    cache_dir: Path,
    logger: logging.Logger,
) -> Optional[Path]:
    """Try multiple sources for lyrics, generating an LRC if necessary."""
    lrclib_path = _download_from_lrclib(title, artist, cache_dir, logger)
    if lrclib_path:
        return lrclib_path

    plain_lyrics = _fetch_plaintext_lyrics(title, artist, logger)
    if plain_lyrics:
        generated = _generate_lrc_from_plaintext(
            plain_lyrics,
            duration=duration,
            title=title,
            cache_dir=cache_dir,
            logger=logger,
        )
        if generated:
            logger.info("Generated approximate LRC from plain lyrics.")
            return generated

    return None


def _download_from_lrclib(
    title: str,
    artist: Optional[str],
    cache_dir: Path,
    logger: logging.Logger,
) -> Optional[Path]:
    params = {"track_name": title}
    if artist:
        params["artist_name"] = artist
    headers = {"User-Agent": friendly_user_agent()}
    url = "https://lrclib.net/api/search"
    logger.info("Searching lrclib for lyrics...")
    try:
        response = requests.get(url, params=params, headers=headers, timeout=8)
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as exc:
        logger.debug("lrclib request failed: %s", exc)
        return None

    entries = payload if isinstance(payload, list) else payload.get("results", [])
    if not entries:
        return None
    synced = entries[0].get("syncedLyrics") or entries[0].get("lyrics")
    if not synced:
        return None
    text = synced.strip()
    if not text:
        return None
    filename = cache_dir / f"{slugify(title)}.lrc"
    filename.write_text(text, encoding="utf-8")
    logger.info("Downloaded lyrics to %s", filename.name)
    return filename


def _fetch_plaintext_lyrics(title: str, artist: Optional[str], logger: logging.Logger) -> Optional[str]:
    """Try a couple of HTTP APIs that return unsynced lyric text."""
    headers = {"User-Agent": friendly_user_agent()}
    artist_or_unknown = artist or "unknown"
    providers = [
        (
            "lyrics.ovh",
            f"https://api.lyrics.ovh/v1/{quote_plus(artist_or_unknown)}/{quote_plus(title)}",
            "lyrics",
        ),
        (
            "lyrist",
            f"https://lyrist.vercel.app/api/{quote_plus(title)}?artist={quote_plus(artist_or_unknown)}",
            "lyrics",
        ),
    ]

    for name, url, key in providers:
        logger.info("Fetching lyrics from %s...", name)
        try:
            resp = requests.get(url, headers=headers, timeout=8)
            resp.raise_for_status()
            data = resp.json()
            text = data.get(key, "").strip()
            if text:
                return text
        except requests.RequestException as exc:
            logger.debug("%s provider failed: %s", name, exc)
        except ValueError:
            logger.debug("%s returned non-JSON payload", name)
    return None


def _generate_lrc_from_plaintext(
    text: str,
    *,
    duration: Optional[float],
    title: str,
    cache_dir: Path,
    logger: logging.Logger,
) -> Optional[Path]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return None

    if not duration:
        duration = len(lines) * 4.0
    per_line = max(duration / len(lines), 2.5)
    timestamp = 0.0
    buffer = []
    for line in lines:
        buffer.append(f"[{_format_lrc_timestamp(timestamp)}]{line}")
        timestamp += per_line

    filename = cache_dir / f"{slugify(title)}_generated.lrc"
    filename.write_text("\n".join(buffer), encoding="utf-8")
    logger.debug("Generated %d pseudo-timestamps for lyrics", len(lines))
    return filename


def _format_lrc_timestamp(value: float) -> str:
    minutes = int(value // 60)
    seconds = value % 60
    return f"{minutes:02d}:{seconds:05.2f}"
