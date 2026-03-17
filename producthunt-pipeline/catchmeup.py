#!/usr/bin/env python3
"""Fetch today's top Product Hunt products via GraphQL API."""

import json
import sys
import urllib.request
from pathlib import Path

from dotenv import load_dotenv
import os

SCRIPT_DIR = Path(__file__).parent
load_dotenv(SCRIPT_DIR / ".env")

API_URL = "https://api.producthunt.com/v2/api/graphql"
API_KEY = os.getenv("PRODUCTHUNT_API_KEY", "")

QUERY = """
{
  posts(order: VOTES, first: 10) {
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
  }
}
"""

def fetch_products():
    payload = json.dumps({"query": QUERY}).encode()
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
    edges = data.get("data", {}).get("posts", {}).get("edges", [])
    return [e["node"] for e in edges]


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

    print(f"{'=' * 70}")
    print(f"  PRODUCT HUNT — TODAY'S TOP PRODUCTS")
    print(f"{'=' * 70}\n")

    products = fetch_products()
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
