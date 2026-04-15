#!/usr/bin/env python3
"""Fetch high-signal Indie Hackers posts via Firebase API.

Queries posts from the last 7 days by engagement, not by creation time.
Tracks previously surfaced post IDs in seen.json to avoid duplicates
across runs. This catches late bloomers that gain traction after their
first day.

No API key needed — Firebase read access is open.
"""

import json
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
LAST_RUN_FILE = SCRIPT_DIR / "last_run.txt"
SEEN_FILE = SCRIPT_DIR / "seen.json"
OUTPUT_FILE = SCRIPT_DIR / "output.json"

FIREBASE_URL = "https://indie-hackers.firebaseio.com/posts.json"
HEADERS = {"User-Agent": "Hyperinformed/1.0"}

MIN_VIEWS = 50
MIN_REPLIES = 2
LOOKBACK_DAYS = 7


def get_last_run():
    if LAST_RUN_FILE.exists():
        text = LAST_RUN_FILE.read_text().strip()
        if text:
            return datetime.fromisoformat(text)
    return datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)


def save_last_run():
    LAST_RUN_FILE.write_text(datetime.now(timezone.utc).isoformat())


def load_seen():
    """Load set of previously surfaced post IDs with their timestamps."""
    if SEEN_FILE.exists():
        data = json.loads(SEEN_FILE.read_text())
        # Prune entries older than 14 days to prevent unbounded growth
        cutoff = (datetime.now(timezone.utc) - timedelta(days=14)).isoformat()
        return {k: v for k, v in data.items() if v > cutoff}
    return {}


def save_seen(seen):
    SEEN_FILE.write_text(json.dumps(seen, indent=2))


def fetch_posts_by_views():
    """Fetch posts from the last 7 days, ordered by creation time.

    Firebase doesn't support ordering by numViews directly when
    filtering by createdTimestamp, so we fetch all recent posts
    and sort client-side.
    """
    since_ms = int(
        (datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)).timestamp() * 1000
    )
    all_posts = []

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


def filter_high_signal(posts, seen):
    """Keep posts with 50+ views AND 2+ replies, excluding already-surfaced."""
    return [
        p for p in posts
        if p["views"] >= MIN_VIEWS
        and p["replies"] >= MIN_REPLIES
        and p["id"] not in seen
    ]


def main():
    since = get_last_run()
    seen = load_seen()
    first_run = not LAST_RUN_FILE.exists()

    try:
        print(f"{'=' * 70}")
        if first_run:
            print(f"  INDIE HACKERS — FIRST RUN (last {LOOKBACK_DAYS} days)")
        else:
            print(f"  INDIE HACKERS — Posts since {since.strftime('%Y-%m-%d %H:%M UTC')}")
        print(f"  Scanning last {LOOKBACK_DAYS} days for high-signal posts")
        print(f"  ({len(seen)} previously surfaced posts excluded)")
        print(f"{'=' * 70}\n")

        all_posts = fetch_posts_by_views()
        filtered = filter_high_signal(all_posts, seen)

        # Sort by views descending — surface the hottest posts first
        filtered.sort(key=lambda p: p["views"], reverse=True)

        if not filtered:
            print(f"  No new high-signal posts (checked {len(all_posts)} total).\n")
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
        print(f"  {len(filtered)} high-signal posts (from {len(all_posts)} in last {LOOKBACK_DAYS}d)")
        print(f"  Filter: {MIN_VIEWS}+ views AND {MIN_REPLIES}+ replies")
        print(f"{'=' * 70}")

        # Mark newly surfaced posts as seen
        now = datetime.now(timezone.utc).isoformat()
        for p in filtered:
            seen[p["id"]] = now
        save_seen(seen)

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
