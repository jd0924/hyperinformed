#!/usr/bin/env python3
"""Convert a narration text file into MP3 audio using Kokoro TTS.

Usage: python3 tts-generate.py catchmeup-2026-04-02-to-2026-04-03.narration.txt
       python3 tts-generate.py catchmeup-2026-04-02-to-2026-04-03.narration.txt --voice am_adam
"""

import argparse
import re
import sys
import time
from pathlib import Path

import lameenc
import numpy as np
from kokoro_onnx import Kokoro

SCRIPT_DIR = Path(__file__).parent
MODEL_PATH = SCRIPT_DIR / "models" / "kokoro" / "kokoro-v1.0.onnx"
VOICES_PATH = SCRIPT_DIR / "models" / "kokoro" / "voices-v1.0.bin"

DEFAULT_VOICE = "af_heart"
SPEED = 1.0
LANG = "en-us"
SAMPLE_RATE = 24000
MP3_BITRATE = 128
MAX_CHUNK_CHARS = 250

# Silence durations in seconds
SILENCE_SECTION = 1.5
SILENCE_TOPIC = 0.8
SILENCE_PAUSE = 0.4
SILENCE_CHUNK = 0.05  # tiny gap between synthesized chunks


def silence(seconds):
    """Generate silence as a float32 numpy array."""
    return np.zeros(int(SAMPLE_RATE * seconds), dtype=np.float32)


def chunk_text(text, max_chars=MAX_CHUNK_CHARS):
    """Split text into chunks at sentence boundaries, respecting max_chars."""
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    chunks = []
    current = ""
    for sent in sentences:
        if len(current) + len(sent) + 1 > max_chars and current:
            chunks.append(current.strip())
            current = sent
        else:
            current = (current + " " + sent).strip()
    if current:
        chunks.append(current)
    return chunks


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


def synthesize(kokoro, segments, voice):
    """Synthesize all segments into a single audio array."""
    audio_parts = []
    total_segments = sum(1 for t, _ in segments if t == "text")
    processed = 0

    for seg_type, content in segments:
        if seg_type == "section":
            audio_parts.append(silence(SILENCE_SECTION))
            header_text = content + "."
            audio, _ = kokoro.create(header_text, voice=voice, speed=SPEED, lang=LANG)
            audio_parts.append(audio)
            audio_parts.append(silence(SILENCE_TOPIC))

        elif seg_type == "topic":
            audio_parts.append(silence(SILENCE_TOPIC))
            topic_text = content + "."
            audio, _ = kokoro.create(topic_text, voice=voice, speed=SPEED, lang=LANG)
            audio_parts.append(audio)
            audio_parts.append(silence(SILENCE_PAUSE))

        elif seg_type == "pause":
            audio_parts.append(silence(SILENCE_PAUSE))

        elif seg_type == "text":
            chunks = chunk_text(content)
            for chunk in chunks:
                if not chunk.strip():
                    continue
                try:
                    audio, _ = kokoro.create(chunk, voice=voice, speed=SPEED, lang=LANG)
                    audio_parts.append(audio)
                    audio_parts.append(silence(SILENCE_CHUNK))
                except (IndexError, RuntimeError):
                    # Chunk too long for phoneme limit — split in half and retry
                    mid = len(chunk) // 2
                    split_at = chunk.rfind(' ', 0, mid)
                    if split_at == -1:
                        split_at = mid
                    for half in [chunk[:split_at].strip(), chunk[split_at:].strip()]:
                        if half:
                            try:
                                audio, _ = kokoro.create(half, voice=voice, speed=SPEED, lang=LANG)
                                audio_parts.append(audio)
                                audio_parts.append(silence(SILENCE_CHUNK))
                            except (IndexError, RuntimeError):
                                print(f"  [!] Skipping chunk too long for TTS: {half[:50]}...")
            processed += 1
            if processed % 10 == 0 or processed == total_segments:
                print(f"  [{processed}/{total_segments}] text segments synthesized")

    return np.concatenate(audio_parts)


def encode_mp3(audio_array):
    """Encode float32 audio array to MP3 bytes."""
    pcm = (audio_array * 32767).clip(-32768, 32767).astype(np.int16).tobytes()
    encoder = lameenc.Encoder()
    encoder.set_bit_rate(MP3_BITRATE)
    encoder.set_in_sample_rate(SAMPLE_RATE)
    encoder.set_channels(1)
    encoder.set_quality(2)
    return encoder.encode(pcm) + encoder.flush()


def main():
    parser = argparse.ArgumentParser(description="Generate MP3 audio from narration text via Kokoro TTS")
    parser.add_argument("narration_file", help="Path to the .narration.txt file")
    parser.add_argument("--voice", default=DEFAULT_VOICE, help=f"Kokoro voice name (default: {DEFAULT_VOICE})")
    args = parser.parse_args()

    narration_path = Path(args.narration_file)
    if not narration_path.exists():
        print(f"ERROR: {narration_path} not found")
        sys.exit(1)

    # Derive output filename
    mp3_path = narration_path.with_suffix("").with_suffix(".mp3")
    if ".narration" in narration_path.stem:
        mp3_path = Path(str(narration_path).replace(".narration.txt", ".mp3"))

    print(f"{'=' * 60}")
    print(f"  TTS GENERATION")
    print(f"  Input:  {narration_path.name}")
    print(f"  Output: {mp3_path.name}")
    print(f"  Voice:  {args.voice}")
    print(f"{'=' * 60}\n")

    # Load model
    print("  Loading Kokoro model...")
    t0 = time.time()
    kokoro = Kokoro(str(MODEL_PATH), str(VOICES_PATH))
    print(f"  Model loaded in {time.time() - t0:.1f}s\n")

    # Verify voice exists
    voices = kokoro.get_voices()
    if args.voice not in voices:
        print(f"ERROR: Voice '{args.voice}' not found. Available: {', '.join(sorted(voices)[:10])}...")
        sys.exit(1)

    # Parse narration
    text = narration_path.read_text()
    segments = parse_narration(text)
    text_count = sum(1 for t, _ in segments if t == "text")
    print(f"  Parsed {len(segments)} segments ({text_count} text blocks)\n")
    print("  Synthesizing...")
    t0 = time.time()
    audio = synthesize(kokoro, segments, args.voice)
    synth_time = time.time() - t0
    audio_duration = len(audio) / SAMPLE_RATE

    print(f"\n  Synthesis complete: {audio_duration:.0f}s audio in {synth_time:.0f}s")
    print(f"  Encoding to MP3...")

    mp3_data = encode_mp3(audio)
    mp3_path.write_bytes(mp3_data)
    mp3_size_mb = len(mp3_data) / (1024 * 1024)

    print(f"\n{'=' * 60}")
    print(f"  Done: {mp3_path.name}")
    print(f"  Duration: {int(audio_duration // 60)}:{int(audio_duration % 60):02d}")
    print(f"  Size: {mp3_size_mb:.1f} MB")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
