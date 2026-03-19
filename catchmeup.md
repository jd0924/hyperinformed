Fetch and summarize recent content from intelligence feeds.

Copy this file to ~/.claude/commands/catchmeup.md to use as a slash command.
Then replace HYPERINFORMED_PATH below with the absolute path to your hyperinformed folder.

## Arguments: $ARGUMENTS

If arguments are provided, only run the specified platform(s). If no arguments, run ALL platforms.

## Platform mapping

| Argument | Script |
|----------|--------|
| youtube | `python3 HYPERINFORMED_PATH/youtube-pipeline/catchmeup.py` |
| twitter, x | `python3 HYPERINFORMED_PATH/twitter-pipeline/catchmeup.py` |
| github, gh | `python3 HYPERINFORMED_PATH/github-pipeline/catchmeup.py` |
| producthunt, ph | `python3 HYPERINFORMED_PATH/producthunt-pipeline/catchmeup.py` |
| every | `python3 HYPERINFORMED_PATH/every-pipeline/catchmeup.py` |
| hackernews, hn | `python3 HYPERINFORMED_PATH/hackernews-pipeline/catchmeup.py` |

Multiple platforms can be specified: `/catchmeup youtube twitter`

## Examples

- `/catchmeup` — run all 6 platforms
- `/catchmeup youtube` — YouTube only
- `/catchmeup x` — Twitter/X only
- `/catchmeup gh` — GitHub only
- `/catchmeup ph` — Product Hunt only
- `/catchmeup every` — Every.to only
- `/catchmeup hn` — Hacker News blogs only
- `/catchmeup youtube x` — YouTube and Twitter

## After fetching

1. Run the matching script(s)
2. Summarize all content grouped by TOPIC, not by source or account. Connect different voices/repos/products discussing the same thing.
3. At the end, highlight the 3-5 most interesting/notable items across all fetched sources
4. If 0 new items from a source, tell the user they're caught up on that source and when the last run was
