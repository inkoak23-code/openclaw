---
name: twitter-x
description: "Manage a Twitter/X account: read timelines, search tweets, post tweets/threads, and run automated daily digests. Use when the user wants to read, summarize, or post to Twitter/X, or set up automated content pipelines (daily news summaries, curated threads, scheduled posting)."
metadata:
  {
    "openclaw":
      {
        "emoji": "𝕏",
        "requires":
          {
            "bins": ["uv"],
            "env":
              [
                "TWITTER_API_KEY",
                "TWITTER_API_SECRET",
                "TWITTER_ACCESS_TOKEN",
                "TWITTER_ACCESS_TOKEN_SECRET",
              ],
          },
        "primaryEnv": "TWITTER_API_KEY",
        "install":
          [
            {
              "id": "uv-brew",
              "kind": "brew",
              "formula": "uv",
              "bins": ["uv"],
              "label": "Install uv (brew)",
            },
            {
              "id": "uv-pip",
              "kind": "node",
              "package": "uv",
              "bins": ["uv"],
              "label": "Install uv (pipx/pip)",
            },
          ],
      },
  }
---

# Twitter/X

Read, search, and post to Twitter/X. Automate daily digests with cron jobs.

## References

- `references/setup.md` — API credential setup, rate limits, and permissions
- `references/daily-digest-cron.md` — Cron job configuration for automated daily digest workflows

## Read tweets

```bash
# Home timeline
uv run {baseDir}/scripts/twitter_read.py timeline --count 20

# Your mentions
uv run {baseDir}/scripts/twitter_read.py mentions --count 10

# Search recent tweets
uv run {baseDir}/scripts/twitter_read.py search --query "AI LLM" --count 20

# Specific user's tweets
uv run {baseDir}/scripts/twitter_read.py user --username username --count 10

# Single tweet by ID
uv run {baseDir}/scripts/twitter_read.py tweet --id 1234567890
```

## Post tweets

```bash
# Single tweet
uv run {baseDir}/scripts/twitter_post.py --text "Hello from OpenClaw!"

# Tweet with image
uv run {baseDir}/scripts/twitter_post.py --text "Check this out" --media /path/to/image.png

# Thread (multiple tweets chained as replies)
uv run {baseDir}/scripts/twitter_post.py --thread "First tweet" "Second tweet" "Third tweet"

# Reply to existing tweet
uv run {baseDir}/scripts/twitter_post.py --text "Great point!" --reply-to 1234567890

# Dry run (preview without posting)
uv run {baseDir}/scripts/twitter_post.py --text "Test" --dry-run
```

## Daily digest (read + summarize + post)

```bash
# Fetch digest from timeline + keyword searches
uv run {baseDir}/scripts/twitter_digest.py --sources timeline,mentions --search "AI,LLM,tech" --count 30

# JSON output for programmatic use
uv run {baseDir}/scripts/twitter_digest.py --sources timeline --search "AI" --format json
```

## Daily digest automation workflow

1. Fetch digest: `uv run {baseDir}/scripts/twitter_digest.py --sources timeline,mentions --search "<user topics>" --count 30`
2. Analyze the output, identify top trending topics and key insights
3. Draft a tweet thread (3-5 tweets) summarizing the highlights
4. Always do a dry run first: `uv run {baseDir}/scripts/twitter_post.py --thread "..." --dry-run`
5. Post the thread: `uv run {baseDir}/scripts/twitter_post.py --thread "Tweet 1" "Tweet 2" "Tweet 3"`

For scheduled automation, see `references/daily-digest-cron.md`.

## Telegram notification

Send digest results or any message to Telegram:

```bash
# Send a text message
uv run {baseDir}/scripts/telegram_notify.py --text "Your digest summary here"

# Pipe content from another command
uv run {baseDir}/scripts/twitter_digest.py --sources timeline --search "AI" | uv run {baseDir}/scripts/telegram_notify.py --stdin
```

Requires `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` in env config.

## Important notes

- Twitter Free tier: 17 tweets/24h per user. Do not exceed this.
- Tweet max length: 280 characters. Split longer content into threads.
- Always preview with `--dry-run` before posting when the user hasn't reviewed content.
- Search queries support Twitter operators: `"exact phrase"`, `from:user`, `lang:zh`, `-filter:retweets`.
