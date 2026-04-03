#!/usr/bin/env python3
"""Fetch recent tweets from X timeline (Following + For You + Notifications)."""

import asyncio
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from twikit import Client

SCRIPT_DIR = Path(__file__).parent
COOKIES_FILE = SCRIPT_DIR / "cookies.json"
LAST_RUN_FILE = SCRIPT_DIR / "last_run.txt"
OUTPUT_FILE = SCRIPT_DIR / "output.json"


def get_last_run():
    if LAST_RUN_FILE.exists():
        text = LAST_RUN_FILE.read_text().strip()
        if text:
            return datetime.fromisoformat(text)
    return datetime.now(timezone.utc) - timedelta(days=7)


def save_last_run():
    LAST_RUN_FILE.write_text(datetime.now(timezone.utc).isoformat())


def parse_tweet(tweet, source):
    """Extract a dict from a Tweet object. Returns None if no timestamp."""
    dt = tweet.created_at_datetime
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    user = tweet.user
    screen_name = user.screen_name if user else "unknown"
    display_name = user.name if user else screen_name

    is_repost = bool(tweet.retweeted_tweet)
    is_quote = bool(tweet.quote)

    text = tweet.full_text or tweet.text or ""
    if is_repost and tweet.retweeted_tweet:
        rt = tweet.retweeted_tweet
        rt_user = rt.user
        text = rt.full_text or rt.text or text
        screen_name = rt_user.screen_name if rt_user else screen_name
        display_name = rt_user.name if rt_user else display_name

    url = f"https://x.com/{screen_name}/status/{tweet.id}"

    return {
        "id": tweet.id,
        "username": screen_name,
        "name": display_name,
        "text": text.replace("\n", " "),
        "date": dt.strftime("%Y-%m-%d %H:%M"),
        "dt": dt,
        "url": url,
        "likes": tweet.favorite_count or 0,
        "source": source,
        "type": "repost" if is_repost else ("quote" if is_quote else "original"),
    }


async def fetch_timeline(client, fetch_fn, source, since, max_pages=5):
    """Paginate a timeline endpoint back to `since`."""
    tweets = {}
    result = await fetch_fn(count=40)

    for page in range(max_pages):
        if result is None or len(result) == 0:
            break
        reached_cutoff = False
        for tweet in result:
            parsed = parse_tweet(tweet, source)
            if parsed is None:
                continue
            if parsed["dt"] <= since:
                reached_cutoff = True
                break
            tweets[parsed["id"]] = parsed
        if reached_cutoff:
            break
        try:
            result = await result.next()
        except Exception:
            break
        await asyncio.sleep(2)

    return tweets


async def fetch_notifications(client, since, max_pages=5):
    """Paginate notifications back to `since`, extracting linked tweets."""
    tweets = {}
    result = await client.get_notifications("All", count=40)

    for page in range(max_pages):
        if result is None or len(result) == 0:
            break
        for notif in result:
            if notif.tweet:
                parsed = parse_tweet(notif.tweet, "notifications")
                if parsed and parsed["dt"] > since:
                    tweets[parsed["id"]] = parsed
        try:
            result = await result.next()
        except Exception:
            break
        await asyncio.sleep(2)

    return tweets


async def main():
    if not COOKIES_FILE.exists():
        print(f"ERROR: {COOKIES_FILE} not found.")
        print()
        print("Export your X cookies using Cookie-Editor Chrome extension:")
        print("  1. Log in to x.com in Chrome")
        print("  2. Click Cookie-Editor extension icon")
        print("  3. Click Export → JSON format")
        print(f"  4. Save the file as: {COOKIES_FILE}")
        sys.exit(1)

    since = get_last_run()
    first_run = not LAST_RUN_FILE.exists()

    client = Client(language="en-US")

    raw = json.loads(COOKIES_FILE.read_text())
    if isinstance(raw, list):
        cookie_dict = {c["name"]: c["value"] for c in raw if "name" in c and "value" in c}
    else:
        cookie_dict = raw
    client.set_cookies(cookie_dict)

    print(f"{'=' * 70}")
    if first_run:
        print(f"  FIRST RUN — showing tweets from the last 7 days")
    else:
        print(f"  Tweets since {since.strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"{'=' * 70}\n")

    # Fetch all three channels
    all_tweets = {}

    print("  [1/3] Fetching Following timeline...")
    following = await fetch_timeline(
        client, client.get_latest_timeline, "following", since
    )
    all_tweets.update(following)
    print(f"         {len(following)} tweets")

    await asyncio.sleep(3)

    print("  [2/3] Fetching For You timeline...")
    for_you = await fetch_timeline(
        client, client.get_timeline, "for_you", since
    )
    # Only add tweets not already seen in Following
    new_from_fy = {k: v for k, v in for_you.items() if k not in all_tweets}
    all_tweets.update(new_from_fy)
    print(f"         {len(for_you)} tweets ({len(new_from_fy)} unique)")

    await asyncio.sleep(3)

    print("  [3/3] Fetching Notifications...")
    notifs = await fetch_notifications(client, since)
    new_from_notifs = {k: v for k, v in notifs.items() if k not in all_tweets}
    all_tweets.update(new_from_notifs)
    print(f"         {len(notifs)} tweets ({len(new_from_notifs)} unique)")

    print()

    # Display sorted by date
    sorted_tweets = sorted(all_tweets.values(), key=lambda x: x["date"], reverse=True)

    for t in sorted_tweets:
        tag = ""
        if t["type"] == "repost":
            tag = " [repost]"
        elif t["type"] == "quote":
            tag = " [quote]"
        source_tag = f"[{t['source']}]"

        print(f"  {t['date']}  @{t['username']}{tag}  {source_tag}")
        print(f"    {t['text']}")
        print(f"    {t['url']}  [{t['likes']} likes]\n")

    print(f"{'=' * 70}")
    print(f"  {len(sorted_tweets)} unique tweets")
    print(f"    Following: {len(following)} | For You: +{len(new_from_fy)} | Notifications: +{len(new_from_notifs)}")
    print(f"{'=' * 70}")

    # Write JSON output
    json_items = [
        {
            "title": t["text"][:280],
            "url": t["url"],
            "author": f"@{t['username']}",
            "date": t["date"],
            "description": "",
            "meta": {
                "source": t["source"],
                "likes": t["likes"],
                "is_retweet": t["type"] == "repost",
                "is_quote": t["type"] == "quote",
            },
        }
        for t in sorted_tweets
    ]
    output = {
        "pipeline": "twitter",
        "status": "ok",
        "count": len(json_items),
        "since": since.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "items": json_items,
    }
    with open(OUTPUT_FILE, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    save_last_run()


if __name__ == "__main__":
    asyncio.run(main())
