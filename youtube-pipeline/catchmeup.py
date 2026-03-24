#!/usr/bin/env python3
"""Fetch recent YouTube videos from subscribed channels via YouTube Data API v3."""

import csv
import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

SCRIPT_DIR = Path(__file__).parent
load_dotenv(SCRIPT_DIR / ".env")

SUBS_FILE = SCRIPT_DIR / "subscriptions.csv"
LAST_RUN_FILE = SCRIPT_DIR / "last_run.txt"
API_KEY = os.getenv("YOUTUBE_API_KEY", "")
API_BASE = "https://www.googleapis.com/youtube/v3"


def load_channels():
    channels = []
    with open(SUBS_FILE, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            cid = row.get("Channel Id", "").strip()
            name = row.get("Channel Title", "").strip()
            if cid and name:
                channels.append((cid, name))
    return channels


def get_last_run():
    if LAST_RUN_FILE.exists():
        text = LAST_RUN_FILE.read_text().strip()
        if text:
            return datetime.fromisoformat(text)
    return datetime.now(timezone.utc) - timedelta(days=7)


def save_last_run():
    LAST_RUN_FILE.write_text(datetime.now(timezone.utc).isoformat())


def api_get(endpoint, params):
    """Make a YouTube Data API request."""
    params["key"] = API_KEY
    qs = "&".join(f"{k}={urllib.request.quote(str(v))}" for k, v in params.items())
    url = f"{API_BASE}/{endpoint}?{qs}"
    resp = urllib.request.urlopen(url, timeout=15)
    return json.loads(resp.read())


def get_uploads_playlist_id(channel_id):
    """Channel ID 'UCxxx' -> uploads playlist 'UUxxx' (replace UC with UU)."""
    return "UU" + channel_id[2:]


def fetch_videos(channel_id, channel_name, since):
    """Fetch recent videos from a channel's uploads playlist. Costs 1 API unit."""
    playlist_id = get_uploads_playlist_id(channel_id)
    since_str = since.strftime("%Y-%m-%dT%H:%M:%SZ")

    videos = []
    data = api_get("playlistItems", {
        "part": "snippet",
        "playlistId": playlist_id,
        "maxResults": 20,
    })

    for item in data.get("items", []):
        snippet = item["snippet"]
        pub_str = snippet.get("publishedAt", "")
        if not pub_str:
            continue
        published = datetime.fromisoformat(pub_str.replace("Z", "+00:00"))
        if published <= since:
            continue

        video_id = snippet.get("resourceId", {}).get("videoId", "")
        videos.append({
            "channel": channel_name,
            "title": snippet.get("title", ""),
            "date": published.strftime("%Y-%m-%d %H:%M"),
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "description": (snippet.get("description", "") or "")[:200],
        })

    return videos


def main():
    if not API_KEY:
        print("ERROR: YOUTUBE_API_KEY not set.")
        print()
        print("1. Go to https://console.cloud.google.com")
        print("2. Enable YouTube Data API v3")
        print("3. Create an API key under Credentials")
        print(f"4. Create {SCRIPT_DIR / '.env'} with:")
        print("   YOUTUBE_API_KEY=your_key_here")
        sys.exit(1)

    channels = load_channels()
    since = get_last_run()
    first_run = not LAST_RUN_FILE.exists()

    print(f"{'=' * 70}")
    if first_run:
        print(f"  FIRST RUN — showing videos from the last 7 days")
    else:
        print(f"  Videos since {since.strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"{'=' * 70}\n")

    total = 0
    errors = 0
    for cid, name in channels:
        try:
            videos = fetch_videos(cid, name, since)
        except Exception as e:
            print(f"  [!] Error fetching {name}: {e}")
            errors += 1
            continue
        if not videos:
            continue
        print(f"  {name}")
        print(f"  {'-' * len(name)}")
        for v in sorted(videos, key=lambda x: x["date"], reverse=True):
            print(f"    {v['date']}  {v['title']}")
            print(f"    {v['url']}")
            if v["description"]:
                print(f"    {v['description']}")
            print()
        total += len(videos)

    print(f"{'=' * 70}")
    print(f"  {total} new video(s) across {len(channels)} channels ({errors} errors)")
    print(f"{'=' * 70}")

    save_last_run()


if __name__ == "__main__":
    main()
