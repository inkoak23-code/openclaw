#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "tweepy>=4.14.0",
#     "httpx>=0.27.0",
#     "openai>=1.0.0",
# ]
# ///
"""
Web3 Founder Twitter Autoposter — fully autonomous tweet generation & posting.

Workflow:
    1. Fetch current CT trends via Twitter search
    2. Generate tweet content using GPT (Web3 founder persona)
    3. Post tweet(s) to Twitter
    4. Send Telegram notification

Usage:
    uv run web3_autoposter.py                          # Auto: fetch trends + generate + post + notify
    uv run web3_autoposter.py --dry-run                # Preview without posting
    uv run web3_autoposter.py --count 2                # Generate 2 tweets
    uv run web3_autoposter.py --type "hot take"        # Force a specific tweet type
    uv run web3_autoposter.py --status                 # Show daily tweet count

Environment variables (required):
    TWITTER_API_KEY, TWITTER_API_SECRET, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_TOKEN_SECRET
    OPENAI_API_KEY
    TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
"""

import argparse
import json
import os
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

# Rate limit: Twitter Free tier = 17 tweets/24h
DAILY_TWEET_LIMIT = 12  # Conservative limit, leave room for manual tweets
STATE_FILE = Path(os.environ.get("OPENCLAW_STATE_DIR", Path.home() / ".openclaw")) / "autoposter_state.json"

TWEET_TYPES = ["hot take", "builder insight", "alpha thread", "engagement"]
TWEET_TYPE_WEIGHTS = [0.4, 0.3, 0.2, 0.1]  # Match the content ratio spec

SEARCH_TOPICS = [
    "crypto meme coin pump.fun",
    "Web3 DeFi protocol launch",
    "Bitcoin ETH market",
    "CT crypto twitter alpha",
    "Web3 founder builder",
]

SYSTEM_PROMPT = """You are a Web3 founder running a Twitter/X account. You write sharp, opinionated, slightly irreverent but insightful tweets that attract English-speaking crypto-native users.

Your voice:
- You've been through multiple crypto cycles — not a newbie, not a maximalist
- Builder/founder perspective, not a pure trader
- Casual tone, lowercase or mixed case, no corporate language
- Short punchy sentences with line breaks for readability
- Emojis: max 1-2 per tweet, sparingly
- Slang is fine: "degen", "aping", "ser", "ngmi/wagmi", "CT", "trench" — but don't overdo it
- Never shill directly. Value > hype
- NO hashtags. NO generic motivational content. NO "gm" without substance.

CRITICAL RULES:
- Each tweet MUST be under 280 characters
- Sound human and authentic — NEVER sound like AI or a bot
- Vary sentence structure — no repetitive patterns
- Be nuanced — not overly bullish or bearish
- Write something only YOU would write, not a generic take anyone could post"""

TWEET_TYPE_PROMPTS = {
    "hot take": "Write a SHORT hot take tweet (1-2 sentences) reacting to current CT trends. Punchy, opinionated, slightly contrarian. Under 280 chars.",
    "builder insight": "Write a tweet sharing a founder/builder lesson — about shipping, fundraising, hiring, or surviving in crypto. Personal, slightly vulnerable or self-deprecating. Under 280 chars.",
    "alpha thread": "Write a single insightful observation tweet about an emerging trend, narrative shift, or on-chain signal you've noticed. Analytical but accessible. Under 280 chars.",
    "engagement": "Write an engagement tweet — an unpopular opinion, a provocative question, or a 'which side are you on' style post that sparks replies. Under 280 chars.",
}


def load_state() -> dict:
    """Load autoposter state (daily tweet count, last run, etc.)."""
    if STATE_FILE.exists():
        try:
            data = json.loads(STATE_FILE.read_text())
            # Reset counter if it's a new day
            last_date = data.get("date", "")
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            if last_date != today:
                data["date"] = today
                data["tweets_today"] = 0
                data["types_today"] = []
            return data
        except (json.JSONDecodeError, KeyError):
            pass
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return {"date": today, "tweets_today": 0, "types_today": [], "history": []}


