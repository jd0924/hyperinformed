#!/usr/bin/env python3
"""Fetch recent articles from Every.to via private RSS feed."""

import os
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

SCRIPT_DIR = Path(__file__).parent
load_dotenv(SCRIPT_DIR / ".env")

LAST_RUN_FILE = SCRIPT_DIR / "last_run.txt"
FEED_URL = os.getenv("EVERY_FEED_URL", "")


def get_last_run():
    if LAST_RUN_FILE.exists():
        text = LAST_RUN_FILE.read_text().strip()
        if text:
            return datetime.fromisoformat(text)
    return datetime.now(timezone.utc) - timedelta(days=7)


def save_last_run():
    LAST_RUN_FILE.write_text(datetime.now(timezone.utc).isoformat())


def fetch_articles(since):
    req = urllib.request.Request(
        FEED_URL,
        headers={"User-Agent": "HyperinformedBot/1.0"},
    )
    resp = urllib.request.urlopen(req)
    root = ET.fromstring(resp.read())

    articles = []
    for item in root.iter("item"):
        title = item.findtext("title", "").strip()
        link = item.findtext("link", "").strip()
        description = item.findtext("description", "").strip()
        pub_date_str = item.findtext("pubDate", "").strip()

        if pub_date_str:
            # Every.to uses "2026-03-18 13:00:00 UTC" format
            clean = pub_date_str.replace(" UTC", "+00:00")
            pub_date = datetime.fromisoformat(clean)
        else:
            pub_date = None

        if pub_date and pub_date <= since:
            continue

        # Strip HTML tags and truncate for digest
        display = re.sub(r"<[^>]+>", "", description).strip()
        display = re.sub(r"\s+", " ", display)
        if len(display) > 300:
            display = display[:297] + "..."

        articles.append({
            "title": title,
            "url": link,
            "date": pub_date.strftime("%Y-%m-%d %H:%M") if pub_date else "unknown",
            "summary": display,
        })

    return articles


def main():
    if not FEED_URL:
        print("ERROR: EVERY_FEED_URL not set.")
        print()
        print("1. Log in to every.to and find your private RSS feed URL")
        print(f"2. Create {SCRIPT_DIR / '.env'} with:")
        print("   EVERY_FEED_URL=https://every.to/feeds/YOUR_TOKEN.xml")
        sys.exit(1)

    since = get_last_run()
    since_label = since.strftime("%Y-%m-%d %H:%M UTC")

    print(f"{'=' * 70}")
    print(f"  EVERY.TO — NEW ARTICLES SINCE {since_label}")
    print(f"{'=' * 70}\n")

    articles = fetch_articles(since)

    if not articles:
        print(f"  No new articles since last run ({since_label}).\n")
    else:
        for i, a in enumerate(articles, 1):
            print(f"  {i:2}. {a['title']}")
            print(f"      {a['date']}")
            if a["summary"]:
                print(f"      {a['summary']}")
            print(f"      {a['url']}")
            print()

    print(f"{'=' * 70}")
    print(f"  {len(articles)} articles")
    print(f"{'=' * 70}")

    save_last_run()


if __name__ == "__main__":
    main()
