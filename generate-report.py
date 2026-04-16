#!/usr/bin/env python3
"""Generate catch-me-up HTML report from a grouping plan + pipeline output.json files.

Usage: python3 generate-report.py <plan.json>

The plan.json contains LLM editorial decisions (topic groupings, highlights).
This script reads the plan + all output.json files and renders the HTML report.
"""

import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
TEMPLATE_FILE = SCRIPT_DIR / "templates" / "report-template.html"

PIPELINES = {
    "youtube": {"json": "youtube-pipeline/output.json", "section": "YouTube", "unit": "videos"},
    "twitter": {"json": "twitter-pipeline/output.json", "section": "Twitter / X", "unit": "tweets"},
    "github": {"json": "github-pipeline/output.json", "section": "GitHub", "unit": "repos"},
    "producthunt": {"json": "producthunt-pipeline/output.json", "section": "Product Hunt", "unit": "products"},
    "every": {"json": "every-pipeline/output.json", "section": "Every.to", "unit": "posts"},
    "hackernews": {"json": "hackernews-pipeline/output.json", "section": "HN Blogs", "unit": "posts"},
    "kickstarter": {"json": "kickstarter-pipeline/output.json", "section": "Kickstarter", "unit": "projects"},
    "indiehackers": {"json": "indiehackers-pipeline/output.json", "section": "Indie Hackers", "unit": "posts"},
}


def esc(s):
    """Escape HTML special chars, preserving existing entities."""
    if not s:
        return ""
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def esc_light(s):
    """Light escape — only < and > (for content that may already have &amp; etc)."""
    if not s:
        return ""
    return s.replace("<", "&lt;").replace(">", "&gt;")


def render_item(title, meta_html, url, desc=""):
    """Render a single item div."""
    link_display = url.replace("https://", "").replace("http://", "")[:60]
    desc_block = f'  <div class="item-desc">{esc_light(desc)}</div>\n' if desc else ""
    return (
        f'<div class="item" onclick="toggleHighlight(this)">\n'
        f'  <div class="item-title">{esc_light(title)}</div>\n'
        f'  <div class="item-meta">{meta_html}</div>\n'
        f'{desc_block}'
        f'  <a class="item-link" href="{url}" target="_blank" onclick="event.stopPropagation()">{link_display}</a>\n'
        f'</div>\n'
    )


def render_youtube(item):
    meta = item["meta"]
    author = esc(item["author"])
    return render_item(
        item["title"],
        f'<span class="author">{author}</span> <span class="type-tag">{meta["type"]}</span> <span>{meta["duration"]}</span>',
        item["url"],
        item.get("description", "")[:200],
    )


def render_twitter(item):
    meta = item["meta"]
    likes = meta.get("likes", 0)
    likes_str = f"{likes:,} likes"
    rt_tag = ""
    if meta.get("is_retweet"):
        rt_tag = " [repost]"
    elif meta.get("is_quote"):
        rt_tag = " [quote]"
    return render_item(
        item["title"] + rt_tag,
        f'<span class="author">{esc(item["author"])}</span> <span>{likes_str}</span>',
        item["url"],
    )


def render_github(item):
    meta = item["meta"]
    lang = meta.get("language") or ""
    stars = meta.get("stars", 0)
    releases = meta.get("releases", [])
    lang_tag = f'<span class="type-tag">{lang}</span> ' if lang else ""
    rel_str = f" | {releases[0]['tag']}" if releases else ""
    section_tag = f'<span class="type-tag">{meta["section"]}</span>'
    return render_item(
        item["title"],
        f'{lang_tag}<span>{stars:,} stars{rel_str}</span> {section_tag}',
        item["url"],
        item.get("description", ""),
    )


def render_producthunt(item):
    meta = item["meta"]
    votes = meta.get("votes", 0)
    cats = meta.get("categories", [])
    rank = meta.get("weekly_rank")
    rank_str = f" #{rank} weekly" if rank else ""
    cat_str = ", ".join(cats) if cats else ""
    return render_item(
        item["title"],
        f'<span>{votes} votes{rank_str}</span> <span class="type-tag">{cat_str}</span>',
        item["url"],
        item.get("description", "")[:200],
    )