def save_state(state: dict):
    """Persist autoposter state."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    # Keep history manageable — last 50 entries
    if "history" in state and len(state["history"]) > 50:
        state["history"] = state["history"][-50:]
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False))


def fetch_trends() -> str:
    """Fetch current CT trends via Twitter search."""
    try:
        import tweepy
    except ImportError:
        return "Could not fetch trends — tweepy not installed."

    bearer = os.environ.get("TWITTER_BEARER_TOKEN")
    api_key = os.environ.get("TWITTER_API_KEY")
    api_secret = os.environ.get("TWITTER_API_SECRET")
    access_token = os.environ.get("TWITTER_ACCESS_TOKEN")
    access_token_secret = os.environ.get("TWITTER_ACCESS_TOKEN_SECRET")

    if bearer:
        client = tweepy.Client(bearer_token=bearer)
    elif api_key and api_secret and access_token and access_token_secret:
        client = tweepy.Client(
            consumer_key=api_key, consumer_secret=api_secret,
            access_token=access_token, access_token_secret=access_token_secret,
        )
    else:
        return "No Twitter credentials available for trend fetching."

    # Pick 2 random search topics to keep it varied
    topics = random.sample(SEARCH_TOPICS, min(2, len(SEARCH_TOPICS)))
    combined_query = " OR ".join(topics[0].split()[:3]) + " -is:retweet lang:en"

    trends_text = []
    try:
        resp = client.search_recent_tweets(
            query=combined_query,
            max_results=15,
            tweet_fields=["created_at", "public_metrics", "author_id"],
            user_fields=["username"],
            expansions=["author_id"],
        )
        if resp and resp.data:
            users_map = {}
            if resp.includes and "users" in resp.includes:
                for u in resp.includes["users"]:
                    users_map[u.id] = u

            for t in resp.data[:10]:
                author = ""
                if t.author_id and t.author_id in users_map:
                    author = f"@{users_map[t.author_id].username}"
                likes = t.public_metrics.get("like_count", 0) if t.public_metrics else 0
                trends_text.append(f"- {author} ({likes} likes): {t.text[:200]}")
    except Exception as e:
        trends_text.append(f"(Search failed: {e})")

    if not trends_text:
        trends_text.append("(No trending tweets found — generate based on general CT knowledge)")

    return "\n".join(trends_text)


def generate_tweet(trends: str, tweet_type: str, recent_tweets: list[str]) -> str:
    """Generate a tweet using OpenAI GPT."""
    from openai import OpenAI

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("Error: OPENAI_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    client = OpenAI(api_key=api_key)

    recent_context = ""
    if recent_tweets:
        recent_context = "\n\nYour recent tweets (DO NOT repeat similar themes or structures):\n"
        recent_context += "\n".join(f"- {t}" for t in recent_tweets[-5:])

    user_prompt = f"""{TWEET_TYPE_PROMPTS[tweet_type]}

Current CT trends and discussions:
{trends}
{recent_context}

Reply with ONLY the tweet text. No quotes, no labels, no explanation. Just the raw tweet."""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.9,
            max_tokens=150,
        )
        tweet = response.choices[0].message.content.strip()
        # Clean up: remove surrounding quotes if GPT added them
        if tweet.startswith('"') and tweet.endswith('"'):
            tweet = tweet[1:-1]
        # Enforce 280 char limit
        if len(tweet) > 280:
            tweet = tweet[:277] + "..."
        return tweet
    except Exception as e:
        print(f"Error generating tweet: {e}", file=sys.stderr)
        sys.exit(1)


def post_tweet_to_twitter(text: str) -> tuple[str, str]:
    """Post tweet and return (tweet_id, tweet_url)."""
    import tweepy

    api_key = os.environ.get("TWITTER_API_KEY")
    api_secret = os.environ.get("TWITTER_API_SECRET")
    access_token = os.environ.get("TWITTER_ACCESS_TOKEN")
    access_token_secret = os.environ.get("TWITTER_ACCESS_TOKEN_SECRET")

    client = tweepy.Client(
        consumer_key=api_key, consumer_secret=api_secret,
        access_token=access_token, access_token_secret=access_token_secret,
    )

    try:
        response = client.create_tweet(text=text)
    except tweepy.Forbidden as e:
        print(f"Error: 403 Forbidden — {e}", file=sys.stderr)
        sys.exit(1)

    tweet_id = response.data["id"]
    tweet_url = f"https://x.com/i/status/{tweet_id}"
    return tweet_id, tweet_url


def send_telegram_notification(tweet_text: str, tweet_url: str, tweet_type: str):
    """Send formatted Telegram notification."""
    import httpx

    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not bot_token or not chat_id:
        print("Warning: Telegram credentials not set, skipping notification.", file=sys.stderr)
        return

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    message = (
        f"\U0001f4e2 New Tweet Posted\n"
        f"\U0001f550 Time: {timestamp}\n"
        f"\U0001f4dd Content: {tweet_text}\n"
        f"\U0001f517 Link: {tweet_url}\n"
        f"\U0001f4ca Type: {tweet_type}"
    )

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    try:
        resp = httpx.post(url, json={"chat_id": chat_id, "text": message}, timeout=30)
        if resp.status_code == 200:
            print("Telegram notification sent.")
        else:
            print(f"Warning: Telegram API {resp.status_code}: {resp.text}", file=sys.stderr)
    except Exception as e:
        print(f"Warning: Telegram notification failed: {e}", file=sys.stderr)


def pick_tweet_type(state: dict, forced_type: str | None = None) -> str:
    """Pick a tweet type based on weights and what's already been posted today."""
    if forced_type and forced_type in TWEET_TYPES:
        return forced_type

    # Avoid repeating same type consecutively
    types_today = state.get("types_today", [])
    last_type = types_today[-1] if types_today else None

    available = [(t, w) for t, w in zip(TWEET_TYPES, TWEET_TYPE_WEIGHTS) if t != last_type]
    if not available:
        available = list(zip(TWEET_TYPES, TWEET_TYPE_WEIGHTS))

    types, weights = zip(*available)
    return random.choices(types, weights=weights, k=1)[0]


