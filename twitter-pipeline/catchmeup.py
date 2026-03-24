#!/usr/bin/env python3
"""Fetch recent tweets from followed X accounts via twikit."""

import asyncio
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from twikit import Client

SCRIPT_DIR = Path(__file__).parent
ACCOUNTS_FILE = SCRIPT_DIR / "accounts.txt"
COOKIES_FILE = SCRIPT_DIR / "cookies.json"
LAST_RUN_FILE = SCRIPT_DIR / "last_run.txt"
USER_CACHE_FILE = SCRIPT_DIR / "user_cache.json"


def load_accounts():
    lines = ACCOUNTS_FILE.read_text().strip().splitlines()
    return [l.strip().lstrip("@") for l in lines if l.strip() and not l.startswith("#")]


def get_last_run():
    if LAST_RUN_FILE.exists():
        text = LAST_RUN_FILE.read_text().strip()
        if text:
            return datetime.fromisoformat(text)
    return datetime.now(timezone.utc) - timedelta(days=7)


def save_last_run():
    LAST_RUN_FILE.write_text(datetime.now(timezone.utc).isoformat())


def load_user_cache():
    if USER_CACHE_FILE.exists():
        try:
            return json.loads(USER_CACHE_FILE.read_text())
        except (json.JSONDecodeError, IOError):
            pass
    return {}


def save_user_cache(cache):
    USER_CACHE_FILE.write_text(json.dumps(cache, indent=2))


async def resolve_user(client, username, cache):
    """Get user ID from cache, or look up once and cache it."""
    key = username.lower()
    if key in cache:
        c = cache[key]
        return c["id"], c["screen_name"], c["name"]

    user = await client.get_user_by_screen_name(username)
    cache[key] = {
        "id": user.id,
        "screen_name": user.screen_name,
        "name": user.name,
    }
    return user.id, user.screen_name, user.name


async def fetch_tweets(client, username, since, cache, max_retries=3):
    tweets = []
    for attempt in range(max_retries):
        try:
            user_id, screen_name, display_name = await resolve_user(
                client, username, cache
            )
            result = await client.get_user_tweets(user_id, "Tweets", count=20)
            for tweet in result:
                dt = tweet.created_at_datetime
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                if dt > since:
                    if tweet.retweeted_tweet and not tweet.text:
                        continue
                    url = f"https://x.com/{screen_name}/status/{tweet.id}"
                    text = tweet.full_text or tweet.text or ""
                    display = text.replace("\n", " ")
                    tweets.append({
                        "username": screen_name,
                        "name": display_name,
                        "text": display,
                        "date": dt.strftime("%Y-%m-%d %H:%M"),
                        "url": url,
                        "likes": tweet.favorite_count or 0,
                    })
            return tweets
        except Exception as e:
            err = str(e)
            if "429" in err and attempt < max_retries - 1:
                wait = 15 * (attempt + 1)
                print(f"  [~] Rate limited on @{username}, waiting {wait}s...")
                await asyncio.sleep(wait)
                continue
            print(f"  [!] Error fetching @{username}: {e}")
            return tweets
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

    accounts = load_accounts()
    since = get_last_run()
    first_run = not LAST_RUN_FILE.exists()
    cache = load_user_cache()

    client = Client(language="en-US")

    # Load cookies — support both Cookie-Editor JSON array and simple dict
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

    # Count how many need UserByScreenName lookup (not cached)
    uncached = [u for u in accounts if u.lower() not in cache]
    if uncached:
        print(f"  [~] Resolving {len(uncached)} new user IDs...\n")

    total = 0
    for i, username in enumerate(accounts):
        if i > 0:
            await asyncio.sleep(8)
        tweets = await fetch_tweets(client, username, since, cache)
        if not tweets:
            continue
        label = tweets[0]["name"]
        print(f"  @{tweets[0]['username']} ({label})")
        print(f"  {'-' * (len(label) + len(tweets[0]['username']) + 4)}")
        for t in sorted(tweets, key=lambda x: x["date"], reverse=True):
            print(f"    {t['date']}  [{t['likes']} likes]")
            print(f"    {t['text']}")
            print(f"    {t['url']}\n")
        total += len(tweets)

    # Save cache so next run skips UserByScreenName entirely
    save_user_cache(cache)

    print(f"{'=' * 70}")
    print(f"  {total} new tweet(s) across {len(accounts)} accounts")
    print(f"{'=' * 70}")

    save_last_run()


if __name__ == "__main__":
    asyncio.run(main())
