# Hyperinformed

Personal intelligence feed — YouTube + X/Twitter + GitHub + Product Hunt digest.

## "Catch me up"

When the user says "catch me up", run `/catchmeup`. This means:

1. Run all four pipelines (YouTube, Twitter, GitHub, Product Hunt)
2. Summarize everything — grouped by TOPIC not by source/account. Connect different voices discussing the same thing.
3. At the end, highlight the top 3-5 most interesting/notable items across all sources
4. If 0 new items from a source, just note they're caught up on that source

## Pipelines

- **YouTube**: `python3 /Users/GenericPerson1/hyperinformed/youtube-pipeline/catchmeup.py`
- **Twitter/X**: `python3 /Users/GenericPerson1/hyperinformed/twitter-pipeline/catchmeup.py` (requires cookies.json)
- **GitHub**: `python3 /Users/GenericPerson1/hyperinformed/github-pipeline/catchmeup.py`
- **Product Hunt**: `python3 /Users/GenericPerson1/hyperinformed/producthunt-pipeline/catchmeup.py` (requires .env with API key)