def main():
    parser = argparse.ArgumentParser(description="Web3 Founder Twitter Autoposter")
    parser.add_argument("--dry-run", action="store_true", help="Preview without posting")
    parser.add_argument("--count", type=int, default=1, help="Number of tweets to generate (default: 1)")
    parser.add_argument("--type", dest="tweet_type", default=None,
                        choices=TWEET_TYPES, help="Force a specific tweet type")
    parser.add_argument("--status", action="store_true", help="Show daily posting status")
    parser.add_argument("--no-trends", action="store_true", help="Skip trend fetching (faster, less contextual)")

    args = parser.parse_args()
    state = load_state()

    if args.status:
        print(f"Date: {state['date']}")
        print(f"Tweets today: {state['tweets_today']}/{DAILY_TWEET_LIMIT}")
        print(f"Types today: {', '.join(state.get('types_today', [])) or 'none'}")
        recent = state.get("history", [])[-5:]
        if recent:
            print("\nRecent tweets:")
            for h in recent:
                print(f"  [{h.get('type', '?')}] {h.get('text', '')[:80]}...")
        return

    # Check rate limit
    if state["tweets_today"] >= DAILY_TWEET_LIMIT:
        print(f"Daily limit reached ({DAILY_TWEET_LIMIT} tweets). Skipping.", file=sys.stderr)
        # Still notify via Telegram
        send_telegram_notification(
            f"[SKIPPED] Daily tweet limit reached ({state['tweets_today']}/{DAILY_TWEET_LIMIT})",
            "", "system"
        )
        return

    # Fetch trends
    print("Fetching CT trends...")
    if args.no_trends:
        trends = "(Generate based on your general knowledge of current crypto/Web3 meta)"
    else:
        trends = fetch_trends()
    print(f"Trends context: {len(trends)} chars\n")

    # Get recent tweet history for dedup
    recent_tweets = [h.get("text", "") for h in state.get("history", [])[-10:]]

    for i in range(args.count):
        remaining = DAILY_TWEET_LIMIT - state["tweets_today"]
        if remaining <= 0:
            print(f"Daily limit reached after {i} tweets. Stopping.")
            break

        tweet_type = pick_tweet_type(state, args.tweet_type)
        print(f"[{i+1}/{args.count}] Generating '{tweet_type}'...")

        tweet_text = generate_tweet(trends, tweet_type, recent_tweets)
        print(f"Generated ({len(tweet_text)} chars): {tweet_text}\n")

        if args.dry_run:
            print(f"[DRY RUN] Would post: {tweet_text}")
            print(f"[DRY RUN] Type: {tweet_type}")
            continue

        # Post
        tweet_id, tweet_url = post_tweet_to_twitter(tweet_text)
        print(f"Posted: {tweet_url}")

        # Notify
        send_telegram_notification(tweet_text, tweet_url, tweet_type)

        # Update state
        state["tweets_today"] += 1
        state["types_today"].append(tweet_type)
        state.setdefault("history", []).append({
            "text": tweet_text,
            "type": tweet_type,
            "url": tweet_url,
            "id": tweet_id,
            "time": datetime.now(timezone.utc).isoformat(),
        })
        recent_tweets.append(tweet_text)
        save_state(state)

    if not args.dry_run:
        print(f"\nDone. Tweets today: {state['tweets_today']}/{DAILY_TWEET_LIMIT}")


if __name__ == "__main__":
    main()
