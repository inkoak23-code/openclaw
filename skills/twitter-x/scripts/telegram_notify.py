#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "httpx>=0.27.0",
# ]
# ///
"""
Send messages to Telegram via Bot API.

Usage:
    uv run telegram_notify.py --text "Hello from OpenClaw!"
    uv run telegram_notify.py --text "$(cat /tmp/digest.txt)"
    echo "piped message" | uv run telegram_notify.py --stdin

Environment variables (required):
    TELEGRAM_BOT_TOKEN  - Bot token from @BotFather
    TELEGRAM_CHAT_ID    - Target chat ID
"""

import argparse
import os
import sys


def send_message(bot_token: str, chat_id: str, text: str, parse_mode: str | None = None):
    """Send a message via Telegram Bot API."""
    import httpx

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    # Telegram has a 4096 char limit per message; split if needed
    chunks = [text[i:i + 4000] for i in range(0, len(text), 4000)]

    for chunk in chunks:
        payload = {"chat_id": chat_id, "text": chunk}
        if parse_mode:
            payload["parse_mode"] = parse_mode

        resp = httpx.post(url, json=payload, timeout=30)
        if resp.status_code != 200:
            print(f"Error: Telegram API returned {resp.status_code}: {resp.text}", file=sys.stderr)
            sys.exit(1)

    print(f"Sent {len(chunks)} message(s) to chat {chat_id}")


def main():
    parser = argparse.ArgumentParser(description="Send Telegram notification")
    parser.add_argument("--text", "-t", help="Message text")
    parser.add_argument("--stdin", action="store_true", help="Read message from stdin")
    parser.add_argument("--parse-mode", choices=["HTML", "Markdown", "MarkdownV2"],
                        default=None, help="Message parse mode")

    args = parser.parse_args()

    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not bot_token:
        print("Error: TELEGRAM_BOT_TOKEN not set", file=sys.stderr)
        sys.exit(1)
    if not chat_id:
        print("Error: TELEGRAM_CHAT_ID not set", file=sys.stderr)
        sys.exit(1)

    if args.stdin:
        text = sys.stdin.read().strip()
    elif args.text:
        text = args.text
    else:
        print("Error: Provide --text or --stdin", file=sys.stderr)
        sys.exit(1)

    if not text:
        print("Error: Empty message", file=sys.stderr)
        sys.exit(1)

    send_message(bot_token, chat_id, text, args.parse_mode)


if __name__ == "__main__":
    main()
