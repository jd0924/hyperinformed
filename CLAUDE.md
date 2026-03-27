# Hyperinformed

Multi-source intelligence feed — YouTube + X/Twitter + GitHub + Product Hunt + Every.to + Hacker News blogs + Kickstarter.

## Safety Rules

- **Preserve existing config files** — When editing existing config files (Firebase, .env, Info.plist, etc.), ALWAYS read the current file first and preserve existing working values. Never overwrite production config files without explicit confirmation.
- **Never commit secrets** — Never commit or push sensitive credentials, API keys, tokens, or cookies to any repository. Always check for secrets before any git push. Use .env files and .gitignore for all sensitive data.

## Bug Fixing

- **Minimal targeted changes** — When fixing bugs, make minimal targeted changes. If a fix doesn't work after 2 attempts, stop and present a root cause analysis before trying again. Never stack speculative fixes.

## "Catch me up"

When the user says "catch me up", run `/catchmeup`. This means:

1. Run all seven pipelines (YouTube, Twitter, GitHub, Product Hunt, Every.to, Hacker News, Kickstarter)
2. Summarize by PLATFORM — present each platform as its own section, then group by topics within each platform. Do not merge content across platforms.
3. At the end, highlight the top 3-5 most interesting/notable items across all sources
4. If 0 new items from a source, just note they're caught up on that source
5. **Report pipeline failures** — If any pipeline fails or errors during fetch, report it immediately at the top of the summary: which pipeline failed, the error message, and the likely reason for the failure

## Pipelines

- **YouTube**: `python3 youtube-pipeline/catchmeup.py` — Output includes `[SHORT]`, `[VIDEO]`, `[STREAM]`, `[UPCOMING]` tags with duration for each video. When presenting YouTube results, always include the URL for every single video regardless of type (short, video, stream, etc.).
- **Twitter/X**: `python3 twitter-pipeline/catchmeup.py` (requires cookies.json)
- **GitHub**: `python3 github-pipeline/catchmeup.py` (requires `gh auth login`)
- **Product Hunt**: `python3 producthunt-pipeline/catchmeup.py` (requires .env with API key)
- **Every.to**: `python3 every-pipeline/catchmeup.py` (private RSS feed)
- **Hacker News**: `python3 hackernews-pipeline/catchmeup.py` (92 curated blog RSS feeds)
- **Kickstarter**: `python3 kickstarter-pipeline/catchmeup.py` (trending live projects)

## Git & Security Rules

This is a **public repository**. Follow these rules strictly:

- **Never commit personal data files** — even temporarily. Deleting a file later does NOT remove it from git history. Files in `.gitignore` (cookies.json, .env, accounts.txt, subscriptions.csv, last_run.txt) must never be force-added.
- **Always use `git add <specific files>`** — never `git add .` or `git add -A`. This prevents accidentally staging secrets or personal data.
- **Review staged changes before committing** — run `git diff --cached` and check for anything sensitive (tokens, personal handles, emails, API keys).
- **No hardcoded credentials** — API keys, tokens, and feed URLs go in `.env` files (which are gitignored), never in code.
- **Commit email** — all commits must use `jd0924@users.noreply.github.com`, never a personal email.
