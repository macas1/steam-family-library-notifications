from steamApi import SteamApi, SteamUserData
from WebhookPublisher import WebhookPublisher
from pathlib import Path
from traceback import print_exc
from config import *

def main():
    # Config validation
    if not DISCORD_WEBHOOKS: raise ValueError("DISCORD_WEBHOOKS is not set")

    for index, hook in enumerate(DISCORD_WEBHOOKS):
        # Config validation and organisation
        if not hook.steam_web_api_key: 
            print("Error: steam_web_api_key is not set for DISCORD_WEBHOOKS[{index}].")     

        # Check if all of the user's apps have been previously recorded
        user_csvs_exists = all_filenames_exist("user_data", hook.user_ids)
        
        # Collect and update data
        try:
            user_data: SteamUserData = SteamApi.get_user_owned_apps(
                [key for key in (hook.steam_web_api_key, hook.steam_web_api_key_2) if key], 
                hook.user_ids
            )
        except Exception as e:
            print("Error: DISCORD_WEBHOOKS[{index}] failed to get user apps")
            print_exc(e)
            continue

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
            continue
        
        # Generate and publish a message to the discord webhook
        try:
            WebhookPublisher.publish_update(hook.webhook_url, hook.steam_web_api_key, user_data)   
        except Exception as e:
            print("Error: DISCORD_WEBHOOKS[{index}] failed to format and publish data")
            print_exc(e)
            continue

def all_filenames_exist(directory: str, filenames: list[str]) -> bool:
    existing = {p.stem for p in Path(directory).iterdir() if p.is_file()}
    incoming = {str(f) for f in filenames}
    return incoming.issubset(existing)

if __name__ == "__main__":
    main()