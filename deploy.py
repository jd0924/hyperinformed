#!/usr/bin/env python3
"""Deploy catch-me-up report to Netlify as a single self-contained file.

Usage: python3 deploy.py catchmeup-2026-04-07-to-2026-04-08.html

Embeds the MP3 audio as base64 directly into the HTML, producing one file
with the audio player built in. Deploys to Netlify and prints the URL.
"""

import base64
import shutil
import subprocess
import sys
from pathlib import Path

DEPLOY_DIR = Path(__file__).parent / "deploy"


def embed_audio(html_content, mp3_path):
    """Replace the audio src with a base64 data URI."""
    mp3_bytes = mp3_path.read_bytes()
    b64 = base64.b64encode(mp3_bytes).decode("ascii")
    data_uri = f"data:audio/mpeg;base64,{b64}"

    mp3_filename = mp3_path.name
    html_content = html_content.replace(
        f'src="{mp3_filename}"',
        f'src="{data_uri}"'
    )
    return html_content


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 deploy.py <report.html>")
        sys.exit(1)

    html_path = Path(sys.argv[1])
    if not html_path.exists():
        print(f"ERROR: {html_path} not found")
        sys.exit(1)

    mp3_path = html_path.with_suffix(".mp3")

    # Read HTML
    html_content = html_path.read_text(encoding="utf-8")

    # Embed audio
    if mp3_path.exists():
        mp3_size = mp3_path.stat().st_size / 1024 / 1024
        print(f"  Embedding {mp3_path.name} ({mp3_size:.1f} MB) into HTML...")
        html_content = embed_audio(html_content, mp3_path)
    else:
        print(f"  No MP3 found ({mp3_path.name}) — deploying without audio")

    # Write to deploy directory
    DEPLOY_DIR.mkdir(exist_ok=True)
    dest = DEPLOY_DIR / "index.html"
    dest.write_text(html_content, encoding="utf-8")
    dest_size = dest.stat().st_size / 1024 / 1024
    print(f"  Built deploy/index.html ({dest_size:.1f} MB)")

    # Deploy to Netlify
    print(f"  Deploying to Netlify...")
    result = subprocess.run(
        ["netlify", "deploy", "--prod", "--dir=deploy"],
        capture_output=True, text=True, timeout=120,
    )

    if result.returncode != 0:
        print(f"  [!] Deploy failed: {result.stderr.strip()}")
        sys.exit(1)

    # Extract production URL from output
    for line in result.stdout.splitlines():
        if "Production URL" in line or "Website URL" in line:
            url = line.split(":", 1)[-1].strip().strip("<>")
            # Clean ANSI escape codes
            import re
            url = re.sub(r'\x1b\[[0-9;]*m', '', url)
            print(f"\n  Live: {url}")
            break
    else:
        print(f"\n  Deployed. Check netlify dashboard for URL.")

    # Clean up
    shutil.rmtree(DEPLOY_DIR, ignore_errors=True)


if __name__ == "__main__":
    main()
