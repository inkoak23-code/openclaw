#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "tweepy>=4.14.0",
# ]
# ///
"""
Generate a daily digest from Twitter/X: fetch timeline, mentions, and keyword
searches, then output a structured summary for the agent to process.

Usage:
    uv run twitter_digest.py --sources timeline,mentions --search "AI,LLM,OpenClaw"
    uv run twitter_digest.py --sources timeline --search "机器学习" --count 30
    uv run twitter_digest.py --sources mentions --format json

Environment variables (required):
    TWITTER_BEARER_TOKEN or all four OAuth tokens.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone


def get_client():
    """Create a Tweepy client."""
    try:
        import tweepy
    except ImportError:
        print("Error: tweepy not installed.", file=sys.stderr)
        sys.exit(1)

    bearer = os.environ.get("TWITTER_BEARER_TOKEN")
    api_key = os.environ.get("TWITTER_API_KEY")
    api_secret = os.environ.get("TWITTER_API_SECRET")
    access_token = os.environ.get("TWITTER_ACCESS_TOKEN")
    access_token_secret = os.environ.get("TWITTER_ACCESS_TOKEN_SECRET")

    if bearer:
        return tweepy.Client(bearer_token=bearer)
    elif api_key and api_secret and access_token and access_token_secret:
        return tweepy.Client(
            consumer_key=api_key,
            consumer_secret=api_secret,
            access_token=access_token,
            access_token_secret=access_token_secret,
        )
    else:
        print("Error: Set TWITTER_BEARER_TOKEN or OAuth env vars.", file=sys.stderr)
        sys.exit(1)


TWEET_FIELDS = ["created_at", "public_metrics", "author_id", "lang"]
USER_FIELDS = ["name", "username"]
EXPANSIONS = ["author_id"]


def extract_tweets(response) -> list[dict]:
    """Extract tweets from a Tweepy response into dicts."""
    if not response or not response.data:
        return []

    users_map = {}
    if response.includes and "users" in response.includes:
        for u in response.includes["users"]:
            users_map[u.id] = u

    results = []
    for t in response.data:
        entry = {
            "id": t.id,
            "text": t.text,
            "created_at": str(t.created_at) if t.created_at else None,
        }
        if t.public_metrics:
            entry["likes"] = t.public_metrics.get("like_count", 0)
            entry["retweets"] = t.public_metrics.get("retweet_count", 0)
            entry["replies"] = t.public_metrics.get("reply_count", 0)
        if t.author_id and t.author_id in users_map:
            u = users_map[t.author_id]
            entry["author"] = f"@{u.username}"
        results.append(entry)
    return results


def fetch_timeline(client, count: int) -> list[dict]:
    """Fetch home timeline."""
    try:
        resp = client.get_home_timeline(
            max_results=min(count, 100),
            tweet_fields=TWEET_FIELDS,
            user_fields=USER_FIELDS,
            expansions=EXPANSIONS,
        )
        return extract_tweets(resp)
    except Exception as e:
        print(f"Warning: Failed to fetch timeline: {e}", file=sys.stderr)
        return []


def fetch_mentions(client, count: int) -> list[dict]:
    """Fetch mentions."""
    try:
        me = client.get_me()
        if not me or not me.data:
            return []
        resp = client.get_users_mentions(
            me.data.id,
            max_results=min(count, 100),
            tweet_fields=TWEET_FIELDS,
            user_fields=USER_FIELDS,
            expansions=EXPANSIONS,
        )
        return extract_tweets(resp)
    except Exception as e:
        print(f"Warning: Failed to fetch mentions: {e}", file=sys.stderr)
        return []


def fetch_search(client, query: str, count: int) -> list[dict]:
    """Search recent tweets."""
    try:
        resp = client.search_recent_tweets(
            query=query,
            max_results=min(count, 100),
            tweet_fields=TWEET_FIELDS,
            user_fields=USER_FIELDS,
            expansions=EXPANSIONS,
        )
        return extract_tweets(resp)
    except Exception as e:
        print(f"Warning: Search failed for '{query}': {e}", file=sys.stderr)
        return []


def main():
    parser = argparse.ArgumentParser(description="Generate Twitter/X daily digest")
    parser.add_argument("--sources", default="timeline,mentions",
                        help="Comma-separated: timeline,mentions (default: timeline,mentions)")
    parser.add_argument("--search", "-s", default="",
                        help="Comma-separated search keywords (e.g. 'AI,LLM,OpenClaw')")
    parser.add_argument("--count", "-n", type=int, default=20,
                        help="Max tweets per source (default: 20)")
    parser.add_argument("--format", choices=["json", "text"], default="text",
                        help="Output format (default: text)")

    args = parser.parse_args()
    client = get_client()
    sources = [s.strip() for s in args.sources.split(",") if s.strip()]
    search_terms = [s.strip() for s in args.search.split(",") if s.strip()]

    digest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sections": [],
    }

    if "timeline" in sources:
        tweets = fetch_timeline(client, args.count)
        digest["sections"].append({"source": "timeline", "count": len(tweets), "tweets": tweets})

    if "mentions" in sources:
        tweets = fetch_mentions(client, args.count)
        digest["sections"].append({"source": "mentions", "count": len(tweets), "tweets": tweets})

    if search_terms:
        # Combine terms into one OR query to save API rate limits
        combined_query = " OR ".join(search_terms) + " -is:retweet"
        tweets = fetch_search(client, combined_query, args.count)
        label = ",".join(search_terms)
        digest["sections"].append({"source": f"search:{label}", "count": len(tweets), "tweets": tweets})

    if args.format == "json":
        print(json.dumps(digest, indent=2, ensure_ascii=False))
    else:
        print(f"=== Twitter/X Digest ({digest['generated_at']}) ===\n")
        for section in digest["sections"]:
            print(f"## {section['source']} ({section['count']} tweets)\n")
            for t in section["tweets"]:
                author = t.get("author", "unknown")
                likes = t.get("likes", 0)
                rts = t.get("retweets", 0)
                print(f"  {author} [{likes} likes, {rts} RTs]")
                print(f"  {t['text'][:280]}")
                print()
            print("---\n")


if __name__ == "__main__":
    main()
