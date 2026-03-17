# Hyperinformed

A multi-source intelligence feed that aggregates content from YouTube, X/Twitter, GitHub, and Product Hunt into a single catch-me-up digest. Built to work with [Claude Code](https://claude.ai/claude-code) as a `/catchmeup` slash command.

## What it does

You say `/catchmeup` and get a topic-grouped summary of everything that happened since you last checked — across all your feeds. New YouTube videos, tweets from people you follow, trending GitHub repos, top Product Hunt launches. All summarized and connected by theme, not listed by source.

```
/catchmeup            # all 4 sources
/catchmeup youtube    # just YouTube
/catchmeup x          # just Twitter
/catchmeup gh         # just GitHub
/catchmeup ph         # just Product Hunt
/catchmeup youtube x  # mix and match
```

## Setup

### Prerequisites

- Python 3.10+
- [Claude Code](https://claude.ai/claude-code)
- [GitHub CLI](https://cli.github.com/) (`brew install gh`)

### Install dependencies

```bash
git clone https://github.com/jd0924/hyperinformed.git
cd hyperinformed
pip install -r requirements.txt
```

### Install the slash command

Copy the slash command into your Claude Code commands:

```bash
mkdir -p ~/.claude/commands
cp catchmeup.md ~/.claude/commands/catchmeup.md
```

Then edit `~/.claude/commands/catchmeup.md` and replace `HYPERINFORMED_PATH` with the absolute path to your cloned repo (e.g. `/Users/you/hyperinformed`).

### Configure each pipeline

#### YouTube

Export your subscriptions from [Google Takeout](https://takeout.google.com/) (select YouTube only), then copy the CSV:

```bash
cp youtube-pipeline/subscriptions.csv.example youtube-pipeline/subscriptions.csv
# Replace with your actual subscriptions.csv from Takeout
```

The CSV format is `Channel Id,Channel Url,Channel Title` — one channel per row.

#### Twitter / X

1. Install the [Cookie-Editor](https://cookie-editor.com/) browser extension
2. Go to x.com and log in
3. Click Cookie-Editor → Export (JSON)
4. Save as `twitter-pipeline/cookies.json`
5. Add accounts to follow:

```bash
cp twitter-pipeline/accounts.txt.example twitter-pipeline/accounts.txt
# Edit accounts.txt — one @handle per line, # for comments
```

Cookies expire periodically — re-export when the script stops working.

#### GitHub

```bash
gh auth login
```

That's it. The script fetches trending repos and tracks updates to your starred repos automatically.

#### Product Hunt

1. Go to [producthunt.com/v2/oauth/applications](https://www.producthunt.com/v2/oauth/applications)
2. Create an application and generate a Developer Token
3. Save it:

```bash
cp producthunt-pipeline/.env.example producthunt-pipeline/.env
# Edit .env and paste your token
```

## How it works

Each pipeline has its own `catchmeup.py` that:
- Fetches content from its source
- Filters for new items since `last_run.txt` (except Product Hunt which shows today's top 10)
- Prints a clean terminal digest

Claude Code reads the output and summarizes everything grouped by topic — connecting voices across sources. For example, if @sama tweets about GPT-5, a YouTube channel reviews it, and it's trending on GitHub, they all appear under one topic heading.

## Project structure

```
hyperinformed/
├── CLAUDE.md                           # Claude Code context
├── catchmeup.md                        # Slash command template
├── requirements.txt
├── youtube-pipeline/
│   ├── catchmeup.py                    # YouTube RSS fetcher
│   └── subscriptions.csv.example
├── twitter-pipeline/
│   ├── catchmeup.py                    # X/Twitter via twikit
│   └── accounts.txt.example
├── github-pipeline/
│   └── catchmeup.py                    # Trending + starred repos
└── producthunt-pipeline/
    ├── catchmeup.py                    # Product Hunt GraphQL API
    └── .env.example
```

## Adding more pipelines

Each pipeline is independent — just create a new folder with a `catchmeup.py` that prints to stdout, add it to the slash command mapping, and you're done.

## License

MIT
