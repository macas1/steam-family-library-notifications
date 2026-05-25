from steamApi import SteamApi, SteamUserData
from WebhookPublisher import WebhookPublisher
from structs import DiscordWebhook
from pathlib import Path
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
SILENT_MODE = False 

# ===============================================
# Methods
# ===============================================

def main():
    # Basic settings validation
    if not DISCORD_WEBHOOKS: raise ValueError("DISCORD_WEBHOOKS is not set")
    if not API_KEY:          raise ValueError("API_KEY is not set")

    for index, hook in enumerate(DISCORD_WEBHOOKS):
        # Check if all of the user's apps have been previously recorded
        user_csvs_exists = all_filenames_exist("user_data", hook.user_ids)
        
        # Collect and update data
        user_data: SteamUserData = SteamApi.get_user_owned_apps(API_KEY, hook.user_ids)

        # Optionally skip publishing
        if SILENT_MODE:
            continue

        # Skip publishing if a user doesn't have an existing csv file
        if not user_csvs_exists:
            print(f"Info: Silent mode enforced for DISCORD_WEBHOOKS[{index}], as at least one user has no previously recorded data.")
            continue
        
        # Skip publishing if the webhook url is not empty
        if not hook.webhook_url: 
            print(f"Warning: Silent mode enforced for DISCORD_WEBHOOKS[{index}], as it has an empty webhook_url.")
            continue
        
        # Skip publishing if no changes
        if not sum(
            len(user.game_data.added_app_ids) + len(user.game_data.removed_app_ids)
            for user in user_data.steam_users
        ):
            print("Info: No changes!")
            return
        
        # Generate and publish a message to the discord webhook
        WebhookPublisher.publish_update(hook.webhook_url, API_KEY, user_data)   

def all_filenames_exist(directory: str, filenames: list[str]) -> bool:
    existing = {p.stem for p in Path(directory).iterdir() if p.is_file()}
    incoming = {str(f) for f in filenames}
    return incoming.issubset(existing)

if __name__ == "__main__":
    main()