#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "httpx>=0.27.0",
#     "tweepy>=4.14.0",
# ]
# ///
"""
Interactive Telegram bot for ClawBot — receive commands via Telegram chat
and execute Twitter/X operations.

Usage:
    uv run telegram_bot.py              # start listening (long-polling)
    uv run telegram_bot.py --once       # process one update then exit

Commands (send in Telegram):
    /search <query>     - Search recent tweets
    /hot <topic>        - Top tweets on a topic (sorted by engagement)
    /digest             - Generate crypto/Web3 daily digest
    /post <text>        - Post a tweet (requires OAuth tokens)
    /help               - Show available commands

Environment variables:
    TELEGRAM_BOT_TOKEN          (required)
    TELEGRAM_CHAT_ID            (optional, restrict to specific chat)
    TWITTER_BEARER_TOKEN        (required for read operations)
    TWITTER_API_KEY             (required for posting)
    TWITTER_API_SECRET          (required for posting)
    TWITTER_ACCESS_TOKEN        (required for posting)
    TWITTER_ACCESS_TOKEN_SECRET (required for posting)
"""

import argparse
import json
import os
import signal
import sys
import time
from datetime import datetime, timezone

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
ALLOWED_CHAT_IDS = set()

# If TELEGRAM_CHAT_ID is set, only respond to that chat (comma-separated for multiple)
_chat_ids = os.environ.get("TELEGRAM_CHAT_ID", "")
if _chat_ids:
    for cid in _chat_ids.split(","):
        cid = cid.strip()
        if cid:
            ALLOWED_CHAT_IDS.add(int(cid))


# ---------------------------------------------------------------------------
# Telegram helpers
# ---------------------------------------------------------------------------

def tg_request(method: str, **kwargs):
    """Call a Telegram Bot API method."""
    import httpx
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"
    resp = httpx.post(url, json=kwargs, timeout=60)
    data = resp.json()
    if not data.get("ok"):
        print(f"TG API error [{method}]: {data}", file=sys.stderr)
    return data


def send_reply(chat_id: int, text: str):
    """Send a text reply, splitting if too long."""
    chunks = [text[i:i + 4000] for i in range(0, len(text), 4000)]
    for chunk in chunks:
        tg_request("sendMessage", chat_id=chat_id, text=chunk)


def send_typing(chat_id: int):
    """Show 'typing...' indicator."""
    tg_request("sendChatAction", chat_id=chat_id, action="typing")


# ---------------------------------------------------------------------------
# Twitter helpers
# ---------------------------------------------------------------------------

def get_twitter_client():
    """Create a Tweepy client."""
    import tweepy

    bearer = os.environ.get("TWITTER_BEARER_TOKEN")
    api_key = os.environ.get("TWITTER_API_KEY")
    api_secret = os.environ.get("TWITTER_API_SECRET")
    access_token = os.environ.get("TWITTER_ACCESS_TOKEN")
    access_secret = os.environ.get("TWITTER_ACCESS_TOKEN_SECRET")

    if api_key and api_secret and access_token and access_secret:
        return tweepy.Client(
            bearer_token=bearer,
            consumer_key=api_key,
            consumer_secret=api_secret,
            access_token=access_token,
            access_token_secret=access_secret,
        )
    if bearer:
        return tweepy.Client(bearer_token=bearer)
    return None


TWEET_FIELDS = ["created_at", "public_metrics", "author_id", "lang"]
USER_FIELDS = ["name", "username"]
EXPANSIONS = ["author_id"]


def extract_tweets(response) -> list[dict]:
    """Extract tweets from a Tweepy response."""
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
            entry["impressions"] = t.public_metrics.get("impression_count", 0)
        if t.author_id and t.author_id in users_map:
            u = users_map[t.author_id]
            entry["author"] = f"@{u.username}"
            entry["author_name"] = u.name
        results.append(entry)
    return results


def engagement_score(t: dict) -> int:
    return t.get("likes", 0) * 3 + t.get("retweets", 0) * 5 + t.get("replies", 0) * 2 + t.get("impressions", 0)


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------

def cmd_help(chat_id: int, _args: str):
    """Show help message."""
    text = (
        "🤖 ClawBot 可用命令：\n\n"
        "/search <关键词> — 搜索最近的推文\n"
        "  例: /search Solana DeFi\n\n"
        "/hot <话题> — 获取某话题的热门推文 Top 5\n"
        "  例: /hot Bitcoin\n\n"
        "/digest — 生成今日加密/Web3 简报\n\n"
        "/post <内容> — 发送一条推文\n"
        "  例: /post Hello from ClawBot!\n\n"
        "/help — 显示本帮助信息"
    )
    send_reply(chat_id, text)


