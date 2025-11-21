# yt-karaoke

`yt-karaoke` is a Python 3.10+ CLI for auto-downloading YouTube audio, fetching LRC lyric files, and printing synchronized karaoke lyrics word-by-word in your terminal.

## Features

- `yt-dlp` search + download (audio-only best-effort MP3/m4a)
- Automatic lyric discovery (local directory first, then online LRC sources or AI-free generated LRC from plain lyrics)
- Robust LRC parsing: line `[MM:SS.xx]` and inline word `<MM:SS.xx>` timestamps
- `ffplay`/`afplay`-based playback clocked with `time.monotonic()` for smooth sync
- Karaoke display with optional word highlighting or timestamp fallback output
- Cache management and graceful handling of missing ffmpeg, lyrics, or downloads

## Quick Start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python play.py "never gonna give you up"
```

## CLI Reference

```bash
python play.py [--query "text"] [--url URL] [--lrc path] \
			   [--cache] [--no-download] [--highlight] [--debug]
```

- `--query / positional` search term if you do not provide `--url`
- `--url` plays a specific YouTube URL (skips search)
- `--lrc` forces a local lyric file (skips auto-discovery)
- `--cache` keeps downloaded media instead of deleting after playback (default now auto-cleans audio & fetched lyrics)
- `--no-download` skips yt-dlp (expect audio already cached)
- `--highlight` uppercases the active word; fallback prints timestamps per line
- `--debug` enables verbose logging for troubleshooting

## Sample `.lrc`

```
[00:01.00]<00:01.00>This <00:01.45>is <00:02.00>a <00:02.40>test
[00:03.00]Simple line-level lyric without inline tags
```

Place `.lrc` files next to their audio file (same basename) or use `--lrc path`.

## Sample Session

```
$ python play.py "lofi beats"
Searching YouTube for "lofi beats"...
Downloading top match: Cozy Lofi Mix
Attempting to find lyrics locally...
Fetching LRC from web source...
Starting playback (press Ctrl+C to stop)
[00:03.12] ♪ LOFI   LOOPS   ALL   NIGHT ♪
<CURRENT WORD HIGHLIGHTED IN TERMINAL>
```

## Troubleshooting

- **ffmpeg/ffplay missing**: Install via `brew install ffmpeg` (macOS) or download from https://ffmpeg.org/download.html and ensure both `ffmpeg` and `ffplay` are on `PATH`. macOS also ships `afplay` as a fallback.
- **VS Code terminal does not overwrite lines**: Disable word highlighting (`--highlight` off) to fall back to timestamped output.
- **yt-dlp blocked network**: Pass `--url` to provide a direct video link, or set HTTP proxy via environment variables.
- **Lyrics not found**: The app will now fall back to plain-text lyric APIs and auto-generate approximate timestamps. Supply a manual file via `--lrc myfile.lrc` if you want your own.

## Project Structure

- `play.py` – CLI entrypoint & orchestration
- `cli.py` – `argparse` config and parsing helpers
- `downloader.py` – yt-dlp wrappers for search/download + lyric fetch
- `lrc_parser.py` – line + word-level parsing utilities
- `player.py` – ffplay/afplay subprocess playback, timing loop, terminal rendering
- `utils.py` – logging, cache helpers, environment checks
- `tests/test_lrc_parser.py` – parser regression tests
- `samples/example_song.lrc` – demo lyric file
- `samples/example_song.mp3` – 12s sine-wave clip for `--no-download` testing

## Running Tests

```bash
python -m unittest discover -s tests
```
