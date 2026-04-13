# Hyperinformed

A multi-source intelligence feed that aggregates content from YouTube, X/Twitter, GitHub, Product Hunt, Every.to, Hacker News blogs, Kickstarter, and Indie Hackers into a single catch-me-up report with audio narration. Built to work with [Claude Code](https://claude.ai/claude-code) as a `/catchmeup` slash command.

## What it does

Say `/catchmeup` and get a comprehensive HTML report of everything that happened since you last checked — across all your feeds. Each report includes:

- **Written report** — topic-grouped HTML with tap-to-highlight items, clickable links, and a pipeline status dashboard
- **Audio narration** — TTS-generated MP3 using macOS Ava (Premium) voice, embedded in the HTML
- **Mobile access** — deployed to Netlify so you can read and listen from your phone

```
/catchmeup              # all 8 sources
/catchmeup youtube      # just YouTube
/catchmeup x            # just Twitter
/catchmeup gh           # just GitHub
/catchmeup ph           # just Product Hunt
/catchmeup every        # just Every.to
/catchmeup hn           # just Hacker News blogs
/catchmeup ks           # just Kickstarter
/catchmeup ih           # just Indie Hackers
/catchmeup youtube x    # mix and match
```

## Pipelines

| Pipeline | Source | Auth | Frequency | What it fetches |
|---|---|---|---|---|
| YouTube | YouTube Data API v3 | API key | Daily | Videos from subscribed channels |
| Twitter/X | X timeline via twikit | Cookies | Daily | Following + For You + Notifications |
| GitHub | Trending + starred repos | `gh` CLI | Daily | Trending repos + updates to starred repos with new releases |
| Product Hunt | GraphQL API | API key | Weekly | Top products by votes with weekly leaderboard rank |
| Every.to | Private RSS feed | Feed URL | Daily | New articles |
| Hacker News | 92 blog RSS feeds + HN API | None | Daily | Blog posts + HN front page top 30 stories |
| Kickstarter | Discover API | None | Weekly | Technology projects, >100% funded, sorted by popularity |
| Indie Hackers | Firebase API | None | Daily | High-signal forum posts (50+ views AND 2+ replies) |

## Setup

### Prerequisites

- Python 3.10+
- [Claude Code](https://claude.ai/claude-code)
- [GitHub CLI](https://cli.github.com/) (`brew install gh`)
- [Netlify CLI](https://docs.netlify.com/cli/get-started/) (`npm install -g netlify-cli`)
- macOS with Ava (Premium) voice installed (System Settings > Accessibility > Spoken Content > Manage Voices)

### Install dependencies

```bash
git clone https://github.com/jd0924/hyperinformed.git
cd hyperinformed
pip install -r requirements.txt
```

### Configure each pipeline

#### YouTube

Requires a YouTube Data API v3 key (free, 10,000 units/day):

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Create a project and enable the YouTube Data API v3
3. Create an API key under Credentials
4. Save it:

```bash
# Create youtube-pipeline/.env with:
YOUTUBE_API_KEY=your_key_here
```

Then add your subscriptions via [Google Takeout](https://takeout.google.com/) — export YouTube data and copy the `subscriptions.csv`:

```bash
cp /path/to/Takeout/YouTube/subscriptions/subscriptions.csv youtube-pipeline/subscriptions.csv
```

#### Twitter / X

1. Install the [Cookie-Editor](https://cookie-editor.com/) browser extension
2. Go to x.com and log in
3. Click Cookie-Editor > Export (JSON)
4. Save as `twitter-pipeline/cookies.json`

Fetches your Following timeline, For You timeline, and Notifications. Cookies expire periodically — re-export when the script stops working.

#### GitHub

```bash
gh auth login
```

Fetches trending repos and tracks updates to your starred repos automatically.

#### Product Hunt

1. Go to [producthunt.com/v2/oauth/applications](https://www.producthunt.com/v2/oauth/applications)
2. Create an application and generate a Developer Token
3. Save it:

```bash
# Create producthunt-pipeline/.env with:
PRODUCTHUNT_API_KEY=your_token_here
```

Runs weekly — fetches the top products from the past 7 days sorted by votes.

#### Every.to

1. Log in to [every.to](https://every.to) and find your private RSS feed URL
2. Save it:

```bash
# Create every-pipeline/.env with:
EVERY_FEED_URL=https://every.to/feeds/YOUR_TOKEN.xml
```

#### Hacker News Blogs

No configuration needed — ships with 92 curated blog RSS feeds plus the HN front page top 30.

#### Kickstarter

No configuration needed — fetches Technology category projects that are >100% funded. Runs weekly.

#### Indie Hackers

No configuration needed — fetches high-signal forum posts (50+ views AND 2+ replies) from the Indie Hackers Firebase API.

### Netlify deploy

```bash
netlify login
```

Reports are deployed to Netlify with audio embedded. The deploy script prints a URL you can open on any device.

## How it works

1. **Fetch** — All 8 pipelines run in parallel, each writing structured `output.json`
2. **Generate** — LLM decides topic groupings and highlights, writes a `plan.json`, then `generate-report.py` renders the HTML from the plan
3. **Cross-check** — `crosscheck.py` verifies every item from JSON appears in the HTML
4. **Audio** — `tts-generate-say.py` generates narration using macOS Ava voice
5. **Open** — Report opens in the browser with an embedded audio player
6. **Deploy** — `deploy.py` embeds the MP3 into the HTML and pushes to Netlify

Each pipeline writes `output.json` with a standard schema and tracks its last run in `last_run.txt`. If a pipeline fails, it writes `status: "error"` to its JSON so other pipelines aren't affected.

## Project structure

```
hyperinformed/
├── CLAUDE.md                           # Claude Code project context
├── README.md
├── requirements.txt
├── generate-report.py                  # Renders HTML from plan.json + output.json
├── crosscheck.py                       # Verifies HTML matches JSON data
├── deploy.py                           # Embeds audio + deploys to Netlify
├── tts-generate-say.py                 # Generates audio narration
├── templates/
│   └── report-template.html            # HTML template (dark theme, audio player)
├── youtube-pipeline/
│   └── catchmeup.py                    # YouTube Data API v3
├── twitter-pipeline/
│   └── catchmeup.py                    # X/Twitter via twikit
├── github-pipeline/
│   └── catchmeup.py                    # Trending + starred repos
├── producthunt-pipeline/
│   └── catchmeup.py                    # Product Hunt GraphQL API (weekly)
├── every-pipeline/
│   └── catchmeup.py                    # Every.to private RSS feed
├── hackernews-pipeline/
│   ├── catchmeup.py                    # HN blogs + front page
│   └── feeds.opml                      # 92 curated blog feeds
├── kickstarter-pipeline/
│   └── catchmeup.py                    # Kickstarter Technology (weekly)
└── indiehackers-pipeline/
    └── catchmeup.py                    # Indie Hackers Firebase API
```

## Adding more pipelines

Each pipeline is independent — create a new folder with a `catchmeup.py` that writes `output.json` following the standard schema, add it to `crosscheck.py`, `generate-report.py`, and the report template, and you're done.

## License

MIT
