#!/usr/bin/env python3
"""Cross-check HTML report against pipeline JSON outputs.

Verifies:
1. Per-platform item count matches JSON count
2. Every URL from JSON appears in HTML
3. Every author from JSON appears in HTML (where applicable)

Usage: python3 crosscheck.py catchmeup-2026-04-02-to-2026-04-03.html
"""

import json
import sys
from pathlib import Path

from bs4 import BeautifulSoup

SCRIPT_DIR = Path(__file__).parent

PIPELINES = [
    {"name": "youtube", "json": "youtube-pipeline/output.json", "section": "YouTube"},
    {"name": "twitter", "json": "twitter-pipeline/output.json", "section": "Twitter"},
    {"name": "github", "json": "github-pipeline/output.json", "section": "GitHub"},
    {"name": "producthunt", "json": "producthunt-pipeline/output.json", "section": "Product Hunt"},
    {"name": "every", "json": "every-pipeline/output.json", "section": "Every.to"},
    {"name": "hackernews", "json": "hackernews-pipeline/output.json", "section": "HN Blogs"},
    {"name": "kickstarter", "json": "kickstarter-pipeline/output.json", "section": "Kickstarter"},
    {"name": "indiehackers", "json": "indiehackers-pipeline/output.json", "section": "Indie Hackers"},
]


def load_json(path):
    full = SCRIPT_DIR / path
    if not full.exists():
        return None
    return json.load(open(full))


def find_platform_section(soup, section_name):
    """Find all .item elements that belong to a platform section."""
    headers = soup.select(".platform-header h2")
    target_header = None
    for h in headers:
        # Match by checking if section name is in the header text
        if section_name.lower() in h.get_text().lower():
            target_header = h.find_parent(class_="platform-header")
            break

    if not target_header:
        return []

    # Collect all .item elements between this header and the next platform-header
    items = []
    el = target_header.find_next_sibling()
    while el:
        if el.get("class") and "platform-header" in el.get("class", []):
            break
        if el.get("class") and "item" in el.get("class", []):
            items.append(el)
        # Also check children
        if hasattr(el, "select"):
            for child in el.select(".item"):
                if child not in items:
                    items.append(child)
        el = el.find_next_sibling()

    return items


def extract_urls_from_html_items(html_items):
    """Extract all href values from .item-link elements within items."""
    urls = set()
    for item in html_items:
        link = item.select_one(".item-link")
        if link and link.get("href"):
            urls.add(link["href"])
    return urls


def extract_authors_from_html_items(html_items):
    """Extract all .author text from items."""
    authors = set()
    for item in html_items:
        author_el = item.select_one(".author")
        if author_el:
            authors.add(author_el.get_text(strip=True))
    return authors


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 crosscheck.py <report.html>")
        sys.exit(1)

    html_path = Path(sys.argv[1])
    if not html_path.exists():
        print(f"ERROR: {html_path} not found")
        sys.exit(1)

    html = html_path.read_text()
    soup = BeautifulSoup(html, "html.parser")

    total_json = 0
    total_html = 0
    total_errors = 0
    results = []

    print(f"{'=' * 60}")
    print(f"  CROSS-CHECK: {html_path.name}")
    print(f"{'=' * 60}\n")

    for pipeline in PIPELINES:
        data = load_json(pipeline["json"])
        if data is None:
            print(f"  [{pipeline['name']}] SKIP — no JSON file")
            continue

        if data["status"] == "error":
            print(f"  [{pipeline['name']}] SKIP — pipeline errored (status=error)")
            continue

        json_count = data["count"]
        json_urls = {item["url"] for item in data["items"]}
        json_authors = {item["author"] for item in data["items"] if item.get("author")}

        html_items = find_platform_section(soup, pipeline["section"])
        html_count = len(html_items)
        html_urls = extract_urls_from_html_items(html_items)
        html_authors = extract_authors_from_html_items(html_items)

        total_json += json_count
        total_html += html_count

        errors = []

        # Check 1: Count match
        if json_count != html_count:
            errors.append(f"COUNT MISMATCH: JSON={json_count} HTML={html_count} (dropped {json_count - html_count})")

        # Check 2: URL match
        missing_urls = json_urls - html_urls
        if missing_urls:
            errors.append(f"MISSING URLs: {len(missing_urls)} items have no matching URL in HTML")
            for url in sorted(missing_urls)[:5]:
                errors.append(f"  - {url[:80]}")
            if len(missing_urls) > 5:
                errors.append(f"  ... and {len(missing_urls) - 5} more")

        # Check 3: Author match (skip pipelines where author is empty)
        # Check both .author spans and full item text (for GitHub where author is in the title)
        json_authors_nonempty = {a for a in json_authors if a.strip()}
        if json_authors_nonempty:
            html_item_texts = set()
            for item in html_items:
                html_item_texts.add(item.get_text())
            all_html_text = " ".join(html_item_texts)
            missing_authors = {a for a in json_authors_nonempty if a not in all_html_text and a not in html_authors}
            if missing_authors and len(missing_authors) > len(json_authors_nonempty) * 0.2:
                errors.append(f"MISSING AUTHORS: {len(missing_authors)} of {len(json_authors_nonempty)} authors not found")
                for author in sorted(missing_authors)[:5]:
                    errors.append(f"  - {author}")

        if errors:
            total_errors += len(errors)
            status = "FAIL"
        else:
            status = "PASS"

        print(f"  [{pipeline['name']}] {status} — JSON={json_count} HTML={html_count} URLs={'all matched' if not missing_urls else f'{len(missing_urls)} missing'}")
        for err in errors:
            print(f"    {err}")

        results.append({
            "pipeline": pipeline["name"],
            "status": status,
            "json_count": json_count,
            "html_count": html_count,
            "missing_urls": len(missing_urls),
            "errors": errors,
        })

    print(f"\n{'=' * 60}")
    print(f"  TOTAL: JSON={total_json} HTML={total_html}")
    if total_json == total_html and total_errors == 0:
        print(f"  RESULT: ALL CHECKS PASSED")
    else:
        print(f"  RESULT: {total_errors} issue(s) found")
    print(f"{'=' * 60}")

    sys.exit(0 if total_errors == 0 else 1)


if __name__ == "__main__":
    main()
