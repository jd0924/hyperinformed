#!/usr/bin/env python3
"""Fetch recent posts from top Hacker News blogs via RSS/Atom feeds."""

import json
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

import feedparser

SCRIPT_DIR = Path(__file__).parent
OPML_FILE = SCRIPT_DIR / "feeds.opml"
LAST_RUN_FILE = SCRIPT_DIR / "last_run.txt"
OUTPUT_FILE = SCRIPT_DIR / "output.json"


def load_feeds():
    tree = ET.parse(OPML_FILE)
    root = tree.getroot()
    feeds = []
    for outline in root.findall(".//outline[@xmlUrl]"):
        name = outline.get("text", outline.get("title", "Unknown"))
        xml_url = outline.get("xmlUrl")
        html_url = outline.get("htmlUrl", "")
        if xml_url:
            feeds.append({"name": name, "xml_url": xml_url, "html_url": html_url})
    return feeds


def get_last_run():
    if LAST_RUN_FILE.exists():
        text = LAST_RUN_FILE.read_text().strip()
        if text:
            return datetime.fromisoformat(text)
    # First run: default to 7 days ago
    return datetime.now(timezone.utc) - timedelta(days=7)


def save_last_run():
    LAST_RUN_FILE.write_text(datetime.now(timezone.utc).isoformat())


def parse_date(entry):
    for attr in ("published_parsed", "updated_parsed"):
        parsed = getattr(entry, attr, None)
        if parsed:
            return datetime(*parsed[:6], tzinfo=timezone.utc)
    return None


def fetch_posts(feed_info, since):
    feed = feedparser.parse(feed_info["xml_url"])
    posts = []
    for entry in feed.entries:
        published = parse_date(entry)
        if not published or published <= since:
            continue
        posts.append({
            "blog": feed_info["name"],
            "title": entry.get("title", "(no title)"),
            "date": published.strftime("%Y-%m-%d %H:%M"),
            "url": entry.get("link", feed_info["html_url"]),
        })
    return posts


def main():
    feeds = load_feeds()
    since = get_last_run()
    first_run = not LAST_RUN_FILE.exists()

    print(f"{'=' * 70}")
    if first_run:
        print(f"  FIRST RUN — showing posts from the last 7 days")
    else:
        print(f"  Posts since {since.strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"  Checking {len(feeds)} blogs...")
    print(f"{'=' * 70}\n")

    total = 0
    errors = 0
    all_items = []
    for feed_info in feeds:
        try:
            posts = fetch_posts(feed_info, since)
        except Exception as e:
            print(f"  [!] Error fetching {feed_info['name']}: {e}")
            errors += 1
            continue
        if not posts:
            continue
        print(f"  {feed_info['name']}")
        print(f"  {'-' * len(feed_info['name'])}")
        for p in sorted(posts, key=lambda x: x["date"], reverse=True):
            print(f"    {p['date']}  {p['title']}")
            print(f"    {p['url']}\n")
            all_items.append({
                "title": p["title"],
                "url": p["url"],
                "author": p["blog"],
                "date": p["date"],
                "description": "",
                "meta": {"blog": p["blog"]},
            })
        total += len(posts)

    print(f"{'=' * 70}")
    print(f"  {total} new post(s) across {len(feeds)} blogs ({errors} errors)")
    print(f"{'=' * 70}")

    # Write JSON output
    output = {
        "pipeline": "hackernews",
        "status": "ok",
        "count": len(all_items),
        "since": since.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "items": all_items,
    }
    with open(OUTPUT_FILE, "w") as f:
        json.dump(output, f, indent=2)

    save_last_run()


if __name__ == "__main__":
    main()
