# Steam Family Library Notifier

A Python tool that monitors Steam library changes for a group of users in a Steam Family and sends notifications via Discord webhooks when games are added or removed.

It does this with no web scraping and without requiring Steam login credentials or tokens.

---

## 📥 Installation

### 1. Requirements
- Python 3.10+
- Steam Web API key

---

### 2. Steam API Key Setup

Obtain a Steam API key from:
https://steamcommunity.com/dev

Set it as an environment variable (example name: `SteamWebApiKeyUserName1`) to be used in the config.py file.

**Important notes:**
- The API key is tied to the Steam account used to generate it.
- All API requests are executed from the perspective of that account.
- If a Steam account being tracked has its profile or game details set to friends only, the account used to generate the API key must be on their Steam friends list for that data to be returned.
- No users in the list can have their game details set to private, must be public or friends only.
- If the Steam account used to generate the API key is also part of the tracked accounts, apps that account has set to private will still be included in the API response when querying its own owned apps.  
If you'd like to avoid this, use a secondary API key as well. Only data seen by both keys will be used, avoiding any private information leaks like this.

---

### 3. Configuration

Edit `config.py` and add your Discord webhooks, api keys and Steam user IDs:

```python
DISCORD_WEBHOOKS = [
    DiscordWebhook(
        webhook_url="https://your_discord_webhook",
        steam_web_api_key=os.environ.get("SteamWebApiKeyUser1"),
        steam_web_api_key_2=os.environ.get("SteamWebApiKeyUser2"), # Optional
        user_ids=[
            123456789123456789,  # Family member 1
            223456789123456789,  # Family member 2
            323456789123456789,  # Family member 3
            423456789123456789,  # Family member 4
            523456789123456789,  # Family member 5
            623456789123456789,  # Family member 6
        ]
    )
]
```
### 4. Dependencies

```
pip install -U "steam[client]"
pip install requests
pip install pydantic
pip install colorthief
```

### 5. Schedule
Run `main.py` once to initialize local history.

After initialization, schedule it to run periodically (recommended: once per day).

Most operating systems provide built-in scheduling tools such as Task Scheduler (Windows) or cron (Linux/macOS).