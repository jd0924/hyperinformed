#!/usr/bin/env python3
"""Fetch top Product Hunt products from the past week via GraphQL API.

Runs at most once every 7 days. Uses VOTES ordering over a 7-day window
with the weeklyRank field for official leaderboard positioning.
"""

import json
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv
import os

SCRIPT_DIR = Path(__file__).parent
load_dotenv(SCRIPT_DIR / ".env")

API_URL = "https://api.producthunt.com/v2/api/graphql"
API_KEY = os.getenv("PRODUCTHUNT_API_KEY", "")
OUTPUT_FILE = SCRIPT_DIR / "output.json"
LAST_RUN_FILE = SCRIPT_DIR / "last_run.txt"

MIN_VOTES = 100
RUN_INTERVAL_DAYS = 7

QUERY_TEMPLATE = """
{
  posts(order: VOTES, featured: true, postedAfter: "%s", postedBefore: "%s", first: 20%s) {
    edges {
      node {
        name
        tagline
        votesCount
        weeklyRank
        url
        description
        topics(first: 3) {
          edges {
            node {
              name
            }
          }
        }
      }
    }
    pageInfo {
      hasNextPage
      endCursor
    }
  }
}
"""


def get_last_run():
    if LAST_RUN_FILE.exists():
        text = LAST_RUN_FILE.read_text().strip()
        if text:
            return datetime.fromisoformat(text)
    return None


def save_last_run():
    LAST_RUN_FILE.write_text(datetime.now(timezone.utc).isoformat())


def fetch_weekly_products():
    """Fetch top products from the past 7 days, sorted by votes.

    The window ends yesterday (UTC) to ensure a full day of voting,
    and starts 7 days before that.
    """
    end_date = datetime.now(timezone.utc).date() - timedelta(days=1)
    start_date = end_date - timedelta(days=7)
    start_iso = datetime(start_date.year, start_date.month, start_date.day,
                         tzinfo=timezone.utc).isoformat()
    end_iso = datetime(end_date.year, end_date.month, end_date.day,
                       23, 59, 59, tzinfo=timezone.utc).isoformat()

    all_products = []
    cursor = None

    for _ in range(10):  # safety cap
        after_clause = f', after: "{cursor}"' if cursor else ""
        query = QUERY_TEMPLATE % (start_iso, end_iso, after_clause)
        payload = json.dumps({"query": query}).encode()
        req = urllib.request.Request(
            API_URL,
            data=payload,
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json",
                "User-Agent": "HyperinformedBot/1.0",
            },
        )
        resp = urllib.request.urlopen(req)
        data = json.loads(resp.read())
        posts = data.get("data", {}).get("posts", {})
        edges = posts.get("edges", [])

        below_threshold = False
        for e in edges:
            product = e["node"]
            if product["votesCount"] >= MIN_VOTES:
                all_products.append(product)
            else:
                below_threshold = True

        if below_threshold:
            break

        page_info = posts.get("pageInfo", {})
        if not page_info.get("hasNextPage"):
            break
        cursor = page_info.get("endCursor")

    # Sort by weeklyRank (official leaderboard order), nulls last
    all_products.sort(key=lambda p: p.get("weeklyRank") or 9999)

    return all_products, start_date, end_date


def main():
    if not API_KEY:
        print("ERROR: PRODUCTHUNT_API_KEY not set.")
        print()
        print("1. Go to https://www.producthunt.com/v2/oauth/applications")
        print("2. Click 'Add an Application'")
        print("3. Fill in any name/URL, click 'Create Token'")
        print("4. Copy the Developer Token")
        print(f"5. Create {SCRIPT_DIR / '.env'} with:")
        print(f'   PRODUCTHUNT_API_KEY=your_token_here')
        sys.exit(1)

    # Check if we should skip (ran within the last 7 days)
    last_run = get_last_run()
    if last_run:
        days_since = (datetime.now(timezone.utc) - last_run).total_seconds() / 86400
        if days_since < RUN_INTERVAL_DAYS:
            next_run = last_run + timedelta(days=RUN_INTERVAL_DAYS)
            print(f"{'=' * 70}")
            print(f"  PRODUCT HUNT — WEEKLY (runs every {RUN_INTERVAL_DAYS} days)")
            print(f"{'=' * 70}\n")
            print(f"  Last run: {last_run.strftime('%Y-%m-%d %H:%M UTC')}")
            print(f"  Next run: {next_run.strftime('%Y-%m-%d %H:%M UTC')}")
            print(f"  ({RUN_INTERVAL_DAYS - days_since:.1f} days remaining)\n")
            print(f"{'=' * 70}")
            print(f"  0 products (skipped — too soon)")
            print(f"{'=' * 70}")

            output = {
                "pipeline": "producthunt",
                "status": "ok",
                "count": 0,
                "since": last_run.isoformat(),
                "items": [],
            }
            with open(OUTPUT_FILE, "w") as f:
                json.dump(output, f, indent=2, ensure_ascii=False)
            return

    try:
        products, start_date, end_date = fetch_weekly_products()
        start_label = start_date.strftime("%b %-d")
        end_label = end_date.strftime("%b %-d, %Y")

        print(f"{'=' * 70}")
        print(f"  PRODUCT HUNT — TOP PRODUCTS: {start_label.upper()} – {end_label.upper()}")
        print(f"{'=' * 70}\n")
        if not products:
            print("  No products with 100+ votes this week.\n")
        else:
            for i, p in enumerate(products, 1):
                topics = [t["node"]["name"] for t in p.get("topics", {}).get("edges", [])]
                topic_str = f"  [{', '.join(topics)}]" if topics else ""
                desc = (p.get("description") or p.get("tagline") or "")[:120]
                rank = p.get("weeklyRank")
                rank_str = f"  #{rank} weekly" if rank else ""

                print(f"  {i:2}. {p['name']}  ({p['votesCount']} votes{rank_str})")
                print(f"      {p['tagline']}")
                if desc and desc != p['tagline']:
                    print(f"      {desc}")
                print(f"      {p['url']}{topic_str}")
                print()

        print(f"{'=' * 70}")
        print(f"  {len(products)} products ({start_label} – {end_label})")
        print(f"{'=' * 70}")

        # Write JSON output
        json_items = []
        for p in products:
            topics = [t["node"]["name"] for t in p.get("topics", {}).get("edges", [])]
            tagline = p.get("tagline", "")
            desc = p.get("description", "") or ""
            description = f"{tagline} -- {desc}" if desc and desc != tagline else tagline
            json_items.append({
                "title": p["name"],
                "url": p["url"],
                "author": "",
                "date": f"{start_date.isoformat()} to {end_date.isoformat()}",
                "description": description[:300],
                "meta": {
                    "tagline": tagline,
                    "votes": p.get("votesCount", 0),
                    "weekly_rank": p.get("weeklyRank"),
                    "categories": topics,
                },
            })
        output = {
            "pipeline": "producthunt",
            "status": "ok",
            "count": len(json_items),
            "since": last_run.isoformat() if last_run else "",
            "items": json_items,
        }
        with open(OUTPUT_FILE, "w") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

        save_last_run()

    except Exception as e:
        print(f"\n  [!] Pipeline error: {e}\n")
        print(f"{'=' * 70}")
        print(f"  0 products (pipeline error)")
        print(f"{'=' * 70}")
        output = {
            "pipeline": "producthunt",
            "status": "error",
            "count": 0,
            "since": last_run.isoformat() if last_run else "",
            "error": str(e),
            "items": [],
        }
        with open(OUTPUT_FILE, "w") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()
