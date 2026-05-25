from steamApi import SteamApi, SteamUserData
from WebhookPublisher import WebhookPublisher
import os

# ===============================================
# OPTIONS
# ===============================================

# Steam Web API key
API_KEY: str = os.environ.get("SteamWebApiKey")
# The webhook to be displayed to
DISCORD_WEBHOOK: str = ""
# User Steam ids to watch, should be the users in your steam family.
USERS: list[int] = [
    76561198060418017, # Me
    76561198915761429, # Bean
    76561198206657967, # Tanner
    76561198125949369, # Sasha
    76561198323443242, # Xav
    76561198197931509  # Tom
]

# If true will not notify users, will only update csv
# Make sure to have this True when first getting data for users and no csv history exists, or the users will be notified about buying every game they own
SILENT_MODE = False 

# ===============================================
# MAIN
# ===============================================

def main():
    # Collect and update data
    user_data: SteamUserData = SteamApi.get_user_owned_apps(API_KEY, USERS)

    # Optionally ship publishing
    if SILENT_MODE:
        return
    
    # Skip if no changes
    if not sum(
        len(user.game_data.added_app_ids) + len(user.game_data.removed_app_ids)
        for user in user_data.steam_users
    ):
        print("Info: No changes!")
        return
    
    # Create app data
    WebhookPublisher.publish_update(DISCORD_WEBHOOK, API_KEY, user_data)    

if __name__ == "__main__":
    main()