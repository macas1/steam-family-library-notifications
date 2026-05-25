import os
from structs import DiscordWebhook

# Steam Web API key
API_KEY: str = os.environ.get("SteamWebApiKey")

# Groups of users with what webhook url to publish to
DISCORD_WEBHOOKS = [
    DiscordWebhook(
        webhook_url="",
        user_ids=[]
    )
]

# If true will not notify users, will only update csv
SILENT_MODE = False 