from steamApi import SteamApi, SteamUserData
from WebhookPublisher import WebhookPublisher
from structs import DiscordWebhook
import os

# ===============================================
# OPTIONS
# ===============================================

# Steam Web API key
API_KEY: str = os.environ.get("SteamWebApiKey")

DISCORD_WEBHOOKS = [
    DiscordWebhook(
        webhook_url="",
        user_ids=[

        ]
    )
]

# If true will not notify users, will only update csv
# Make sure to have this True when first getting data for users and no csv history exists, or the users will be notified about buying every game they own
SILENT_MODE = False 

# ===============================================
# MAIN
# ===============================================

def main():
    # Basic settings validation
    if not DISCORD_WEBHOOKS: raise ValueError("DISCORD_WEBHOOKS is not set")
    if not API_KEY:          raise ValueError("API_KEY is not set")

    for index, hook in enumerate(DISCORD_WEBHOOKS):
        # Collect and update data
        user_data: SteamUserData = SteamApi.get_user_owned_apps(API_KEY, hook.user_ids)

        # Optionally ship publishing
        if SILENT_MODE:
            continue
        
        # Make sure the webhook url is not empty
        if not hook.webhook_url: 
            print(f"Warning: Skipping DISCORD_WEBHOOKS[{index}] because it has an empty webhook_url.")
            continue
        
        # Skip if no changes
        if not sum(
            len(user.game_data.added_app_ids) + len(user.game_data.removed_app_ids)
            for user in user_data.steam_users
        ):
            print("Info: No changes!")
            return
        
        # Create app data
        WebhookPublisher.publish_update(hook.webhook_url, API_KEY, user_data)    

if __name__ == "__main__":
    main()