#!/usr/bin/env python3
"""Fetch high-signal Indie Hackers posts via Firebase API.

Fetches forum posts since last run, filters by engagement:
  - 25+ views OR 5+ replies
No API key needed — Firebase read access is open.
"""

import json
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
LAST_RUN_FILE = SCRIPT_DIR / "last_run.txt"
OUTPUT_FILE = SCRIPT_DIR / "output.json"

FIREBASE_URL = "https://indie-hackers.firebaseio.com/posts.json"
HEADERS = {"User-Agent": "Hyperinformed/1.0"}

MIN_VIEWS = 50
MIN_REPLIES = 2


def get_last_run():
    if LAST_RUN_FILE.exists():
        text = LAST_RUN_FILE.read_text().strip()
        if text:
            return datetime.fromisoformat(text)
    return datetime.now(timezone.utc) - timedelta(days=7)


def save_last_run():
    LAST_RUN_FILE.write_text(datetime.now(timezone.utc).isoformat())


def fetch_posts(since):
    """Fetch posts created since `since`, paginating if needed."""
    since_ms = int(since.timestamp() * 1000)
    all_posts = []

    # Firebase limits results; fetch in batches
    url = (
        f'{FIREBASE_URL}?orderBy="createdTimestamp"'
        f"&startAt={since_ms}"
        f"&limitToFirst=500"
    )
    req = urllib.request.Request(url, headers=HEADERS)
    resp = urllib.request.urlopen(req, timeout=30)
    data = json.loads(resp.read())

    if not data:
        return []

    for post_id, post in data.items():
        created_ms = post.get("createdTimestamp", 0)
        created = datetime.fromtimestamp(created_ms / 1000, tz=timezone.utc)

        if post.get("createdByBannedUser"):
            continue

        all_posts.append({
            "id": post_id,
            "title": (post.get("title") or "").strip(),
            "body": (post.get("body") or "").strip(),
            "username": post.get("username", ""),
            "group": post.get("groupName", ""),
            "views": post.get("numViews", 0),
            "replies": post.get("numReplies", 0),
            "link_clicks": post.get("numLinkClicks", 0),
            "date": created.strftime("%Y-%m-%d %H:%M"),
            "url": f"https://www.indiehackers.com/post/{post_id}",
        })

    return all_posts


def filter_high_signal(posts):
    """Keep posts with 50+ views AND 2+ replies."""
    return [
        p for p in posts
        if p["views"] >= MIN_VIEWS and p["replies"] >= MIN_REPLIES
    ]


def main():
    since = get_last_run()
    first_run = not LAST_RUN_FILE.exists()

    try:
        print(f"{'=' * 70}")
        if first_run:
            print(f"  INDIE HACKERS — FIRST RUN (last 7 days)")
        else:
            print(f"  INDIE HACKERS — Posts since {since.strftime('%Y-%m-%d %H:%M UTC')}")
        print(f"{'=' * 70}\n")

        all_posts = fetch_posts(since)
        filtered = filter_high_signal(all_posts)

        # Sort by views descending
        filtered.sort(key=lambda p: p["views"], reverse=True)

        if not filtered:
            print(f"  No high-signal posts (checked {len(all_posts)} total).\n")
        else:
            for i, p in enumerate(filtered, 1):
                group = f"  [{p['group']}]" if p["group"] else ""
                body_preview = p["body"][:120].replace("\n", " ")
                print(f"  {i:2}. {p['title'][:80]}")
                print(f"      {p['views']} views, {p['replies']} replies{group}")
                print(f"      {body_preview}")
                print(f"      {p['url']}")
                print()

        print(f"{'=' * 70}")
        print(f"  {len(filtered)} high-signal posts (from {len(all_posts)} total)")
        print(f"  Filter: {MIN_VIEWS}+ views AND {MIN_REPLIES}+ replies")
        print(f"{'=' * 70}")

        # Write JSON output
        json_items = [
            {
                "title": p["title"],
                "url": p["url"],
                "author": p["username"],
                "date": p["date"],
                "description": p["body"][:300],
                "meta": {
                    "views": p["views"],
                    "replies": p["replies"],
                    "group": p["group"],
                },
            }
            for p in filtered
        ]
        output = {
            "pipeline": "indiehackers",
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
        print(f"  0 posts (pipeline error)")
        print(f"{'=' * 70}")
        output = {
            "pipeline": "indiehackers",
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
