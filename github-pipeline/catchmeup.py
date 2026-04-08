#!/usr/bin/env python3
"""Fetch GitHub trending repos and updates to starred repos."""

import json
import subprocess
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

from bs4 import BeautifulSoup

SCRIPT_DIR = Path(__file__).parent
LAST_RUN_FILE = SCRIPT_DIR / "last_run.txt"
OUTPUT_FILE = SCRIPT_DIR / "output.json"


def _fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return urllib.request.urlopen(req).read().decode()


def get_last_run():
    if LAST_RUN_FILE.exists():
        text = LAST_RUN_FILE.read_text().strip()
        if text:
            return datetime.fromisoformat(text)
    return datetime.now(timezone.utc) - timedelta(days=7)


def save_last_run():
    LAST_RUN_FILE.write_text(datetime.now(timezone.utc).isoformat())


def fetch_trending():
    html = _fetch("https://github.com/trending")
    soup = BeautifulSoup(html, "html.parser")
    repos = []
    for article in soup.select("article.Box-row"):
        name_el = article.select_one("h2 a")
        if not name_el:
            continue
        name = name_el.get_text(strip=True).replace("\n", "").replace(" ", "")
        desc_el = article.select_one("p")
        desc = desc_el.get_text(strip=True) if desc_el else ""
        lang_el = article.select_one('[itemprop="programmingLanguage"]')
        lang = lang_el.get_text(strip=True) if lang_el else ""
        stars_el = article.select("a.Link--muted")
        stars = stars_el[0].get_text(strip=True) if stars_el else ""
        repos.append({"name": name, "desc": desc, "lang": lang, "stars": stars})
    return repos


def gh_api(endpoint):
    result = subprocess.run(
        ["gh", "api", endpoint, "--paginate"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        return []
    # gh --paginate concatenates JSON arrays, fix by wrapping
    raw = result.stdout.strip()
    if raw.startswith("[") and "][" in raw:
        raw = raw.replace("][", ",")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return []


def fetch_starred_updates(since):
    starred = gh_api("user/starred")
    updates = []
    since_str = since.strftime("%Y-%m-%dT%H:%M:%SZ")

    for repo in starred:
        full_name = repo.get("full_name", "")
        desc = repo.get("description", "") or ""
        pushed_at = repo.get("pushed_at", "")
        stars = repo.get("stargazers_count", 0)

        if not pushed_at:
            continue
        pushed = datetime.fromisoformat(pushed_at.replace("Z", "+00:00"))
        if pushed <= since:
            continue

        # Check for new releases
        releases = gh_api(f"repos/{full_name}/releases?per_page=3")
        new_releases = []
        for rel in releases:
            pub = rel.get("published_at", "")
            if pub:
                rel_dt = datetime.fromisoformat(pub.replace("Z", "+00:00"))
                if rel_dt > since:
                    new_releases.append({
                        "tag": rel.get("tag_name", ""),
                        "name": rel.get("name", ""),
                        "date": rel_dt.strftime("%Y-%m-%d"),
                    })

        updates.append({
            "name": full_name,
            "desc": desc[:120],
            "stars": stars,
            "pushed": pushed.strftime("%Y-%m-%d %H:%M"),
            "releases": new_releases,
        })

    return updates


def main():
    since = get_last_run()
    first_run = not LAST_RUN_FILE.exists()

    try:
        # --- Trending ---
        print(f"{'=' * 70}")
        print(f"  GITHUB TRENDING TODAY")
        print(f"{'=' * 70}\n")

        trending = fetch_trending()
        if trending:
            for i, r in enumerate(trending[:25], 1):
                lang_str = f" [{r['lang']}]" if r['lang'] else ""
                stars_str = f" ({r['stars']} stars)" if r['stars'] else ""
                print(f"  {i:2}. {r['name']}{lang_str}{stars_str}")
                if r['desc']:
                    print(f"      {r['desc'][:100]}")
                print()
        else:
            print("  Could not fetch trending repos.\n")

        # --- Starred Updates ---
        print(f"{'=' * 70}")
        if first_run:
            print(f"  STARRED REPO UPDATES — last 7 days")
        else:
            print(f"  STARRED REPO UPDATES — since {since.strftime('%Y-%m-%d %H:%M UTC')}")
        print(f"{'=' * 70}\n")

        updates = fetch_starred_updates(since)
        if updates:
            for u in sorted(updates, key=lambda x: x["pushed"], reverse=True):
                print(f"  {u['name']}  ({u['stars']} stars)")
                if u['desc']:
                    print(f"    {u['desc']}")
                print(f"    Last push: {u['pushed']}")
                for rel in u['releases']:
                    print(f"    NEW RELEASE: {rel['tag']} — {rel['name']} ({rel['date']})")
                print()
        else:
            print("  No updates to starred repos.\n")

        print(f"{'=' * 70}")
        print(f"  {len(trending)} trending | {len(updates)} starred with updates")
        print(f"{'=' * 70}")

        # Write JSON output
        def parse_stars(s):
            s = str(s).replace(",", "").strip()
            try:
                return int(s)
            except ValueError:
                return 0

        json_items = []
        for r in trending[:25]:
            json_items.append({
                "title": r["name"],
                "url": f"https://github.com/{r['name']}",
                "author": r["name"].split("/")[0] if "/" in r["name"] else r["name"],
                "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "description": r.get("desc", "")[:120],
                "meta": {
                    "section": "trending",
                    "language": r.get("lang") or None,
                    "stars": parse_stars(r.get("stars", 0)),
                    "releases": [],
                },
            })
        for u in updates:
            json_items.append({
                "title": u["name"],
                "url": f"https://github.com/{u['name']}",
                "author": u["name"].split("/")[0] if "/" in u["name"] else u["name"],
                "date": u["pushed"],
                "description": u.get("desc", "")[:120],
                "meta": {
                    "section": "starred",
                    "language": None,
                    "stars": u.get("stars", 0),
                    "releases": u.get("releases", []),
                },
            })
        output = {
            "pipeline": "github",
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
        print(f"  0 repos (pipeline error)")
        print(f"{'=' * 70}")
        output = {
            "pipeline": "github",
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
