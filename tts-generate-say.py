#!/usr/bin/env python3
"""Convert a narration text file into MP3 audio using macOS `say` command.

Usage: python3 tts-generate-say.py catchmeup-2026-04-03-to-2026-04-06.narration.txt
       python3 tts-generate-say.py catchmeup-2026-04-03-to-2026-04-06.narration.txt --voice "Ava (Premium)"

Requires: macOS with `say` command, ffmpeg
"""

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

DEFAULT_VOICE = "Ava (Premium)"
SAMPLE_RATE = 22050

# Silence durations in seconds
SILENCE_SECTION = 1.5
SILENCE_TOPIC = 0.8
SILENCE_PAUSE = 0.4


def parse_narration(text):
    """Parse narration text into segments with type markers."""
    segments = []
    lines = text.strip().split("\n")
    current_text = []

    def flush_text():
        joined = " ".join(current_text).strip()
        if joined:
            segments.append(("text", joined))
        current_text.clear()

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("[SECTION]"):
            flush_text()
            segments.append(("section", stripped[len("[SECTION]"):].strip()))
        elif stripped.startswith("[TOPIC]"):
            flush_text()
            segments.append(("topic", stripped[len("[TOPIC]"):].strip()))
        elif stripped == "[PAUSE]":
            flush_text()
            segments.append(("pause", ""))
        else:
            current_text.append(stripped)

    flush_text()
    return segments


def say_to_aiff(text, voice, output_path):
    """Generate audio from text using macOS say command."""
    subprocess.run(
        ["say", "-v", voice, "-o", str(output_path)],
        input=text, text=True, capture_output=True
    )


def make_silence(seconds, output_path):
    """Generate a silent audio file using ffmpeg."""
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i",
        f"anullsrc=r={SAMPLE_RATE}:cl=mono",
        "-t", str(seconds),
        "-ar", str(SAMPLE_RATE), "-ac", "1",
        str(output_path)
    ], capture_output=True)


def main():
    parser = argparse.ArgumentParser(description="Generate MP3 audio from narration via macOS say")
    parser.add_argument("narration_file", help="Path to the .narration.txt file")
    parser.add_argument("--voice", default=DEFAULT_VOICE,
                        help=f"macOS voice name (default: {DEFAULT_VOICE})")
    args = parser.parse_args()

    narration_path = Path(args.narration_file)
    if not narration_path.exists():
        print(f"ERROR: {narration_path} not found", flush=True)
        sys.exit(1)

    mp3_path = Path(str(narration_path).replace(".narration.txt", ".mp3"))

    print(f"{'=' * 60}", flush=True)
    print(f"  macOS SAY TTS GENERATION", flush=True)
    print(f"  Input:  {narration_path.name}", flush=True)
    print(f"  Output: {mp3_path.name}", flush=True)
    print(f"  Voice:  {args.voice}", flush=True)
    print(f"{'=' * 60}\n", flush=True)

    # Parse narration
    text = narration_path.read_text()
    segments = parse_narration(text)
    text_count = sum(1 for t, _ in segments if t == "text")
    print(f"  Parsed {len(segments)} segments ({text_count} text blocks)", flush=True)

    # Synthesize segments
    tmpdir = tempfile.mkdtemp()
    tmpdir_path = Path(tmpdir)
    part_files = []
    idx = 0
    processed = 0

    print("  Synthesizing...", flush=True)
    t0 = time.time()

    for seg_type, content in segments:
        if seg_type == "section":
            # Silence before section
            sil = tmpdir_path / f"part_{idx:05d}_sil.aiff"
            make_silence(SILENCE_SECTION, sil)
            part_files.append(sil)
            idx += 1
            # Section header speech
            aiff = tmpdir_path / f"part_{idx:05d}.aiff"
            say_to_aiff(content + ".", args.voice, aiff)
            part_files.append(aiff)
            idx += 1
            # Silence after
            sil = tmpdir_path / f"part_{idx:05d}_sil.aiff"
            make_silence(SILENCE_TOPIC, sil)
            part_files.append(sil)
            idx += 1

        elif seg_type == "topic":
            sil = tmpdir_path / f"part_{idx:05d}_sil.aiff"
            make_silence(SILENCE_TOPIC, sil)
            part_files.append(sil)
            idx += 1
            aiff = tmpdir_path / f"part_{idx:05d}.aiff"
            say_to_aiff(content + ".", args.voice, aiff)
            part_files.append(aiff)
            idx += 1
            sil = tmpdir_path / f"part_{idx:05d}_sil.aiff"
            make_silence(SILENCE_PAUSE, sil)
            part_files.append(sil)
            idx += 1

        elif seg_type == "pause":
            sil = tmpdir_path / f"part_{idx:05d}_sil.aiff"
            make_silence(SILENCE_PAUSE, sil)
            part_files.append(sil)
            idx += 1

        elif seg_type == "text":
            aiff = tmpdir_path / f"part_{idx:05d}.aiff"
            say_to_aiff(content, args.voice, aiff)
            part_files.append(aiff)
            idx += 1
            processed += 1
            if processed % 50 == 0 or processed == text_count:
                elapsed = time.time() - t0
                print(f"  [{processed}/{text_count}] text segments ({elapsed:.0f}s elapsed)", flush=True)

    synth_time = time.time() - t0
    print(f"\n  Synthesis complete in {synth_time:.1f}s ({len(part_files)} parts)", flush=True)

    # Concatenate with ffmpeg
    print("  Concatenating with ffmpeg...", flush=True)
    t1 = time.time()

    concat_file = tmpdir_path / "concat.txt"
    concat_file.write_text("\n".join(f"file '{f}'" for f in part_files if f.exists()))

    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", str(concat_file),
        "-b:a", "128k", "-ar", str(SAMPLE_RATE), "-ac", "1",
        str(mp3_path)
    ], capture_output=True)

    concat_time = time.time() - t1

    # Cleanup
    shutil.rmtree(tmpdir, ignore_errors=True)

    mp3_size = mp3_path.stat().st_size / (1024 * 1024)

    # Get duration
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(mp3_path)],
            capture_output=True, text=True
        )
        duration = float(result.stdout.strip())
        dur_str = f"{int(duration // 60)}:{int(duration % 60):02d}"
    except Exception:
        dur_str = "unknown"
        duration = 0

    total_time = time.time() - t0

    print(f"\n{'=' * 60}", flush=True)
    print(f"  Done: {mp3_path.name}", flush=True)
    print(f"  Duration:    {dur_str}", flush=True)
    print(f"  Size:        {mp3_size:.1f} MB", flush=True)
    print(f"  Synth time:  {synth_time:.1f}s", flush=True)
    print(f"  Concat time: {concat_time:.1f}s", flush=True)
    print(f"  Total time:  {total_time:.1f}s", flush=True)
    if duration > 0:
        print(f"  RTF:         {total_time / duration:.3f} ({duration / total_time:.0f}x real-time)", flush=True)
    print(f"{'=' * 60}", flush=True)


if __name__ == "__main__":
    main()
