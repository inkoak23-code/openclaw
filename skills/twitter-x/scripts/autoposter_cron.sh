#!/usr/bin/env bash
# Web3 Founder Autoposter — cron wrapper
#
# Runs the autoposter to generate and post 1 tweet per invocation.
# Schedule this 3 times/day at staggered, non-round times to appear human.
#
# Example crontab (US/EU active hours, slightly randomized):
#   23 14 * * * /path/to/autoposter_cron.sh    # ~10:23 AM ET
#   47 18 * * * /path/to/autoposter_cron.sh    # ~2:47 PM ET
#   12 23 * * * /path/to/autoposter_cron.sh    # ~7:12 PM ET
#
# Or use OpenClaw cron:
#   openclaw cron add --name "web3-autoposter" \
#     --schedule cron --expression "23 14,18,23 * * *" \
#     --timezone "America/New_York" --mode isolated \
#     --message "Run web3_autoposter.py to auto-generate and post a tweet"

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="${OPENCLAW_ENV_FILE:-$HOME/.openclaw/.env}"

# Load environment
if [ -f "$ENV_FILE" ]; then
    set -a
    source "$ENV_FILE"
    set +a
fi

# Add random delay (0-15 min) to avoid exact cron-time patterns
DELAY=$((RANDOM % 900))
echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Sleeping ${DELAY}s for randomization..."
sleep "$DELAY"

# Run autoposter (1 tweet per invocation)
echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Starting autoposter..."
uv run "$SCRIPT_DIR/web3_autoposter.py" --count 1 2>&1

EXIT_CODE=$?
if [ $EXIT_CODE -ne 0 ]; then
    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Autoposter failed with exit code $EXIT_CODE" >&2
    # Notify failure to Telegram
    if [ -n "${TELEGRAM_BOT_TOKEN:-}" ] && [ -n "${TELEGRAM_CHAT_ID:-}" ]; then
        uv run "$SCRIPT_DIR/telegram_notify.py" \
            --text "⚠️ Autoposter failed at $(date -u +%Y-%m-%dT%H:%M:%SZ) with exit code $EXIT_CODE" 2>/dev/null || true
    fi
fi

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Done."
