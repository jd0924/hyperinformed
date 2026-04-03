# Hyperinformed

Multi-source intelligence feed — YouTube + X/Twitter + GitHub + Product Hunt + Every.to + Hacker News blogs + Kickstarter.

## Safety Rules

- **Preserve existing config files** — When editing existing config files (Firebase, .env, Info.plist, etc.), ALWAYS read the current file first and preserve existing working values. Never overwrite production config files without explicit confirmation.
- **Never commit secrets** — Never commit or push sensitive credentials, API keys, tokens, or cookies to any repository. Always check for secrets before any git push. Use .env files and .gitignore for all sensitive data.

## Bug Fixing

- **Minimal targeted changes** — When fixing bugs, make minimal targeted changes. If a fix doesn't work after 2 attempts, stop and present a root cause analysis before trying again. Never stack speculative fixes.

## "Catch me up"

When the user says "catch me up", run `/catchmeup`. Follow these steps exactly:

1. **Fetch** — Run all 7 pipeline scripts in parallel. Each writes `output.json` with structured data. If one fails, it exits cleanly with `status: "error"` in its JSON. No pipeline can crash another.
2. **Group & Write** — Read the 7 `output.json` files. Use LLM judgment to decide topic groupings and write Top 5 highlights. Fill in `templates/report-template.html` with all items. Save as `catchmeup-<start>-to-<end>.html`. Do NOT rewrite CSS/JS — only fill content blocks.
3. **Cross-check** — Run `python3 crosscheck.py <report.html>`. It verifies per-platform item counts, URLs, and authors between JSON and HTML. If ANY check fails, fix the HTML before showing the report.
4. **Open** — Open the HTML in the browser for the user.
5. If 0 new items from a source, note they're caught up and when last run was.
6. **Report pipeline failures** at the top of the status table: which pipeline failed, the error, and the likely reason.
7. **Include everything except ads** — RTs, reposts, quotes, low-engagement posts all stay in. Only filter out pure advertisements with zero informational value.

## Report Format Rules

After running pipelines, produce an **HTML file** (`catchmeup-<start-date>-to-<end-date>.html`) — never markdown. The HTML is the Layer 1 consumption format (read on phone + audio).

### HTML Template
Use `templates/report-template.html` as the base. Copy it, fill in the content blocks (marked with HTML comments), and save as `catchmeup-<start-date>-to-<end-date>.html`. Do NOT rewrite the CSS or JavaScript — they are already in the template. The template uses the **Minimal Editorial** style (Template C): dark #111 background, Georgia serif, warm amber #d4a574 accent, generous whitespace.

### HTML Features (built into template)
- **Tap-to-highlight items** — tapping an item toggles an amber highlight (border + dot). Tapping a link follows it; tapping anywhere else toggles highlight.
- **All links clickable** — every URL opens in a new tab (`target="_blank"`)
- **Sticky header** with live highlight counter badge
- **Bottom action bar** — Clear All, Show Selected (filter to highlighted only), Copy Links (copies title + URL for all highlighted items)
- **Dark theme, phone-optimized** — serif + system font stack, comfortable tap targets, no horizontal scroll
- **Pipeline Status dashboard** at the top — show each pipeline's status (OK/FAILED) and item count

### Structure
- **Pipeline Status table** at the top
- **Top 5 Highlights** summary section after status table
- **One section per platform** — never merge content across platforms
- **Topic subgroups within each platform** — group related items by theme/relevance

### Content Rules
- **Every item must include its URL** — no exceptions, every video/tweet/post/repo/product gets a clickable link
- **Include everything except ads** — include all RTs, reposts, quotes, low-engagement posts. Only filter out pure advertisements with zero informational value. For sponsored YouTube videos, keep the video but note the sponsorship.
- **YouTube** — include channel name, video type tag (`[VIDEO]`, `[SHORT]`, `[STREAM]`, `[UPCOMING]`), and duration
- **Twitter/X** — include all tweets; include author handle and like count for context
- **GitHub** — include language, star count, and one-line description
- **Product Hunt** — include vote count and category
- **Hacker News blogs** — include all posts within the date range; group by topic themes
- **Kickstarter** — include funding percentage, amount raised, and backer count

## Pipelines

Each pipeline prints human-readable text to stdout AND writes structured JSON to `<pipeline>/output.json`. The JSON is the source of truth for cross-checking.

- **YouTube**: `python3 youtube-pipeline/catchmeup.py` — Output includes `[SHORT]`, `[VIDEO]`, `[STREAM]`, `[UPCOMING]` tags with duration for each video. When presenting YouTube results, always include the URL for every single video regardless of type (short, video, stream, etc.).
- **Twitter/X**: `python3 twitter-pipeline/catchmeup.py` (requires cookies.json)
- **GitHub**: `python3 github-pipeline/catchmeup.py` (requires `gh auth login`)
- **Product Hunt**: `python3 producthunt-pipeline/catchmeup.py` (requires .env with API key)
- **Every.to**: `python3 every-pipeline/catchmeup.py` (private RSS feed)
- **Hacker News**: `python3 hackernews-pipeline/catchmeup.py` (92 curated blog RSS feeds)
- **Kickstarter**: `python3 kickstarter-pipeline/catchmeup.py` (trending live projects)

### JSON Output Schema

Every pipeline writes `output.json` with this structure:
```json
{
  "pipeline": "youtube",
  "status": "ok",
  "count": 20,
  "since": "2026-04-01T06:32:00Z",
  "items": [
    {
      "title": "...",
      "url": "...",
      "author": "...",
      "date": "...",
      "description": "...",
      "meta": { }
    }
  ]
}
```

## Cross-Check (mandatory after generating HTML)

Run `python3 crosscheck.py <report.html>` after every report. It checks:

1. **Per-platform item count** — JSON count must equal HTML count for each pipeline individually
2. **URL matching** — every URL from JSON must appear in the HTML
3. **Author matching** — every author from JSON must appear in the HTML

If ANY check fails, fix the HTML and re-run before showing the report to the user. Do NOT silently drop items.

## Git & Security Rules

This is a **public repository**. Follow these rules strictly:

- **Never commit personal data files** — even temporarily. Deleting a file later does NOT remove it from git history. Files in `.gitignore` (cookies.json, .env, accounts.txt, subscriptions.csv, last_run.txt) must never be force-added.
- **Always use `git add <specific files>`** — never `git add .` or `git add -A`. This prevents accidentally staging secrets or personal data.
- **Review staged changes before committing** — run `git diff --cached` and check for anything sensitive (tokens, personal handles, emails, API keys).
- **No hardcoded credentials** — API keys, tokens, and feed URLs go in `.env` files (which are gitignored), never in code.
- **Commit email** — all commits must use `jd0924@users.noreply.github.com`, never a personal email.
