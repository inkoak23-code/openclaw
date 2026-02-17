#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "tweepy>=4.14.0",
#     "httpx>=0.27.0",
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
from datetime import datetime, timezone

def get_credentials():
    """Read and validate Twitter API credentials from environment."""
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

    return api_key, api_secret, access_token, access_token_secret


def get_client():
    """Create an authenticated Tweepy client."""
    try:
        import tweepy
    except ImportError:
        print("Error: tweepy not installed. Run: uv run this_script.py", file=sys.stderr)
        sys.exit(1)

    api_key, api_secret, access_token, access_token_secret = get_credentials()

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


def verify_permissions():
    """Verify Twitter API credentials and app permissions for posting."""
    try:
        import tweepy
    except ImportError:
        print("Error: tweepy not installed. Run: uv run this_script.py", file=sys.stderr)
        sys.exit(1)

    api_key, api_secret, access_token, access_token_secret = get_credentials()

    print("=== Twitter API Permission Diagnostic ===\n")

    # Check credentials format
    print(f"API Key:            {api_key[:6]}...{api_key[-4:]}")
    print(f"API Secret:         {api_secret[:4]}...{api_secret[-4:]}")
    print(f"Access Token:       {access_token[:6]}...{access_token[-4:]}")
    print(f"Access Token Secret: {access_token_secret[:4]}...{access_token_secret[-4:]}")
    print()

    # Test 1: Verify credentials with v1.1 API (returns permission level)
    print("[1/3] Checking OAuth1 credentials via v1.1 API...")
    auth = tweepy.OAuth1UserHandler(api_key, api_secret, access_token, access_token_secret)
    api_v1 = tweepy.API(auth)
    try:
        resp = api_v1.verify_credentials()
        print(f"  OK — Authenticated as: @{resp.screen_name} (id={resp.id})")
    except tweepy.Unauthorized as e:
        print(f"  FAIL — 401 Unauthorized: credentials are invalid.")
        print(f"  Detail: {e}")
        print(f"\n  Fix: Regenerate all 4 credentials in Developer Portal > Keys and Tokens.")
        sys.exit(1)
    except tweepy.Forbidden as e:
        print(f"  FAIL — 403 Forbidden: {e}")
        print(f"\n  This usually means your App lacks 'User authentication' settings.")
        print(f"  Fix: Developer Portal > App > Settings > User authentication settings > Set up")
        sys.exit(1)
    except Exception as e:
        print(f"  FAIL — {type(e).__name__}: {e}")
        sys.exit(1)

    # Test 2: Check the access level header from the last response
    print("\n[2/3] Checking app permission level...")
    try:
        last_resp = api_v1.last_response
        access_level = last_resp.headers.get("x-access-level", "unknown")
        print(f"  x-access-level: {access_level}")
        if "write" in access_level.lower():
            print(f"  OK — App has write permission.")
        elif access_level == "unknown":
            print(f"  WARN — Could not determine access level from headers.")
            print(f"  The x-access-level header may not be present on all endpoints.")
        else:
            print(f"  FAIL — App only has '{access_level}' permission. 'Read and write' is required.")
            print(f"\n  Fix:")
            print(f"    1. Developer Portal > App > Settings > User authentication settings")
            print(f"    2. Set 'App permissions' to 'Read and Write'")
            print(f"    3. Save, then go to 'Keys and Tokens'")
            print(f"    4. Regenerate Access Token and Secret")
            print(f"    5. Update your config with the NEW tokens")
            sys.exit(1)
    except Exception:
        print(f"  WARN — Could not read access level header.")

    # Test 3: Try the v2 /2/users/me endpoint
    print("\n[3/3] Checking v2 API access...")
    client = tweepy.Client(
        consumer_key=api_key,
        consumer_secret=api_secret,
        access_token=access_token,
        access_token_secret=access_token_secret,
    )
    try:
        me = client.get_me()
        print(f"  OK — v2 API authenticated as: @{me.data.username} (id={me.data.id})")
    except tweepy.Forbidden as e:
        print(f"  FAIL — 403 Forbidden on v2 API: {e}")
        print(f"\n  Your app may not have the v2 tweet.read or tweet.write scope.")
        sys.exit(1)
    except Exception as e:
        print(f"  FAIL — {type(e).__name__}: {e}")
        sys.exit(1)

    print("\n=== All checks passed. Your app should be able to post tweets. ===")
    print("If posting still fails with 403, the most likely cause is:")
    print("  - Access Token was generated BEFORE you set 'Read and Write' permission")
    print("  - Fix: Regenerate Access Token & Secret AFTER setting permissions, then update config")


