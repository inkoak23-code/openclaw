#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "tweepy>=4.14.0",
# ]
# ///
"""
Post tweets to Twitter/X using the v2 API.

Usage:
    uv run twitter_post.py --text "Hello from OpenClaw!"
    uv run twitter_post.py --text "Check this out" --media /tmp/image.png
    uv run twitter_post.py --thread "First tweet" "Second tweet" "Third tweet"

Environment variables (required):
    TWITTER_API_KEY            - API Key (Consumer Key)
    TWITTER_API_SECRET         - API Secret (Consumer Secret)
    TWITTER_ACCESS_TOKEN       - Access Token
    TWITTER_ACCESS_TOKEN_SECRET - Access Token Secret

Optional:
    TWITTER_BEARER_TOKEN       - Bearer Token (for read-only endpoints)
"""

import argparse
import os
import sys

def get_client():
    """Create an authenticated Tweepy client."""
    try:
        import tweepy
    except ImportError:
        print("Error: tweepy not installed. Run: uv run this_script.py", file=sys.stderr)
        sys.exit(1)

    api_key = os.environ.get("TWITTER_API_KEY")
    api_secret = os.environ.get("TWITTER_API_SECRET")
    access_token = os.environ.get("TWITTER_ACCESS_TOKEN")
    access_token_secret = os.environ.get("TWITTER_ACCESS_TOKEN_SECRET")

    missing = []
    if not api_key:
        missing.append("TWITTER_API_KEY")
    if not api_secret:
        missing.append("TWITTER_API_SECRET")
    if not access_token:
        missing.append("TWITTER_ACCESS_TOKEN")
    if not access_token_secret:
        missing.append("TWITTER_ACCESS_TOKEN_SECRET")

    if missing:
        print(f"Error: Missing environment variables: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)

    # v1.1 API for media uploads
    auth = tweepy.OAuth1UserHandler(api_key, api_secret, access_token, access_token_secret)
    api_v1 = tweepy.API(auth)

    # v2 Client for tweet creation
    client = tweepy.Client(
        consumer_key=api_key,
        consumer_secret=api_secret,
        access_token=access_token,
        access_token_secret=access_token_secret,
    )

    return client, api_v1


def upload_media(api_v1, media_path: str) -> str:
    """Upload media file and return media_id."""
    if not os.path.isfile(media_path):
        print(f"Error: Media file not found: {media_path}", file=sys.stderr)
        sys.exit(1)

    media = api_v1.media_upload(filename=media_path)
    print(f"Uploaded media: {media_path} -> media_id={media.media_id}")
    return media.media_id


def post_tweet(client, text: str, media_ids: list | None = None, reply_to: str | None = None):
    """Post a single tweet, optionally with media or as a reply."""
    kwargs = {"text": text}
    if media_ids:
        kwargs["media_ids"] = media_ids
    if reply_to:
        kwargs["in_reply_to_tweet_id"] = reply_to

    response = client.create_tweet(**kwargs)
    tweet_id = response.data["id"]
    print(f"Posted tweet: https://x.com/i/status/{tweet_id}")
    return tweet_id


def post_thread(client, texts: list[str], media_ids: list | None = None):
    """Post a thread of tweets. First tweet optionally includes media."""
    if not texts:
        print("Error: No texts provided for thread.", file=sys.stderr)
        sys.exit(1)

    first_media = media_ids if media_ids else None
    prev_id = post_tweet(client, texts[0], media_ids=first_media)

    for text in texts[1:]:
        prev_id = post_tweet(client, text, reply_to=prev_id)

    print(f"Thread posted: {len(texts)} tweets")


def main():
    parser = argparse.ArgumentParser(description="Post tweets to Twitter/X")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--text", "-t", help="Tweet text (max 280 chars)")
    group.add_argument("--thread", nargs="+", metavar="TEXT", help="Post a thread of tweets")

    parser.add_argument("--media", "-m", action="append", dest="media_files", metavar="FILE",
                        help="Attach media file(s) (images/videos, max 4)")
    parser.add_argument("--reply-to", "-r", metavar="TWEET_ID",
                        help="Reply to an existing tweet ID")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print what would be posted without actually posting")

    args = parser.parse_args()

    if args.dry_run:
        if args.text:
            print(f"[DRY RUN] Would post: {args.text}")
            if args.media_files:
                print(f"[DRY RUN] With media: {args.media_files}")
        elif args.thread:
            for i, t in enumerate(args.thread, 1):
                print(f"[DRY RUN] Thread [{i}/{len(args.thread)}]: {t}")
        return

    client, api_v1 = get_client()

    media_ids = None
    if args.media_files:
        media_ids = [upload_media(api_v1, f) for f in args.media_files]

    if args.text:
        post_tweet(client, args.text, media_ids=media_ids, reply_to=args.reply_to)
    elif args.thread:
        post_thread(client, args.thread, media_ids=media_ids)


if __name__ == "__main__":
    main()
