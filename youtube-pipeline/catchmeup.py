#!/usr/bin/env python3
"""Fetch recent YouTube videos from subscribed channels via RSS."""

import csv
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

import feedparser

SCRIPT_DIR = Path(__file__).parent
SUBS_FILE = SCRIPT_DIR / "subscriptions.csv"
LAST_RUN_FILE = SCRIPT_DIR / "last_run.txt"
RSS_URL = "https://www.youtube.com/feeds/videos.xml?channel_id={}"


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
    # First run: default to 7 days ago
    return datetime.now(timezone.utc) - timedelta(days=7)


def save_last_run():
    LAST_RUN_FILE.write_text(datetime.now(timezone.utc).isoformat())


def fetch_videos(channel_id, channel_name, since):
    url = RSS_URL.format(channel_id)
    feed = feedparser.parse(url)
    videos = []
    for entry in feed.entries:
        published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
        if published > since:
            videos.append({
                "channel": channel_name,
                "title": entry.title,
                "date": published.strftime("%Y-%m-%d %H:%M"),
                "url": entry.link,
            })
    return videos


def main():
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
    for cid, name in channels:
        try:
            videos = fetch_videos(cid, name, since)
        except Exception as e:
            print(f"  [!] Error fetching {name}: {e}")
            continue
        if not videos:
            continue
        print(f"  {name}")
        print(f"  {'-' * len(name)}")
        for v in sorted(videos, key=lambda x: x["date"], reverse=True):
            print(f"    {v['date']}  {v['title']}")
            print(f"    {v['url']}\n")
        total += len(videos)

    print(f"{'=' * 70}")
    print(f"  {total} new video(s) across {len(channels)} channels")
    print(f"{'=' * 70}")

    save_last_run()


if __name__ == "__main__":
    main()
