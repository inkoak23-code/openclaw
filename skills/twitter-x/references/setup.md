# Twitter/X API Setup

## 1. Create a Developer Account

1. Go to https://developer.x.com/ and sign in
2. Apply for a developer account (Free tier supports posting + reading)
3. Create a Project and an App inside it

## 2. Generate Credentials

In the Developer Portal under your App:

1. Go to "Keys and Tokens"
2. Generate **API Key and Secret** (Consumer Keys)
3. Generate **Access Token and Secret** (with Read and Write permissions)
4. Copy the **Bearer Token**

## 3. Configure in OpenClaw

Add to `~/.openclaw/openclaw.json`:

```json
{
  "skills": {
    "twitter-x": {
      "env": {
        "TWITTER_API_KEY": "your-api-key",
        "TWITTER_API_SECRET": "your-api-secret",
        "TWITTER_ACCESS_TOKEN": "your-access-token",
        "TWITTER_ACCESS_TOKEN_SECRET": "your-access-token-secret",
        "TWITTER_BEARER_TOKEN": "your-bearer-token"
      }
    }
  }
}
```

Or set them as shell environment variables.

## 4. API Rate Limits (Free Tier)

| Endpoint      | Rate Limit                                     |
| ------------- | ---------------------------------------------- |
| POST tweets   | 17 tweets / 24h (user), 100 tweets / 24h (app) |
| GET timeline  | 15 requests / 15min                            |
| GET mentions  | 10 requests / 15min                            |
| Search recent | 60 requests / 15min                            |

Basic tier ($100/mo) raises these significantly. See https://developer.x.com/en/docs/twitter-api/rate-limits.

## 5. Permissions

Ensure your App has **Read and Write** permission:

- Developer Portal > App > Settings > User authentication settings
- Set "App permissions" to "Read and Write"

## 6. Verify Setup

```bash
# Test read access
uv run {baseDir}/scripts/twitter_read.py timeline --count 5

# Test post (dry run)
uv run {baseDir}/scripts/twitter_post.py --text "Test" --dry-run
```
