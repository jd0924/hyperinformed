#!/usr/bin/env python3
"""Fetch trending Kickstarter projects since last run."""

import json
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
LAST_RUN_FILE = SCRIPT_DIR / "last_run.txt"
OUTPUT_FILE = SCRIPT_DIR / "output.json"

DISCOVER_URL = "https://www.kickstarter.com/discover/advanced.json"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Referer": "https://www.kickstarter.com/discover/advanced",
    "X-Requested-With": "XMLHttpRequest",
}


def get_last_run():
    if LAST_RUN_FILE.exists():
        text = LAST_RUN_FILE.read_text().strip()
        if text:
            return datetime.fromisoformat(text)
    # First run: default to 7 days ago
    return datetime.now(timezone.utc) - timedelta(days=7)


def save_last_run():
    LAST_RUN_FILE.write_text(datetime.now(timezone.utc).isoformat())


def format_currency(amount, symbol="$"):
    if amount >= 1_000_000:
        return f"{symbol}{amount / 1_000_000:.1f}M"
    if amount >= 1_000:
        return f"{symbol}{amount / 1_000:.0f}K"
    return f"{symbol}{amount:,.0f}"


def fetch_projects(since):
    """Fetch trending live projects launched since the last run."""
    all_projects = []

    for page in range(1, 11):  # safety cap
        params = f"?sort=magic&state=live&page={page}"
        req = urllib.request.Request(DISCOVER_URL + params, headers=HEADERS)
        try:
            resp = urllib.request.urlopen(req, timeout=15)
            data = json.loads(resp.read())
        except Exception as e:
            print(f"  [!] Error fetching page {page}: {e}")
            break

        projects = data.get("projects", [])
        if not projects:
            break

        old_count = 0
        for p in projects:
            launched_at = p.get("launched_at")
            if launched_at is None:
                continue
            launched = datetime.fromtimestamp(launched_at, tz=timezone.utc)
            if launched <= since:
                old_count += 1
                continue

            goal = p.get("goal", 0)
            pledged = p.get("pledged", 0)
            pct = int(p.get("percent_funded", 0))
            symbol = p.get("currency_symbol", "$")

            deadline_ts = p.get("deadline")
            deadline_dt = (
                datetime.fromtimestamp(deadline_ts, tz=timezone.utc)
                if deadline_ts
                else None
            )
            days_left = None
            if deadline_dt:
                remaining = (deadline_dt - datetime.now(timezone.utc)).days
                if remaining > 0:
                    days_left = remaining

            all_projects.append({
                "name": p.get("name", "(untitled)"),
                "blurb": p.get("blurb", ""),
                "category": p.get("category", {}).get("name", ""),
                "pledged": pledged,
                "goal": goal,
                "symbol": symbol,
                "pct_funded": pct,
                "backers": p.get("backers_count", 0),
                "staff_pick": p.get("staff_pick", False),
                "days_left": days_left,
                "launched": launched.strftime("%Y-%m-%d"),
                "url": p.get("urls", {}).get("web", {}).get("project", ""),
            })

        # Stop paginating if most projects on this page predate last run
        if old_count > len(projects) * 0.8:
            break

    # Sort by percent funded (most traction first)
    all_projects.sort(key=lambda x: x["pct_funded"], reverse=True)
    return all_projects


def main():
    since = get_last_run()
    first_run = not LAST_RUN_FILE.exists()

    print(f"{'=' * 70}")
    print(f"  KICKSTARTER — TRENDING PROJECTS")
    if first_run:
        print(f"  First run — showing projects launched in the last 7 days")
    else:
        print(f"  Since {since.strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"{'=' * 70}\n")

    projects = fetch_projects(since)

    if not projects:
        print("  No new trending projects found.\n")
    else:
        for i, p in enumerate(projects, 1):
            cat = f"  [{p['category']}]" if p["category"] else ""
            days = f"  {p['days_left']}d left" if p["days_left"] else ""
            pick = " *Staff Pick*" if p["staff_pick"] else ""

            print(f"  {i:2}. {p['name']}  ({p['pct_funded']}% funded{pick})")
            print(f"      {p['blurb'][:120]}")
            print(
                f"      {format_currency(p['pledged'], p['symbol'])} / "
                f"{format_currency(p['goal'], p['symbol'])}  |  "
                f"{p['backers']:,} backers{days}{cat}"
            )
            print(f"      {p['url']}")
            print()

    print(f"{'=' * 70}")
    print(f"  {len(projects)} new project(s)")
    print(f"{'=' * 70}")

    # Write JSON output
    json_items = [
        {
            "title": p["name"],
            "url": p["url"],
            "author": "",
            "date": p["launched"],
            "description": p["blurb"],
            "meta": {
                "pct_funded": p["pct_funded"],
                "pledged": format_currency(p["pledged"], p["symbol"]),
                "goal": format_currency(p["goal"], p["symbol"]),
                "backers": p["backers"],
                "days_left": p["days_left"],
                "category": p["category"],
                "staff_pick": p["staff_pick"],
            },
        }
        for p in projects
    ]
    output = {
        "pipeline": "kickstarter",
        "status": "ok",
        "count": len(json_items),
        "since": since.isoformat().replace("+00:00", "Z"),
        "items": json_items,
    }
    with open(OUTPUT_FILE, "w") as f:
        json.dump(output, f, indent=2)

    save_last_run()


if __name__ == "__main__":
    main()
