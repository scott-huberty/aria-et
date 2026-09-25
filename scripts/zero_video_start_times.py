"""Losslessly remux videos so their first frame is at timestamp 0.

The Social Interactive clips carry an MP4 edit list that starts playback at
0.033 s. PsychoPy's ffpyplayer backend seeks to 0 after opening a movie and
waits for the player position to read exactly 0, so these clips each hit
PsychoPy's 5 s timeout on every load. Dropping the edit list moves the first
frame to 0 without re-encoding.

Each output is checked against its source: identical decoded frames, identical
frame intervals, and a start time of 0. A file is only replaced if every check
passes.

Usage:
    python scripts/zero_video_start_times.py src/aria_et/assets/abcct/social-interactive/videos/*.mp4
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

import imageio_ffmpeg

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()


def start_time(path: Path) -> float:
    probe = subprocess.run(
        [FFMPEG, "-hide_banner", "-i", str(path)], capture_output=True, text=True
    ).stderr
    return float(probe.split("start: ", 1)[1].split(",", 1)[0])


def frames(path: Path) -> list[tuple[float, str]]:
    """Return (pts_seconds, md5) for every decoded video frame."""
    output = subprocess.run(
        [FFMPEG, "-v", "error", "-i", str(path), "-map", "0:v", "-f", "framemd5", "-"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    rows = []
    timebase = None
    for line in output.splitlines():
        if line.startswith("#tb 0:"):
            numerator, denominator = line.split(":", 1)[1].strip().split("/")
            timebase = int(numerator) / int(denominator)
        elif not line.startswith("#"):
            fields = [field.strip() for field in line.split(",")]
            rows.append((int(fields[2]) * timebase, fields[5]))
    return rows


def remux(source: Path, destination: Path) -> None:
    subprocess.run(
        [
            FFMPEG, "-v", "error", "-y",
            "-ignore_editlist", "1",
            "-i", str(source),
            "-map", "0",
            "-c", "copy",
            str(destination),
        ],
        check=True,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("videos", nargs="+", type=Path)
    args = parser.parse_args(argv)

    failures = 0
    for source in args.videos:
        if start_time(source) == 0:
            print(f"skip   {source.name}: already starts at 0")
            continue
        with tempfile.TemporaryDirectory() as tmp:
            candidate = Path(tmp) / source.name
            remux(source, candidate)
            before, after = frames(source), frames(candidate)
            problems = []
            if [md5 for _, md5 in before] != [md5 for _, md5 in after]:
                problems.append("decoded frames differ")
            if [round(pts, 6) for pts, _ in before] != [round(pts, 6) for pts, _ in after]:
                problems.append("frame timestamps differ")
            if start_time(candidate) != 0:
                problems.append(f"start is {start_time(candidate)}")
            if problems:
                failures += 1
                print(f"FAIL   {source.name}: {'; '.join(problems)}")
                continue
            candidate.replace(source)
        print(f"fixed  {source.name}: {len(before)} frames unchanged, start now 0")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