def send_telegram_notification(tweet_text: str, tweet_url: str, tweet_type: str = "post"):
    """Send a Telegram notification after posting a tweet."""
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not bot_token or not chat_id:
        print("Warning: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set, skipping notification.", file=sys.stderr)
        return

    try:
        import httpx
    except ImportError:
        print("Warning: httpx not installed, skipping Telegram notification.", file=sys.stderr)
        return

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    message = (
        f"📢 New Tweet Posted\n"
        f"🕐 Time: {timestamp}\n"
        f"📝 Content: {tweet_text}\n"
        f"🔗 Link: {tweet_url}\n"
        f"📊 Type: {tweet_type}"
    )

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message}

    try:
        resp = httpx.post(url, json=payload, timeout=30)
        if resp.status_code == 200:
            print(f"Telegram notification sent.")
        else:
            print(f"Warning: Telegram API returned {resp.status_code}: {resp.text}", file=sys.stderr)
    except Exception as e:
        print(f"Warning: Failed to send Telegram notification: {e}", file=sys.stderr)


def upload_media(api_v1, media_path: str) -> str:
    """Upload media file and return media_id."""
    if not os.path.isfile(media_path):
        print(f"Error: Media file not found: {media_path}", file=sys.stderr)
        sys.exit(1)

    media = api_v1.media_upload(filename=media_path)
    print(f"Uploaded media: {media_path} -> media_id={media.media_id}")
    return media.media_id


def post_tweet(client, text: str, media_ids: list | None = None, reply_to: str | None = None,
               notify: bool = False, tweet_type: str = "post"):
    """Post a single tweet, optionally with media or as a reply."""
    import tweepy

    kwargs = {"text": text}
    if media_ids:
        kwargs["media_ids"] = media_ids
    if reply_to:
        kwargs["in_reply_to_tweet_id"] = reply_to

    try:
        response = client.create_tweet(**kwargs)
    except tweepy.Forbidden as e:
        print(f"\nError: 403 Forbidden — cannot post tweet.", file=sys.stderr)
        print(f"Detail: {e}", file=sys.stderr)
        print(f"\nThis means your app's Access Token does not have write permission.", file=sys.stderr)
        print(f"To fix this:", file=sys.stderr)
        print(f"  1. Go to https://developer.x.com/ > your App > Settings", file=sys.stderr)
        print(f"  2. Under 'User authentication settings', set App permissions to 'Read and Write'", file=sys.stderr)
        print(f"  3. Go to 'Keys and Tokens' and REGENERATE Access Token & Secret", file=sys.stderr)
        print(f"  4. Update your config with the NEW Access Token and Secret", file=sys.stderr)
        print(f"\nRun with --verify to diagnose your permissions in detail.", file=sys.stderr)
        sys.exit(1)

    tweet_id = response.data["id"]
    tweet_url = f"https://x.com/i/status/{tweet_id}"
    print(f"Posted tweet: {tweet_url}")

    if notify:
        send_telegram_notification(text, tweet_url, tweet_type)

    return tweet_id


def post_thread(client, texts: list[str], media_ids: list | None = None,
                notify: bool = False, tweet_type: str = "thread"):
    """Post a thread of tweets. First tweet optionally includes media."""
    if not texts:
        print("Error: No texts provided for thread.", file=sys.stderr)
        sys.exit(1)

    first_media = media_ids if media_ids else None
    prev_id = post_tweet(client, texts[0], media_ids=first_media)
    thread_url = f"https://x.com/i/status/{prev_id}"

    for text in texts[1:]:
        prev_id = post_tweet(client, text, reply_to=prev_id)

    print(f"Thread posted: {len(texts)} tweets")

    if notify:
        full_content = "\n---\n".join(f"[{i+1}/{len(texts)}] {t}" for i, t in enumerate(texts))
        send_telegram_notification(full_content, thread_url, tweet_type)


def main():
    parser = argparse.ArgumentParser(description="Post tweets to Twitter/X")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--text", "-t", help="Tweet text (max 280 chars)")
    group.add_argument("--thread", nargs="+", metavar="TEXT", help="Post a thread of tweets")
    group.add_argument("--verify", action="store_true",
                       help="Verify API credentials and app permissions (diagnose 403 errors)")

    parser.add_argument("--media", "-m", action="append", dest="media_files", metavar="FILE",
                        help="Attach media file(s) (images/videos, max 4)")
    parser.add_argument("--reply-to", "-r", metavar="TWEET_ID",
                        help="Reply to an existing tweet ID")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print what would be posted without actually posting")
    parser.add_argument("--notify", action="store_true",
                        help="Send Telegram notification after posting (requires TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)")
    parser.add_argument("--type", dest="tweet_type", default="post",
                        choices=["hot take", "builder insight", "alpha thread", "engagement", "reply", "QT", "post"],
                        help="Tweet type label for Telegram notification (default: post)")

    args = parser.parse_args()

    if args.verify:
        verify_permissions()
        return

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
        post_tweet(client, args.text, media_ids=media_ids, reply_to=args.reply_to,
                   notify=args.notify, tweet_type=args.tweet_type)
    elif args.thread:
        post_thread(client, args.thread, media_ids=media_ids,
                    notify=args.notify, tweet_type=args.tweet_type)


if __name__ == "__main__":
    main()
