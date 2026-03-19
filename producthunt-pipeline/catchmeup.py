#!/usr/bin/env python3
"""Fetch today's top Product Hunt products via GraphQL API."""

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

# Product Hunt's daily cycle resets at midnight Pacific Time.
PT = timezone(timedelta(hours=-7))

QUERY_TEMPLATE = """
{
  posts(order: RANKING, postedAfter: "%s", postedBefore: "%s", first: 20%s) {
    edges {
      node {
        name
        tagline
        votesCount
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


MIN_VOTES = 100


def fetch_products_for_date(date_pt):
    """Fetch products with >= MIN_VOTES for a specific date (in PT), paginating."""
    start = datetime(date_pt.year, date_pt.month, date_pt.day, tzinfo=PT)
    end = start + timedelta(days=1)
    all_products = []
    cursor = None

    for _ in range(10):  # safety cap
        after_clause = f', after: "{cursor}"' if cursor else ""
        query = QUERY_TEMPLATE % (start.isoformat(), end.isoformat(), after_clause)
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
            elif product["votesCount"] == 0:
                # Promoted products (0 votes) — include regardless
                all_products.append(product)
            else:
                below_threshold = True

        if below_threshold:
            break

        page_info = posts.get("pageInfo", {})
        if not page_info.get("hasNextPage"):
            break
        cursor = page_info.get("endCursor")

    return all_products, date_pt


def fetch_products():
    """Fetch today's products; fall back to yesterday if today has none yet."""
    today_pt = datetime.now(PT).date()
    products, date_used = fetch_products_for_date(today_pt)
    if not products:
        yesterday = today_pt - timedelta(days=1)
        products, date_used = fetch_products_for_date(yesterday)
    return products, date_used


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

    products, date_used = fetch_products()
    date_label = date_used.strftime("%A, %B %-d, %Y")

    print(f"{'=' * 70}")
    print(f"  PRODUCT HUNT — TOP PRODUCTS FOR {date_label.upper()}")
    print(f"{'=' * 70}\n")
    if not products:
        print("  No products found.\n")
    else:
        for i, p in enumerate(products, 1):
            topics = [t["node"]["name"] for t in p.get("topics", {}).get("edges", [])]
            topic_str = f"  [{', '.join(topics)}]" if topics else ""
            desc = (p.get("description") or p.get("tagline") or "")[:120]

            print(f"  {i:2}. {p['name']}  ({p['votesCount']} votes)")
            print(f"      {p['tagline']}")
            if desc and desc != p['tagline']:
                print(f"      {desc}")
            print(f"      {p['url']}{topic_str}")
            print()

    print(f"{'=' * 70}")
    print(f"  {len(products)} products")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
