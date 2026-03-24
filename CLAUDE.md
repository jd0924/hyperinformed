# Hyperinformed

Multi-source intelligence feed — YouTube + X/Twitter + GitHub + Product Hunt + Every.to + Hacker News blogs + Kickstarter.

## "Catch me up"

When the user says "catch me up", run `/catchmeup`. This means:

1. Run all seven pipelines (YouTube, Twitter, GitHub, Product Hunt, Every.to, Hacker News, Kickstarter)
2. Summarize everything — grouped by TOPIC not by source/account. Connect different voices discussing the same thing.
3. At the end, highlight the top 3-5 most interesting/notable items across all sources
4. If 0 new items from a source, just note they're caught up on that source

## Pipelines

- **YouTube**: `python3 youtube-pipeline/catchmeup.py`
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
