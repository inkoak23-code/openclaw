# Daily Digest Cron Job Setup

Automate daily reading, summarization, and posting with OpenClaw's cron system.

## Overview

The workflow:

1. **Cron job fires** at a scheduled time (e.g. every morning 9:00 AM)
2. **Agent reads** Twitter timeline + keyword searches via `twitter_digest.py`
3. **Agent summarizes** the digest into key takeaways
4. **Agent posts** a summary thread to your account via `twitter_post.py`
5. **Agent announces** the result to your preferred channel (optional)

## Add the Cron Job

```bash
openclaw cron add \
  --name "twitter-daily-digest" \
  --schedule "cron" \
  --expression "0 9 * * *" \
  --timezone "Asia/Shanghai" \
  --mode isolated \
  --delivery announce \
  --message "Run the twitter-x daily digest workflow:
1. Use twitter_digest.py to fetch timeline and search for topics: AI, LLM, tech news
2. Summarize the top 5 most important items in Chinese
3. Draft a tweet thread (3-5 tweets) highlighting key insights
4. Post the thread using twitter_post.py
5. Report what was posted"
```

## Configuration Options

### Schedule Variants

```bash
# Every morning at 8:00 AM Beijing time
--expression "0 8 * * *" --timezone "Asia/Shanghai"

# Twice daily: 9 AM and 6 PM
--expression "0 9,18 * * *" --timezone "Asia/Shanghai"

# Weekdays only at 9 AM
--expression "0 9 * * 1-5" --timezone "Asia/Shanghai"

# Every 6 hours
--expression "0 */6 * * *" --timezone "UTC"
```

### Delivery Modes

```bash
# Post summary to your chat channel (WhatsApp/Telegram/etc)
--delivery announce

# POST result to a webhook URL
--delivery webhook --webhook-url "https://your.webhook/endpoint"

# Internal only (no notification)
--delivery none
```

### Custom Search Topics

Adjust the `--message` prompt to focus on your interests:

```
"Fetch twitter digest with searches: 区块链, Web3, DeFi, crypto.
Summarize in Chinese. Post a thread of 3 tweets with market insights."
```

```
"Fetch twitter digest for: Python, Rust, TypeScript, open source.
Pick the 3 most interesting developer tools/libraries mentioned.
Post a curated thread."
```

## Manage Cron Jobs

```bash
# List all cron jobs
openclaw cron list

# View a specific job
openclaw cron list --name twitter-daily-digest

# Run manually (test without waiting for schedule)
openclaw cron run --name twitter-daily-digest

# Edit the job
openclaw cron edit --name twitter-daily-digest --expression "0 10 * * *"

# Delete the job
openclaw cron edit --name twitter-daily-digest --delete
```

## Example Agent Prompt for Custom Digest

If you want to run the digest manually via the agent:

```bash
openclaw agent --message "
Use the twitter-x skill:
1. Run twitter_digest.py --sources timeline,mentions --search 'AI,机器学习,大模型' --count 30
2. Analyze the results and identify the top 5 trending topics
3. Write a summary in Chinese (200-300 chars per tweet)
4. Post as a thread using twitter_post.py
" --thinking high
```
