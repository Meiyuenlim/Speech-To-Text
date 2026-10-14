from __future__ import annotations

import shutil
import subprocess
import re
from pathlib import Path


class AudioProcessingError(RuntimeError):
    pass


class AudioPipeline:
    def duration_seconds(self, source: Path) -> float | None:
        """Return duration when ffprobe is available; an unavailable probe is non-fatal."""
        probe = shutil.which("ffprobe")
        if not probe:
            return None
        result = subprocess.run(
            [probe, "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(source)],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            return None
        match = re.search(r"\d+(?:\.\d+)?", result.stdout)
        return float(match.group(0)) if match else None

    def convert_to_wav(self, source: Path, destination: Path, sample_rate: int) -> Path:
        ffmpeg_executable = shutil.which("ffmpeg")
        if ffmpeg_executable is None:
            raise AudioProcessingError("FFmpeg was not found. Install FFmpeg and add it to PATH.")
        destination.parent.mkdir(parents=True, exist_ok=True)
        command = [
            ffmpeg_executable,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(source),
            "-ac",
            "1",
            "-ar",
            str(sample_rate),
            "-vn",
            "-f",
            "wav",
            str(destination),
        ]
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            raise AudioProcessingError(result.stderr.strip() or "FFmpeg could not convert the recording")
        return destination

    def enhance_with_deepfilter(self, source: Path, destination: Path) -> Path:
        executable = shutil.which("deepFilter")
        if not executable:
            raise AudioProcessingError("DeepFilterNet is not installed")
        destination.parent.mkdir(parents=True, exist_ok=True)
        output_dir = destination.parent / f"deepfilter-{destination.stem}"
        output_dir.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(
            [executable, str(source), "--output-dir", str(output_dir)],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise AudioProcessingError(result.stderr.strip() or "DeepFilterNet could not process the recording")
        candidates = sorted(output_dir.glob("*.wav"))
        if not candidates:
            raise AudioProcessingError("DeepFilterNet completed without producing a WAV file")
        shutil.copyfile(candidates[0], destination)
        return destination
