#!/usr/bin/env python3
"""Fetch trending Technology projects on Kickstarter.

Runs at most once every 7 days. Filters to Technology category (id=16),
sorted by popularity, with >100% funded threshold.
"""

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

RUN_INTERVAL_DAYS = 7
CATEGORY_ID = 16  # Technology


def get_last_run():
    if LAST_RUN_FILE.exists():
        text = LAST_RUN_FILE.read_text().strip()
        if text:
            return datetime.fromisoformat(text)
    return None


def save_last_run():
    LAST_RUN_FILE.write_text(datetime.now(timezone.utc).isoformat())


def format_currency(amount, symbol="$"):
    if amount >= 1_000_000:
        return f"{symbol}{amount / 1_000_000:.1f}M"
    if amount >= 1_000:
        return f"{symbol}{amount / 1_000:.0f}K"
    return f"{symbol}{amount:,.0f}"


def fetch_projects():
    """Fetch top live Technology projects sorted by popularity, >100% funded.

    Uses category_id=16 (Technology) and raised=2 (>100% funded).
    Takes top 20 results.
    """
    all_projects = []

    for page in range(1, 4):  # up to 3 pages to get enough results
        params = (
            f"?category_id={CATEGORY_ID}"
            f"&sort=popularity"
            f"&state=live"
            f"&raised=2"
            f"&page={page}"
        )
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

        for p in projects:
            launched_at = p.get("launched_at")
            launched = (
                datetime.fromtimestamp(launched_at, tz=timezone.utc)
                if launched_at else None
            )

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
                "launched": launched.strftime("%Y-%m-%d") if launched else "",
                "url": p.get("urls", {}).get("web", {}).get("project", ""),
            })

    # Sort by percent funded (most traction first), take top 20
    all_projects.sort(key=lambda x: x["pct_funded"], reverse=True)
    return all_projects[:20]


def main():
    # Check if we should skip (ran within the last 7 days)
    last_run = get_last_run()
    if last_run:
        days_since = (datetime.now(timezone.utc) - last_run).total_seconds() / 86400
        if days_since < RUN_INTERVAL_DAYS:
            next_run = last_run + timedelta(days=RUN_INTERVAL_DAYS)
            print(f"{'=' * 70}")
            print(f"  KICKSTARTER — TECHNOLOGY, WEEKLY (runs every {RUN_INTERVAL_DAYS} days)")
            print(f"{'=' * 70}\n")
            print(f"  Last run: {last_run.strftime('%Y-%m-%d %H:%M UTC')}")
            print(f"  Next run: {next_run.strftime('%Y-%m-%d %H:%M UTC')}")
            print(f"  ({RUN_INTERVAL_DAYS - days_since:.1f} days remaining)\n")
            print(f"{'=' * 70}")
            print(f"  0 projects (skipped — too soon)")
            print(f"{'=' * 70}")

            output = {
                "pipeline": "kickstarter",
                "status": "ok",
                "count": 0,
                "since": last_run.isoformat(),
                "items": [],
            }
            with open(OUTPUT_FILE, "w") as f:
                json.dump(output, f, indent=2)
            return

    try:
        print(f"{'=' * 70}")
        print(f"  KICKSTARTER — TOP TECHNOLOGY PROJECTS (>100% FUNDED)")
        print(f"{'=' * 70}\n")

        projects = fetch_projects()

        if not projects:
            print("  No overfunded technology projects found.\n")
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
        print(f"  {len(projects)} project(s)")
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
            "since": datetime.now(timezone.utc).isoformat(),
            "items": json_items,
        }
        with open(OUTPUT_FILE, "w") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

        save_last_run()

    except Exception as e:
        print(f"\n  [!] Pipeline error: {e}\n")
        print(f"{'=' * 70}")
        print(f"  0 projects (pipeline error)")
        print(f"{'=' * 70}")
        output = {
            "pipeline": "kickstarter",
            "status": "error",
            "count": 0,
            "since": datetime.now(timezone.utc).isoformat(),
            "error": str(e),
            "items": [],
        }
        with open(OUTPUT_FILE, "w") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()
