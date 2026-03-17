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


async def fetch_tweets(client, username, since):
    tweets = []
    try:
        user = await client.get_user_by_screen_name(username)
        result = await client.get_user_tweets(user.id, "Tweets", count=20)
        for tweet in result:
            dt = tweet.created_at_datetime
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            if dt > since:
                # Skip pure retweets
                if tweet.retweeted_tweet and not tweet.text:
                    continue
                url = f"https://x.com/{user.screen_name}/status/{tweet.id}"
                text = tweet.full_text or tweet.text or ""
                # Truncate long tweets for digest
                display = text.replace("\n", " ")
                if len(display) > 280:
                    display = display[:277] + "..."
                tweets.append({
                    "username": user.screen_name,
                    "name": user.name,
                    "text": display,
                    "date": dt.strftime("%Y-%m-%d %H:%M"),
                    "url": url,
                    "likes": tweet.favorite_count or 0,
                })
    except Exception as e:
        print(f"  [!] Error fetching @{username}: {e}")
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

    total = 0
    for i, username in enumerate(accounts):
        if i > 0:
            await asyncio.sleep(2)
        tweets = await fetch_tweets(client, username, since)
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

    print(f"{'=' * 70}")
    print(f"  {total} new tweet(s) across {len(accounts)} accounts")
    print(f"{'=' * 70}")

    save_last_run()


if __name__ == "__main__":
    asyncio.run(main())