def cmd_search(chat_id: int, args: str):
    """Search recent tweets."""
    if not args.strip():
        send_reply(chat_id, "用法: /search <关键词>\n例: /search Solana NFT")
        return

    send_typing(chat_id)
    client = get_twitter_client()
    if not client:
        send_reply(chat_id, "Twitter API 未配置，无法搜索。")
        return

    query = f"{args.strip()} -is:retweet"
    try:
        resp = client.search_recent_tweets(
            query=query,
            max_results=10,
            tweet_fields=TWEET_FIELDS,
            user_fields=USER_FIELDS,
            expansions=EXPANSIONS,
        )
        tweets = extract_tweets(resp)
    except Exception as e:
        send_reply(chat_id, f"搜索失败: {e}")
        return

    if not tweets:
        send_reply(chat_id, f"未找到关于 \"{args.strip()}\" 的推文。")
        return

    lines = [f"🔍 搜索: {args.strip()} ({len(tweets)} 条)\n"]
    for i, t in enumerate(tweets, 1):
        author = t.get("author", "unknown")
        likes = t.get("likes", 0)
        rts = t.get("retweets", 0)
        text = t["text"][:200].replace("\n", " ")
        lines.append(f"{i}. {author} [❤️{likes} 🔁{rts}]\n   {text}\n")

    send_reply(chat_id, "\n".join(lines))


def cmd_hot(chat_id: int, args: str):
    """Get top tweets by engagement."""
    if not args.strip():
        send_reply(chat_id, "用法: /hot <话题>\n例: /hot Solana")
        return

    send_typing(chat_id)
    client = get_twitter_client()
    if not client:
        send_reply(chat_id, "Twitter API 未配置。")
        return

    query = f"{args.strip()} -is:retweet lang:en"
    try:
        resp = client.search_recent_tweets(
            query=query,
            max_results=30,
            tweet_fields=TWEET_FIELDS,
            user_fields=USER_FIELDS,
            expansions=EXPANSIONS,
            sort_order="relevancy",
        )
        tweets = extract_tweets(resp)
    except Exception as e:
        send_reply(chat_id, f"搜索失败: {e}")
        return

    if not tweets:
        send_reply(chat_id, f"未找到关于 \"{args.strip()}\" 的热门推文。")
        return

    # Sort by engagement and take top 5
    tweets.sort(key=engagement_score, reverse=True)
    top = tweets[:5]

    lines = [f"🔥 {args.strip()} 热门 Top {len(top)}\n"]
    for i, t in enumerate(top, 1):
        author = t.get("author", "unknown")
        name = t.get("author_name", "")
        likes = t.get("likes", 0)
        rts = t.get("retweets", 0)
        impr = t.get("impressions", 0)
        text = t["text"][:200].replace("\n", " ")
        lines.append(
            f"{'🥇🥈🥉'[i-1] if i <= 3 else '🔹'} #{i} {author} ({name})\n"
            f"   ❤️{likes} 🔁{rts} 👁{impr}\n"
            f"   {text}\n"
        )

    send_reply(chat_id, "\n".join(lines))


def cmd_digest(chat_id: int, _args: str):
    """Generate crypto/Web3 digest."""
    send_typing(chat_id)
    client = get_twitter_client()
    if not client:
        send_reply(chat_id, "Twitter API 未配置。")
        return

    topics = ["crypto", "Web3", "DeFi", "Bitcoin", "Solana"]
    query = " OR ".join(topics) + " -is:retweet lang:en"

    try:
        resp = client.search_recent_tweets(
            query=query,
            max_results=30,
            tweet_fields=TWEET_FIELDS,
            user_fields=USER_FIELDS,
            expansions=EXPANSIONS,
            sort_order="relevancy",
        )
        tweets = extract_tweets(resp)
    except Exception as e:
        send_reply(chat_id, f"获取失败: {e}")
        return

    if not tweets:
        send_reply(chat_id, "今日暂无相关推文。")
        return

    tweets.sort(key=engagement_score, reverse=True)
    top = tweets[:10]

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [f"📊 加密/Web3 每日简报\n🕐 {now}\n━━━━━━━━━━━━━━━━━\n"]

    for i, t in enumerate(top, 1):
        author = t.get("author", "unknown")
        likes = t.get("likes", 0)
        rts = t.get("retweets", 0)
        text = t["text"][:200].replace("\n", " ")
        lines.append(f"{i}. {author} [❤️{likes} 🔁{rts}]\n   {text}\n")

    lines.append("━━━━━━━━━━━━━━━━━")
    send_reply(chat_id, "\n".join(lines))