def render_hackernews(item):
    meta = item["meta"]
    score = meta.get("score", 0)
    comments = meta.get("comments", 0)
    if score:
        meta_html = f'<span class="author">{esc(item["author"])}</span> <span>{score} pts, {comments} comments</span>'
    else:
        meta_html = f'<span class="author">{esc(item["author"])}</span>'
    return render_item(item["title"], meta_html, item["url"])


def render_kickstarter(item):
    meta = item["meta"]
    pct = meta.get("pct_funded", 0)
    pledged = meta.get("pledged", "")
    goal = meta.get("goal", "")
    backers = meta.get("backers", 0)
    days = meta.get("days_left")
    pick = " (Staff Pick)" if meta.get("staff_pick") else ""
    days_str = f" <span>{days}d left</span>" if days else ""
    return render_item(
        item["title"] + pick,
        f'<span class="type-tag">{pct}% funded</span> <span>{pledged} / {goal}</span> <span>{backers:,} backers</span>{days_str}',
        item["url"],
        item.get("description", ""),
    )


def render_indiehackers(item):
    meta = item["meta"]
    # Support both new "upvotes" and legacy "views" keys
    engagement = meta.get("upvotes", meta.get("views", 0))
    engagement_label = "upvotes" if "upvotes" in meta else "views"
    replies = meta.get("replies", 0)
    group = meta.get("group", "")
    tag = meta.get("tag", "")
    group_tag = f' <span class="type-tag">{group}</span>' if group else ""
    status_tag = f' <span class="type-tag">{tag}</span>' if tag else ""
    return render_item(
        item["title"],
        f'<span class="author">{esc(item["author"])}</span> <span>{engagement} {engagement_label}, {replies} replies</span>{group_tag}{status_tag}',
        item["url"],
        item.get("description", "")[:200],
    )


RENDERERS = {
    "youtube": render_youtube,
    "twitter": render_twitter,
    "github": render_github,
    "producthunt": render_producthunt,
    "hackernews": render_hackernews,
    "kickstarter": render_kickstarter,
    "indiehackers": render_indiehackers,
    "every": lambda item: render_item(
        item["title"],
        f'<span class="author">{esc(item["author"])}</span>',
        item["url"],
        item.get("description", "")[:200],
    ),
}


