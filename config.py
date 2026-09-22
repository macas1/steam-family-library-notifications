import os
from structs import DiscordWebhook

# Groups of users with what webhook url to publish to
DISCORD_WEBHOOKS = [
    DiscordWebhook(
        steam_web_api_key=os.environ.get("SteamWebApiKeyUser1"),
        steam_web_api_key_2=os.environ.get("SteamWebApiKeyUser2"), # Optional
        webhook_url="",
        user_ids=[]
    )
]

# If true will not notify users, will only update csv
SILENT_MODE = False