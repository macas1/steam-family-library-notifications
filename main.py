from steamApi import SteamApi, SteamUserData
from webhookPublisher import WebhookPublisher
from pathlib import Path
from structs import PublishState
from traceback import print_exception
from config import *

def main():
    # Config validation
    if not DISCORD_WEBHOOKS: raise ValueError("DISCORD_WEBHOOKS is not set")

    for index, hook in enumerate(DISCORD_WEBHOOKS):
        print(f"Info: Processing hook {index}: {hook.webhook_url}")

        # Config validation
        if not hook.steam_web_api_key: 
            print("Error: steam_web_api_key is not set for DISCORD_WEBHOOKS[{index}]")     

        # Collect data
        user_csvs_exists = all_filenames_exist("user_data", hook.user_ids)
        try:
            user_data: SteamUserData = SteamApi.get_user_owned_apps(
                [key for key in (hook.steam_web_api_key, hook.steam_web_api_key_2) if key], 
                hook.user_ids
            )
        except Exception as e:
            print("Error: DISCORD_WEBHOOKS[{index}] failed to get user apps")
            print_exception(e)
            continue

        # Publish
        publish_state = None
        # Optionally skip publishing
        if SILENT_MODE:
            publish_state = PublishState("SKIPPED")
            print(f"Info: Silent mode enabled, skipping publish stage")

        # Skip publishing if a user doesn't have an existing csv file
        elif not user_csvs_exists:
            publish_state = PublishState("SKIPPED")
            print(f"Info: Silent mode enforced for DISCORD_WEBHOOKS[{index}], as at least one user has no previously recorded data")
        
        # Skip publishing if the webhook url is empty
        elif not hook.webhook_url: 
            publish_state = PublishState("SKIPPED")
            print(f"Warning: Silent mode enforced for DISCORD_WEBHOOKS[{index}], as it has an empty webhook_url")
        
        # Skip publishing if no changes
        elif not any(
            user.game_data.added_app_ids or user.game_data.removed_app_ids
            for user in user_data.steam_users
        ):
            publish_state = PublishState("SKIPPED")
            print("Info: No changes! Skipping publish stage")

        # Generate and publish a message to the discord webhook
        else:
            print(f"Info: Publishing to webhook")
            try:
                if(WebhookPublisher.publish_update(hook.webhook_url, hook.steam_web_api_key, user_data)):
                    publish_state = PublishState("SUCCESS")
                else:
                    publish_state = PublishState("FAILED")
            except Exception as e:
                publish_state = PublishState("FAILED")
                print(f"Error: DISCORD_WEBHOOKS[{index}] failed to format and publish data")
                print_exception(e)

        # If everything ran correctly, update locally stored data
        if publish_state != PublishState("FAILED"):
            print(f"Info: Updating local data")
            SteamApi.update_stored_user_data(user_data)

        # Spacer between individual webhook logs
        print()

    print("Info: Application completed successfully")

def all_filenames_exist(directory: str, filenames: list[str]) -> bool:
    existing = {p.stem for p in Path(directory).iterdir() if p.is_file()}
    incoming = {str(f) for f in filenames}
    return incoming.issubset(existing)

if __name__ == "__main__":
    main()