def render_platform(pipeline_name, data, topics, renderer):
    """Render all items for a platform, grouped by topics from the plan."""
    html = ""
    rendered_indices = set()

    # Build URL -> list of item indices for lookup
    url_to_indices = {}
    for idx, item in enumerate(data["items"]):
        url_to_indices.setdefault(item["url"], []).append(idx)

    if topics:
        for topic_name, urls in topics.items():
            topic_items = []
            for u in urls:
                for idx in url_to_indices.get(u, []):
                    if idx not in rendered_indices:
                        topic_items.append((idx, data["items"][idx]))
                        rendered_indices.add(idx)
                        break  # take first unrendered match per URL per topic
            if not topic_items:
                continue
            html += f'<div class="topic">{esc(topic_name)}</div>\n'
            for idx, item in topic_items:
                html += renderer(item)

        # Catch any items not assigned to a topic
        for idx, item in enumerate(data["items"]):
            if idx not in rendered_indices:
                html += renderer(item)
    else:
        for item in data["items"]:
            html += renderer(item)

    return html


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 generate-report.py <plan.json>")
        sys.exit(1)

    plan_path = Path(sys.argv[1])
    if not plan_path.exists():
        print(f"ERROR: {plan_path} not found")
        sys.exit(1)

    plan = json.loads(plan_path.read_text())
    template = TEMPLATE_FILE.read_text()

    date_range = plan["date_range"]
    audio_file = plan["audio_file"]
    output_file = plan.get("output_file", f"catchmeup-{date_range.replace(' ', '').replace('–', '-to-').lower()}.html")
    highlights = plan["highlights"]
    topic_assignments = plan.get("topics", {})
    skipped_messages = plan.get("skipped", {})

    # Load all pipeline data
    pipeline_data = {}
    for name, info in PIPELINES.items():
        json_path = SCRIPT_DIR / info["json"]
        if json_path.exists():
            pipeline_data[name] = json.load(open(json_path))
        else:
            pipeline_data[name] = {"status": "error", "count": 0, "items": []}

    # Dedup items within each pipeline
    for name, data in pipeline_data.items():
        seen = set()
        deduped = []
        for item in data["items"]:
            # GitHub items can legitimately share a URL across trending/starred
            if name == "github":
                key = item["url"] + "|" + item["meta"].get("section", "")
            else:
                key = item["url"]
            if key not in seen:
                seen.add(key)
                deduped.append(item)
        data["items"] = deduped
        data["count"] = len(deduped)

    # === BUILD HTML ===
    html = template

    # Date range
    html = html.replace("<!-- DATE RANGE -->", date_range, 2)
    html = html.replace("<!-- AUDIO_FILE -->", audio_file)

    # --- Status table ---
    status_html = ""
    for name, info in PIPELINES.items():
        data = pipeline_data[name]
        badge = "ok" if data["status"] == "ok" else "fail"
        status_html += (
            f'<div class="status-row"><span class="name">{info["section"]}</span>'
            f'<div><span class="status-badge {badge}">{badge.upper()}</span>'
            f'<span class="status-count">{data["count"]}</span></div></div>\n'
        )
    # Replace the status table comment block
    import re
    html = re.sub(
        r'<!-- One row per pipeline\..*?-->',
        status_html,
        html,
        flags=re.DOTALL,
    )

    # --- Highlights ---
    hl_html = ""
    for i, h in enumerate(highlights, 1):
        hl_html += (
            f'<div class="hl-item">\n'
            f'  <span class="num">{i}.</span><span class="hl-title">{h["title"]}</span>\n'
            f'  <div class="hl-desc">{h["desc"]}</div>\n'
            f'</div>\n'
        )
    html = re.sub(
        r'<!-- One per highlight\..*?-->',
        hl_html,
        html,
        flags=re.DOTALL,
    )

    # --- Platform sections ---
    # For each platform, replace the header count and the example comment block
    for name, info in PIPELINES.items():
        data = pipeline_data[name]
        section = info["section"]
        unit = info["unit"]
        count = data["count"]

        # Replace count in header
        html = html.replace(
            f'<h2>{section}<span class="pcount"><!-- COUNT --> {unit}</span></h2>',
            f'<h2>{section}<span class="pcount"> {count} {unit}</span></h2>',
        )
        # Also handle "<!-- COUNT or FAILED -->" for Every.to
        html = html.replace(
            f'<h2>{section}<span class="pcount"><!-- COUNT or FAILED --></span></h2>',
            f'<h2>{section}<span class="pcount"> {count} {unit}</span></h2>',
        )

    # Replace each platform's example comment block with rendered content
    # YouTube
    yt_content = render_platform("youtube", pipeline_data["youtube"], topic_assignments.get("youtube"), render_youtube)
    html = re.sub(r'<!-- TOPIC GROUPS AND ITEMS GO HERE\. Example:\n<div class="topic">Topic Name</div>.*?-->\n\n<!-- TWITTER', yt_content + '\n<!-- TWITTER', html, flags=re.DOTALL)

    # Twitter
    tw_content = render_platform("twitter", pipeline_data["twitter"], topic_assignments.get("twitter"), render_twitter)
    html = re.sub(r'<!-- TOPIC GROUPS AND ITEMS GO HERE\. Example:\n<div class="topic">Topic Name</div>.*?-->\n\n<!-- GITHUB', tw_content + '\n<!-- GITHUB', html, flags=re.DOTALL)

    # GitHub
    gh_content = render_platform("github", pipeline_data["github"], topic_assignments.get("github"), render_github)
    html = re.sub(r'<!-- TOPIC GROUPS AND ITEMS GO HERE\. Example:\n<div class="topic">Trending Today</div>.*?-->\n\n<!-- PRODUCTHUNT', gh_content + '\n<!-- PRODUCTHUNT', html, flags=re.DOTALL)

    # Product Hunt
    if pipeline_data["producthunt"]["count"] > 0:
        ph_content = render_platform("producthunt", pipeline_data["producthunt"], topic_assignments.get("producthunt"), render_producthunt)
    else:
        ph_content = f'<div style="padding:16px 20px;color:var(--dim);font-family:-apple-system,system-ui,sans-serif;font-size:14px;">{skipped_messages.get("producthunt", "No products")}</div>\n'
    html = re.sub(r'<!-- TOPIC GROUPS AND ITEMS GO HERE\. Example:\n<div class="topic">Developer Tools</div>.*?-->\n\n<!-- EVERY', ph_content + '\n<!-- EVERY', html, flags=re.DOTALL)

    # Every.to
    if pipeline_data["every"]["count"] > 0:
        ev_content = render_platform("every", pipeline_data["every"], topic_assignments.get("every"), RENDERERS["every"])
    else:
        ev_content = f'<div style="padding:16px 20px;color:var(--dim);font-family:-apple-system,system-ui,sans-serif;font-size:14px;">{skipped_messages.get("every", "All caught up")}</div>\n'
    html = re.sub(r'<!-- If failed:.*?If OK, items go here same pattern as above -->\n\n<!-- HACKERNEWS', ev_content + '\n<!-- HACKERNEWS', html, flags=re.DOTALL)

    # HN
    hn_content = render_platform("hackernews", pipeline_data["hackernews"], topic_assignments.get("hackernews"), render_hackernews)
    html = re.sub(r'<!-- TOPIC GROUPS AND ITEMS GO HERE\. Example:\n<div class="topic">Apple at 50</div>.*?-->\n\n<!-- KICKSTARTER', hn_content + '\n<!-- KICKSTARTER', html, flags=re.DOTALL)

    # Kickstarter
    if pipeline_data["kickstarter"]["count"] > 0:
        ks_content = render_platform("kickstarter", pipeline_data["kickstarter"], topic_assignments.get("kickstarter"), render_kickstarter)
    else:
        ks_content = f'<div style="padding:16px 20px;color:var(--dim);font-family:-apple-system,system-ui,sans-serif;font-size:14px;">{skipped_messages.get("kickstarter", "No projects")}</div>\n'
    html = re.sub(r'<!-- ITEMS GO HERE\. Example:.*?-->\n\n<!-- INDIEHACKERS', ks_content + '\n<!-- INDIEHACKERS', html, flags=re.DOTALL)

    # Indie Hackers
    if pipeline_data["indiehackers"]["count"] > 0:
        ih_content = render_platform("indiehackers", pipeline_data["indiehackers"], topic_assignments.get("indiehackers"), render_indiehackers)
    else:
        ih_content = f'<div style="padding:16px 20px;color:var(--dim);font-family:-apple-system,system-ui,sans-serif;font-size:14px;">{skipped_messages.get("indiehackers", "No posts")}</div>\n'
    html = re.sub(r'<!-- TOPIC GROUPS AND ITEMS GO HERE\. Example:\n<div class="topic">Building in Public</div>.*?-->\n\n<!-- ACTION BAR', ih_content + '\n<!-- ACTION BAR', html, flags=re.DOTALL)

    # Write output
    output_path = SCRIPT_DIR / output_file
    output_path.write_text(html, encoding="utf-8")

    # Verify
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    item_count = len(soup.select(".item"))
    topic_count = len(soup.select(".topic"))
    print(f"  Generated: {output_file}")
    print(f"  Size: {len(html):,} chars")
    print(f"  Items: {item_count}")
    print(f"  Topics: {topic_count}")


if __name__ == "__main__":
    main()
