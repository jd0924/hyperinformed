#!/usr/bin/env python3
"""Fetch recent YouTube videos from subscribed channels via YouTube Data API v3."""

import csv
import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

SCRIPT_DIR = Path(__file__).parent
load_dotenv(SCRIPT_DIR / ".env")

SUBS_FILE = SCRIPT_DIR / "subscriptions.csv"
LAST_RUN_FILE = SCRIPT_DIR / "last_run.txt"
OUTPUT_FILE = SCRIPT_DIR / "output.json"
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


def parse_duration(iso_duration):
    """Parse ISO 8601 duration (e.g. PT1H2M3S) to total seconds."""
    match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso_duration or "")
    if not match:
        return 0
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)
    return hours * 3600 + minutes * 60 + seconds


def format_duration(total_seconds):
    """Format seconds as human-readable duration string."""
    if total_seconds == 0:
        return "0:00"
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    if hours > 0:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


def is_short_url(video_id):
    """Check if youtube.com/shorts/{id} resolves (confirms it's a Short)."""
    url = f"https://www.youtube.com/shorts/{video_id}"
    req = urllib.request.Request(url, method="HEAD")
    req.add_header("User-Agent", "Mozilla/5.0")
    try:
        resp = urllib.request.urlopen(req, timeout=5)
        final_url = resp.geturl()
        return "/shorts/" in final_url
    except Exception:
        return False


def fetch_video_details(video_ids):
    """Batch-fetch duration and live status for up to 50 video IDs."""
    details = {}
    for i in range(0, len(video_ids), 50):
        batch = video_ids[i:i + 50]
        data = api_get("videos", {
            "part": "contentDetails,snippet,liveStreamingDetails",
            "id": ",".join(batch),
        })
        for item in data.get("items", []):
            vid = item["id"]
            duration_str = item.get("contentDetails", {}).get("duration", "")
            live_content = item.get("snippet", {}).get("liveBroadcastContent", "none")
            has_live_details = "liveStreamingDetails" in item
            details[vid] = {
                "duration_seconds": parse_duration(duration_str),
                "duration_str": duration_str,
                "live_broadcast": live_content,
                "is_livestream": has_live_details,
            }
    return details


def classify_video(video_id, duration_seconds, live_broadcast, is_livestream,
                   check_shorts=True):
    """Classify a video as Short, Live, or Video with duration label."""
    if live_broadcast == "live":
        return "LIVE"
    if live_broadcast == "upcoming":
        return "UPCOMING"
    if is_livestream:
        return "STREAM"
    if duration_seconds <= 60 and check_shorts:
        if is_short_url(video_id):
            return "SHORT"
    return "VIDEO"


def get_uploads_playlist_id(channel_id):
    """Channel ID 'UCxxx' -> uploads playlist 'UUxxx' (replace UC with UU)."""
    return "UU" + channel_id[2:]


def fetch_videos(channel_id, channel_name, since):
    """Fetch recent videos from a channel's uploads playlist. Costs 1 API unit."""
    playlist_id = get_uploads_playlist_id(channel_id)

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
            "video_id": video_id,
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

    since = get_last_run()
    first_run = not LAST_RUN_FILE.exists()

    try:
        channels = load_channels()

        print(f"{'=' * 70}")
        if first_run:
            print(f"  FIRST RUN — showing videos from the last 7 days")
        else:
            print(f"  Videos since {since.strftime('%Y-%m-%d %H:%M UTC')}")
        print(f"{'=' * 70}\n")

        # Phase 1: Collect all videos from all channels
        all_videos = []
        errors = 0
        for cid, name in channels:
            try:
                videos = fetch_videos(cid, name, since)
                all_videos.extend(videos)
            except Exception as e:
                print(f"  [!] Error fetching {name}: {e}")
                errors += 1

        # Phase 2: Batch-fetch video details (duration, live status)
        video_ids = [v["video_id"] for v in all_videos if v.get("video_id")]
        details = {}
        if video_ids:
            try:
                details = fetch_video_details(video_ids)
            except Exception as e:
                print(f"  [!] Error fetching video details: {e}")

        # Phase 3: Classify each video and check shorts
        shorts_to_check = []
        for v in all_videos:
            vid = v["video_id"]
            info = details.get(vid, {})
            v["duration_seconds"] = info.get("duration_seconds", 0)
            v["duration"] = format_duration(v["duration_seconds"])
            v["live_broadcast"] = info.get("live_broadcast", "none")
            v["is_livestream"] = info.get("is_livestream", False)

            if v["duration_seconds"] <= 60 and v["live_broadcast"] == "none" and not v["is_livestream"]:
                shorts_to_check.append(v)
            elif v["live_broadcast"] == "live":
                v["type"] = "LIVE"
            elif v["live_broadcast"] == "upcoming":
                v["type"] = "UPCOMING"
            elif v["is_livestream"]:
                v["type"] = "STREAM"
            else:
                v["type"] = "VIDEO"

        # Check short candidates via URL probe
        for v in shorts_to_check:
            if is_short_url(v["video_id"]):
                v["type"] = "SHORT"
                v["url"] = f"https://www.youtube.com/shorts/{v['video_id']}"
            else:
                v["type"] = "VIDEO"

        # Phase 4: Print grouped by channel
        by_channel = {}
        for v in all_videos:
            by_channel.setdefault(v["channel"], []).append(v)

        total = len(all_videos)
        shorts_count = sum(1 for v in all_videos if v.get("type") == "SHORT")
        streams_count = sum(1 for v in all_videos if v.get("type") in ("LIVE", "STREAM"))
        videos_count = total - shorts_count - streams_count

        if all_videos:
            for name in dict.fromkeys(v["channel"] for v in all_videos):
                channel_videos = by_channel.get(name, [])
                if not channel_videos:
                    continue
                print(f"  {name}")
                print(f"  {'-' * len(name)}")
                for v in sorted(channel_videos, key=lambda x: x["date"], reverse=True):
                    tag = v.get("type", "VIDEO")
                    duration = v.get("duration", "")
                    print(f"    {v['date']}  [{tag}] ({duration})  {v['title']}")
                    print(f"    {v['url']}")
                    if v.get("description"):
                        print(f"    {v['description']}")
                    print()

        print(f"{'=' * 70}")
        print(f"  {total} new video(s) across {len(channels)} channels ({errors} errors)")
        print(f"  {videos_count} videos, {shorts_count} shorts, {streams_count} streams")
        print(f"{'=' * 70}")

        # Write JSON output
        json_items = [
            {
                "title": v["title"],
                "url": v["url"],
                "author": v["channel"],
                "date": v["date"],
                "description": v.get("description", "")[:200],
                "meta": {
                    "type": v.get("type", "VIDEO"),
                    "duration": v.get("duration", "0:00"),
                },
            }
            for v in all_videos
        ]
        output = {
            "pipeline": "youtube",
            "status": "ok",
            "count": len(json_items),
            "since": since.isoformat().replace("+00:00", "Z"),
            "items": json_items,
        }
        with open(OUTPUT_FILE, "w") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

        save_last_run()

    except Exception as e:
        print(f"\n  [!] Pipeline error: {e}\n")
        print(f"{'=' * 70}")
        print(f"  0 videos (pipeline error)")
        print(f"{'=' * 70}")
        output = {
            "pipeline": "youtube",
            "status": "error",
            "count": 0,
            "since": since.isoformat().replace("+00:00", "Z"),
            "error": str(e),
            "items": [],
        }
        with open(OUTPUT_FILE, "w") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()
