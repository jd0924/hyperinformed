#!/usr/bin/env python3
"""Fetch high-signal Indie Hackers posts via the site's Algolia search API.

Queries posts from the last 7 days by engagement. Posts that clear the
threshold show up every run — recurring appearances mean the post is
genuinely important. Each post is tagged:
  [NEW]    — first time appearing on the leaderboard
  [RISING] — seen before, and upvotes or replies increased since last run

Tracks previous stats in seen.json to compute tags.

Previously this used the Firebase Realtime Database directly, but IH
revoked public read access (returns 401). The site itself uses Algolia
for search, and the search key is exposed in the page config — so we
query that directly. No auth, no rate limits observed.
"""

import json
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
LAST_RUN_FILE = SCRIPT_DIR / "last_run.txt"
SEEN_FILE = SCRIPT_DIR / "seen.json"
OUTPUT_FILE = SCRIPT_DIR / "output.json"

ALGOLIA_URL = "https://N86T1R3OWZ-dsn.algolia.net/1/indexes/discussions/query"
ALGOLIA_APP_ID = "N86T1R3OWZ"
ALGOLIA_API_KEY = "5140dac5e87f47346abbda1a34ee70c3"  # public search-only key
HEADERS = {
    "User-Agent": "Hyperinformed/1.0",
    "X-Algolia-Application-Id": ALGOLIA_APP_ID,
    "X-Algolia-API-Key": ALGOLIA_API_KEY,
    "Content-Type": "application/json",
}

MIN_UPVOTES = 2
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
    """Load previous stats for posts we've surfaced before.

    Format: {post_id: {"views": N, "replies": N, "first_seen": iso, "times": N}}
    Auto-prunes entries older than 14 days.
    """
    if SEEN_FILE.exists():
        data = json.loads(SEEN_FILE.read_text())
        cutoff = (datetime.now(timezone.utc) - timedelta(days=14)).isoformat()
        return {k: v for k, v in data.items() if v.get("first_seen", "") > cutoff}
    return {}


def save_seen(seen):
    SEEN_FILE.write_text(json.dumps(seen, indent=2))


def tag_post(post, seen):
    """Tag a post as [NEW] or [RISING] based on previous stats."""
    prev = seen.get(post["id"])
    if not prev:
        return "NEW"
    if post["upvotes"] > prev.get("upvotes", 0) or post["replies"] > prev["replies"]:
        return "RISING"
    return ""


def fetch_posts_by_engagement():
    """Fetch high-signal posts from the last 7 days via Algolia.

    Filters server-side for minimum engagement, dedups across the
    Algolia partNumber shards (same post can appear multiple times
    with different objectIDs like `post-abc123-1`, `post-abc123-2`),
    and returns the first part of each unique post.
    """
    since_ms = int(
        (datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)).timestamp() * 1000
    )

    body = json.dumps({
        "hitsPerPage": 200,
        "filters": f"createdTimestamp > {since_ms} AND itemType:post",
        "numericFilters": [
            f"numUpvotes >= {MIN_UPVOTES}",
            f"numReplies >= {MIN_REPLIES}",
        ],
    }).encode()

    req = urllib.request.Request(ALGOLIA_URL, data=body, headers=HEADERS)
    resp = urllib.request.urlopen(req, timeout=30)
    data = json.loads(resp.read())

    # Dedup by itemKey (same post appears across part shards)
    by_item = {}
    for hit in data.get("hits", []):
        item_key = hit.get("itemKey", "")
        # itemKey is like "post-5e39db229c" — strip prefix for URL path
        if not item_key.startswith("post-"):
            continue
        post_id = item_key[len("post-"):]
        created_ms = hit.get("createdTimestamp", 0)
        created = datetime.fromtimestamp(created_ms / 1000, tz=timezone.utc)

        # Prefer part 0 (first shard) if we see multiple
        if post_id in by_item and hit.get("partNumber", 0) > by_item[post_id]["_part"]:
            continue

        by_item[post_id] = {
            "id": post_id,
            "title": (hit.get("title") or "").strip(),
            "body": (hit.get("body") or "").strip(),
            "username": hit.get("username", ""),
            "group": hit.get("groupName", ""),
            "upvotes": hit.get("numUpvotes", 0),
            "replies": hit.get("numReplies", 0),
            "link_clicks": hit.get("numLinkClicks", 0),
            "date": created.strftime("%Y-%m-%d %H:%M"),
            "url": f"https://www.indiehackers.com/post/{post_id}",
            "_part": hit.get("partNumber", 0),
        }

    # Strip internal _part field
    for p in by_item.values():
        p.pop("_part", None)
    return list(by_item.values())


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
        print(f"{'=' * 70}\n")

        filtered = fetch_posts_by_engagement()

        # Tag each post and sort by upvotes descending
        for p in filtered:
            p["tag"] = tag_post(p, seen)
        filtered.sort(key=lambda p: p["upvotes"], reverse=True)

        new_count = sum(1 for p in filtered if p["tag"] == "NEW")
        rising_count = sum(1 for p in filtered if p["tag"] == "RISING")
        returning_count = len(filtered) - new_count - rising_count

        if not filtered:
            print(f"  No high-signal posts in the last {LOOKBACK_DAYS} days.\n")
        else:
            for i, p in enumerate(filtered, 1):
                group = f"  [{p['group']}]" if p["group"] else ""
                tag = f"  [{p['tag']}]" if p["tag"] else ""
                body_preview = p["body"][:120].replace("\n", " ")
                print(f"  {i:2}. {p['title'][:80]}")
                print(f"      {p['upvotes']} upvotes, {p['replies']} replies{group}{tag}")
                print(f"      {body_preview}")
                print(f"      {p['url']}")
                print()

        print(f"{'=' * 70}")
        print(f"  {len(filtered)} high-signal posts (last {LOOKBACK_DAYS}d)")
        print(f"  {new_count} new, {rising_count} rising, {returning_count} returning")
        print(f"  Filter: {MIN_UPVOTES}+ upvotes AND {MIN_REPLIES}+ replies")
        print(f"{'=' * 70}")

        # Update seen with current stats
        now = datetime.now(timezone.utc).isoformat()
        for p in filtered:
            prev = seen.get(p["id"])
            seen[p["id"]] = {
                "upvotes": p["upvotes"],
                "replies": p["replies"],
                "first_seen": prev["first_seen"] if prev else now,
                "times": (prev["times"] if prev else 0) + 1,
            }
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
                    "upvotes": p["upvotes"],
                    "replies": p["replies"],
                    "group": p["group"],
                    "tag": p["tag"],
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
