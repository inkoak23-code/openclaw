#!/usr/bin/env bash
# Daily Twitter/X digest -> Telegram cron job
# Runs twitter_digest.py, then sends output via telegram_notify.py
#
# Usage: Add to crontab:
#   0 9 * * * /path/to/daily_cron.sh
#
# Or use OpenClaw cron:
#   openclaw cron add --name twitter-daily-digest --expression "0 1 * * *" ...

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Source env from openclaw config if not already set
if [ -z "${TWITTER_BEARER_TOKEN:-}" ]; then
    echo "Warning: TWITTER_BEARER_TOKEN not set, attempting to load from openclaw config" >&2
fi

# Fetch digest (uses single combined OR query to save rate limits)
DIGEST=$(uv run "$SCRIPT_DIR/twitter_digest.py" \
    --sources timeline \
    --search "crypto,Web3,DeFi,Bitcoin,BTC,ETH" \
    --count 30 \
    --format text 2>&1) || true

if [ -z "$DIGEST" ]; then
    DIGEST="[Twitter Digest] No tweets found for today's topics."
fi

# Send to Telegram group (DClaw group, both accounts receive)
# Use TELEGRAM_CHAT_ID=-5260745220 for group, or 6936746569 for private
echo "$DIGEST" | uv run "$SCRIPT_DIR/telegram_notify.py" --stdin

echo "Daily digest sent to Telegram at $(date -u +%Y-%m-%dT%H:%M:%SZ)"
