Fetch and summarize recent content from intelligence feeds.

## Arguments: $ARGUMENTS

If arguments are provided, only run the specified platform(s). If no arguments, run ALL platforms.

## Platform mapping

| Argument | Script |
|----------|--------|
| youtube | `python3 /Users/reggin003/hyperinformed/youtube-pipeline/catchmeup.py` |
| twitter, x | `python3 /Users/reggin003/hyperinformed/twitter-pipeline/catchmeup.py` |
| github, gh | `python3 /Users/reggin003/hyperinformed/github-pipeline/catchmeup.py` |
| producthunt, ph | `python3 /Users/reggin003/hyperinformed/producthunt-pipeline/catchmeup.py` |
| every | `python3 /Users/reggin003/hyperinformed/every-pipeline/catchmeup.py` |
| hackernews, hn | `python3 /Users/reggin003/hyperinformed/hackernews-pipeline/catchmeup.py` |
| kickstarter, ks | `python3 /Users/reggin003/hyperinformed/kickstarter-pipeline/catchmeup.py` |

Multiple platforms can be specified: `/catchmeup youtube twitter`

## Examples

- `/catchmeup` — run all 7 platforms
- `/catchmeup youtube` — YouTube only
- `/catchmeup x` — Twitter/X only
- `/catchmeup gh` — GitHub only
- `/catchmeup ph` — Product Hunt only
- `/catchmeup every` — Every.to only
- `/catchmeup hn` — Hacker News blogs only
- `/catchmeup ks` — Kickstarter only
- `/catchmeup youtube x` — YouTube and Twitter

## After fetching

1. Run the matching script(s) — all pipelines write `output.json` alongside stdout
2. Read each pipeline's `output.json` for structured item data
3. Use LLM judgment to decide topic groupings and Top 5 highlights
4. Fill in `templates/report-template.html` content blocks to produce `catchmeup-<start>-to-<end>.html` — do NOT rewrite CSS/JS
5. One section per platform, then group by topics within each platform
6. Include everything except pure ads
7. If 0 new items from a source, note they're caught up and when last run was
8. **Cross-check**: Run `python3 crosscheck.py <report.html>` — verifies per-platform counts, URLs, and authors. Fix any failures before showing the report.
9. **Generate audio**: Run `python3 tts-generate-say.py <narration.txt>` — produces MP3 using macOS Ava (Premium) voice.
10. **Open**: Open the HTML in the browser. The embedded audio player loads the MP3 automatically.
