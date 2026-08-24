from __future__ import annotations

import math
import os
import subprocess
from typing import List

from app.config.settings import settings

FFPROBE_TIMEOUT_S = 15
FFMPEG_COMPRESS_TIMEOUT_S = 60
FFMPEG_THUMBNAIL_TIMEOUT_S = 30
FFMPEG_FRAMES_TIMEOUT_S = 30
FFMPEG_TRIM_TIMEOUT_S = 30

FRAME_SAMPLE_INTERVAL_SEC = 1  # one sampled frame per second, for food scoring


class VideoCorruptError(Exception):
    """Raised when ffprobe/ffmpeg can't make sense of the input file at all."""


def _run(args: List[str], *, timeout: int) -> subprocess.CompletedProcess:
    # subprocess.run with a list (never a shell string) means every arg is
    # passed to the binary literally -- no shell ever parses/interprets
    # any part of a filename or option, so there's no shell-injection
    # surface here regardless of what a filename or path contains.
    return subprocess.run(
        args,
        capture_output=True,
        timeout=timeout,
        check=False,
    )


def check_duration_ms(local_path: str) -> int:
    """
    Duration via ffprobe, in milliseconds. Raises VideoCorruptError on
    anything ffprobe can't parse a duration out of, rather than letting a
    corrupt file silently pass whatever gate the caller applies to the
    return value.
    """
    result = _run(
        [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            local_path,
        ],
        timeout=FFPROBE_TIMEOUT_S,
    )

    if result.returncode != 0:
        raise VideoCorruptError(
            f"ffprobe failed (exit {result.returncode}): {result.stderr.decode(errors='replace')[:300]}"
        )

    raw = result.stdout.decode(errors="replace").strip()
    try:
        seconds = float(raw)
    except ValueError as exc:
        raise VideoCorruptError(f"ffprobe returned no parseable duration: {raw!r}") from exc

    # Python's float() accepts "nan"/"inf" without raising -- an
    # undecodable/corrupt file can make ffprobe print exactly that instead
    # of erroring outright, which would otherwise silently produce a
    # duration that fails every downstream comparison in a confusing way
    # rather than being caught here as the corrupt file it actually is.
    if not math.isfinite(seconds):
        raise VideoCorruptError(f"ffprobe returned a non-finite duration: {raw!r}")

    return round(seconds * 1000)


def compress_video(local_path: str) -> str:
    """
    Single delivery resolution/bitrate, both from settings -- adaptive
    bitrate is overkill for clips this short. Always outputs a real .mp4
    container regardless of the source extension (the caller's final
    storage key must match -- see key_builder.build_video_processed_key).
    """
    output_path = _swap_suffix(local_path, "-compressed.mp4")

    scale_filter = f"scale=-2:min({settings.video_compression_max_height}\\,ih)"

    result = _run(
        [
            "ffmpeg",
            "-y",
            "-i", local_path,
            "-vf", scale_filter,
            "-c:v", "libx264",
            "-b:v", settings.video_compression_bitrate,
            "-preset", "veryfast",
            "-c:a", "aac",
            "-b:a", "128k",
            output_path,
        ],
        timeout=FFMPEG_COMPRESS_TIMEOUT_S,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"ffmpeg compression failed (exit {result.returncode}): "
            f"{result.stderr.decode(errors='replace')[:500]}"
        )
    return output_path


def generate_thumbnail(video_path: str) -> str:
    output_path = _swap_suffix(video_path, "-thumb.jpg")

    result = _run(
        [
            "ffmpeg",
            "-y",
            "-i", video_path,
            "-ss", "00:00:00.5",  # just past the start -- avoids a black-frame open
            "-vframes", "1",
            output_path,
        ],
        timeout=FFMPEG_THUMBNAIL_TIMEOUT_S,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"ffmpeg thumbnail generation failed (exit {result.returncode}): "
            f"{result.stderr.decode(errors='replace')[:500]}"
        )
    return output_path


def trim_video(local_path: str, start_sec: float, duration_sec: float) -> str:
    """
    Cuts a window out of a source clip -- used by the auto-highlight step
    (see video_processing_worker.py) to pull the best-scoring
    video_max_duration_ms-length window out of a longer upload instead of
    rejecting it outright. Re-encodes rather than stream-copying: `-ss`
    placed before `-i` seeks to the nearest keyframe on a copy, which can
    land noticeably off the requested start on a clip with sparse
    keyframes, and compress_video() runs on the result next regardless so
    a second encode pass here costs nothing extra in practice.
    """
    output_path = _swap_suffix(local_path, "-trimmed.mp4")

    result = _run(
        [
            "ffmpeg",
            "-y",
            "-ss", str(start_sec),
            "-i", local_path,
            "-t", str(duration_sec),
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-c:a", "aac",
            "-b:a", "128k",
            output_path,
        ],
        timeout=FFMPEG_TRIM_TIMEOUT_S,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"ffmpeg trim failed (exit {result.returncode}): "
            f"{result.stderr.decode(errors='replace')[:500]}"
        )
    return output_path


def extract_sample_frames(video_path: str) -> List[str]:
    """
    One sampled frame per second, for the food classifier to score. Frame
    files land in a dedicated directory next to video_path so the caller
    can clean up the whole directory in one shot.
    """
    frame_dir = _swap_suffix(video_path, "-frames")
    os.makedirs(frame_dir, exist_ok=True)

    result = _run(
        [
            "ffmpeg",
            "-y",
            "-i", video_path,
            "-vf", f"fps=1/{FRAME_SAMPLE_INTERVAL_SEC}",
            os.path.join(frame_dir, "frame-%03d.jpg"),
        ],
        timeout=FFMPEG_FRAMES_TIMEOUT_S,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"ffmpeg frame extraction failed (exit {result.returncode}): "
            f"{result.stderr.decode(errors='replace')[:500]}"
        )

    return sorted(
        os.path.join(frame_dir, f) for f in os.listdir(frame_dir)
    )


def _swap_suffix(path: str, suffix: str) -> str:
    base, _ext = os.path.splitext(path)
    return base + suffix
