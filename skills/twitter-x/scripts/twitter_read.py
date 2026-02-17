#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "tweepy>=4.14.0",
# ]
# ///
"""
Read tweets, timelines, and search Twitter/X using the v2 API.

Usage:
    uv run twitter_read.py timeline --count 20
    uv run twitter_read.py mentions --count 10
    uv run twitter_read.py search --query "AI news" --count 20
    uv run twitter_read.py user --username elonmusk --count 10
    uv run twitter_read.py tweet --id 1234567890

Environment variables (required):
    TWITTER_BEARER_TOKEN       - Bearer Token (for read endpoints)

Or use OAuth tokens:
    TWITTER_API_KEY, TWITTER_API_SECRET,
    TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_TOKEN_SECRET
"""

import argparse
import json
import os
import sys


def get_client():
    """Create a Tweepy client for reading."""
    try:
        import tweepy
    except ImportError:
        print("Error: tweepy not installed. Run: uv run this_script.py", file=sys.stderr)
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
        print("Error: Set TWITTER_BEARER_TOKEN or all four OAuth env vars.", file=sys.stderr)
        sys.exit(1)


TWEET_FIELDS = ["created_at", "public_metrics", "author_id", "lang"]
USER_FIELDS = ["name", "username", "description", "public_metrics"]
EXPANSIONS = ["author_id"]


def format_tweet(tweet, users_map: dict | None = None) -> dict:
    """Format a tweet object into a readable dict."""
    data = {
        "id": tweet.id,
        "text": tweet.text,
        "created_at": str(tweet.created_at) if tweet.created_at else None,
    }
    if tweet.public_metrics:
        data["metrics"] = tweet.public_metrics
    if users_map and tweet.author_id and tweet.author_id in users_map:
        u = users_map[tweet.author_id]
        data["author"] = f"@{u.username} ({u.name})"
    return data


def build_users_map(response) -> dict:
    """Build a map of user_id -> user from includes."""
    users_map = {}
    if response.includes and "users" in response.includes:
        for u in response.includes["users"]:
            users_map[u.id] = u
    return users_map


def cmd_timeline(client, args):
    """Get authenticated user's home timeline."""
    me = client.get_me()
    if not me or not me.data:
        print("Error: Could not get authenticated user.", file=sys.stderr)
        sys.exit(1)

    response = client.get_home_timeline(
        max_results=min(args.count, 100),
        tweet_fields=TWEET_FIELDS,
        user_fields=USER_FIELDS,
        expansions=EXPANSIONS,
    )
    if not response.data:
        print("No tweets found.")
        return

    users_map = build_users_map(response)
    tweets = [format_tweet(t, users_map) for t in response.data]
    print(json.dumps(tweets, indent=2, ensure_ascii=False))


def cmd_mentions(client, args):
    """Get mentions for the authenticated user."""
    me = client.get_me()
    if not me or not me.data:
        print("Error: Could not get authenticated user.", file=sys.stderr)
        sys.exit(1)

    response = client.get_users_mentions(
        me.data.id,
        max_results=min(args.count, 100),
        tweet_fields=TWEET_FIELDS,
        user_fields=USER_FIELDS,
        expansions=EXPANSIONS,
    )
    if not response.data:
        print("No mentions found.")
        return

    users_map = build_users_map(response)
    tweets = [format_tweet(t, users_map) for t in response.data]
    print(json.dumps(tweets, indent=2, ensure_ascii=False))


def cmd_search(client, args):
    """Search recent tweets."""
    response = client.search_recent_tweets(
        query=args.query,
        max_results=min(args.count, 100),
        tweet_fields=TWEET_FIELDS,
        user_fields=USER_FIELDS,
        expansions=EXPANSIONS,
    )
    if not response.data:
        print("No tweets found.")
        return

    users_map = build_users_map(response)
    tweets = [format_tweet(t, users_map) for t in response.data]
    print(json.dumps(tweets, indent=2, ensure_ascii=False))


def cmd_user(client, args):
    """Get tweets from a specific user."""
    user = client.get_user(username=args.username, user_fields=USER_FIELDS)
    if not user or not user.data:
        print(f"Error: User @{args.username} not found.", file=sys.stderr)
        sys.exit(1)

    print(f"User: @{user.data.username} ({user.data.name})")
    if user.data.description:
        print(f"Bio: {user.data.description}")
    if user.data.public_metrics:
        m = user.data.public_metrics
        print(f"Followers: {m['followers_count']} | Following: {m['following_count']} | Tweets: {m['tweet_count']}")
    print("---")

    response = client.get_users_tweets(
        user.data.id,
        max_results=min(args.count, 100),
        tweet_fields=TWEET_FIELDS,
    )
    if not response.data:
        print("No tweets found.")
        return

    tweets = [format_tweet(t) for t in response.data]
    print(json.dumps(tweets, indent=2, ensure_ascii=False))


def cmd_tweet(client, args):
    """Get a single tweet by ID."""
    response = client.get_tweet(
        args.id,
        tweet_fields=TWEET_FIELDS,
        user_fields=USER_FIELDS,
        expansions=EXPANSIONS,
    )
    if not response or not response.data:
        print(f"Error: Tweet {args.id} not found.", file=sys.stderr)
        sys.exit(1)

    users_map = build_users_map(response)
    tweet = format_tweet(response.data, users_map)
    print(json.dumps(tweet, indent=2, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description="Read tweets from Twitter/X")
    sub = parser.add_subparsers(dest="command", required=True)

    p_tl = sub.add_parser("timeline", help="Home timeline")
    p_tl.add_argument("--count", "-n", type=int, default=20)

    p_mt = sub.add_parser("mentions", help="Your mentions")
    p_mt.add_argument("--count", "-n", type=int, default=10)

    p_sr = sub.add_parser("search", help="Search recent tweets")
    p_sr.add_argument("--query", "-q", required=True, help="Search query")
    p_sr.add_argument("--count", "-n", type=int, default=20)

    p_us = sub.add_parser("user", help="User's tweets")
    p_us.add_argument("--username", "-u", required=True)
    p_us.add_argument("--count", "-n", type=int, default=10)

    p_tw = sub.add_parser("tweet", help="Single tweet by ID")
    p_tw.add_argument("--id", required=True, help="Tweet ID")

    args = parser.parse_args()
    client = get_client()

    handlers = {
        "timeline": cmd_timeline,
        "mentions": cmd_mentions,
        "search": cmd_search,
        "user": cmd_user,
        "tweet": cmd_tweet,
    }
    handlers[args.command](client, args)


if __name__ == "__main__":
    main()