def cmd_post(chat_id: int, args: str):
    """Post a tweet."""
    if not args.strip():
        send_reply(chat_id, "用法: /post <推文内容>\n例: /post Hello World!")
        return

    send_typing(chat_id)

    import tweepy

    api_key = os.environ.get("TWITTER_API_KEY")
    api_secret = os.environ.get("TWITTER_API_SECRET")
    access_token = os.environ.get("TWITTER_ACCESS_TOKEN")
    access_secret = os.environ.get("TWITTER_ACCESS_TOKEN_SECRET")

    if not all([api_key, api_secret, access_token, access_secret]):
        send_reply(chat_id, "发推需要 OAuth 完整配置（API Key + Access Token），当前未设置。")
        return

    client = tweepy.Client(
        consumer_key=api_key,
        consumer_secret=api_secret,
        access_token=access_token,
        access_token_secret=access_secret,
    )

    text = args.strip()
    if len(text) > 280:
        send_reply(chat_id, f"推文内容过长 ({len(text)}/280)，请缩短。")
        return

    try:
        resp = client.create_tweet(text=text)
        tweet_id = resp.data["id"]
        send_reply(chat_id, f"✅ 推文已发送！\nhttps://twitter.com/i/status/{tweet_id}")
    except Exception as e:
        send_reply(chat_id, f"发推失败: {e}")


# Command routing table
COMMANDS = {
    "/help": cmd_help,
    "/start": cmd_help,
    "/search": cmd_search,
    "/hot": cmd_hot,
    "/digest": cmd_digest,
    "/post": cmd_post,
}


def handle_message(message: dict):
    """Route an incoming message to the right handler."""
    chat_id = message["chat"]["id"]
    text = message.get("text", "").strip()

    if not text:
        return

    # Check if this chat is allowed
    if ALLOWED_CHAT_IDS and chat_id not in ALLOWED_CHAT_IDS:
        return

    # Parse command
    if text.startswith("/"):
        parts = text.split(maxsplit=1)
        cmd = parts[0].lower().split("@")[0]  # strip @botname suffix
        args = parts[1] if len(parts) > 1 else ""

        handler = COMMANDS.get(cmd)
        if handler:
            try:
                handler(chat_id, args)
            except Exception as e:
                send_reply(chat_id, f"命令执行出错: {e}")
        else:
            send_reply(chat_id, f"未知命令: {cmd}\n输入 /help 查看可用命令")
    else:
        # Non-command text — echo a hint
        send_reply(chat_id, "请使用 / 开头的命令，输入 /help 查看帮助。")


# ---------------------------------------------------------------------------
# Main loop (long-polling)
# ---------------------------------------------------------------------------

def poll_loop(once: bool = False):
    """Long-polling loop to receive updates from Telegram."""
    import httpx

    offset = 0
    print(f"ClawBot started. Listening for Telegram messages...", flush=True)
    if ALLOWED_CHAT_IDS:
        print(f"Restricted to chat IDs: {ALLOWED_CHAT_IDS}", flush=True)

    while True:
        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
            params = {"offset": offset, "timeout": 30}
            resp = httpx.get(url, params=params, timeout=60)
            data = resp.json()

            if not data.get("ok"):
                print(f"getUpdates error: {data}", file=sys.stderr)
                time.sleep(5)
                continue

            for update in data.get("result", []):
                offset = update["update_id"] + 1
                msg = update.get("message")
                if msg:
                    who = msg.get("from", {}).get("username", "?")
                    txt = msg.get("text", "")[:50]
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] @{who}: {txt}", flush=True)
                    handle_message(msg)

            if once:
                break

        except KeyboardInterrupt:
            print("\nStopping ClawBot.")
            break
        except Exception as e:
            print(f"Poll error: {e}", file=sys.stderr)
            time.sleep(5)


def main():
    if not BOT_TOKEN:
        print("Error: TELEGRAM_BOT_TOKEN not set", file=sys.stderr)
        sys.exit(1)

    parser = argparse.ArgumentParser(description="ClawBot - Interactive Telegram bot")
    parser.add_argument("--once", action="store_true", help="Process one batch of updates then exit")
    args = parser.parse_args()

    # Graceful shutdown
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))

    poll_loop(once=args.once)


if __name__ == "__main__":
    main()
