import requests
from structs import AppEmbeddableInfo, SteamUserData, SteamAppData
from steamApi import SteamApi
from colorthief import ColorThief
from io import BytesIO
import requests
import colorsys

class WebhookPublisher:    
    __MAX_EMBEDS = 10

    @staticmethod
    def publish_update(webhook_url: str, steam_web_api_key: str, user_data: SteamUserData) -> None:
        display_data = WebhookPublisher.__get_info_from_users(steam_web_api_key, user_data)
        embeds = WebhookPublisher.__generate_embeds(display_data)

        # Send at most __MAX_EMBEDS per message, as discord caps this. Only add content to the first message.
        for i in range(0, len(embeds), WebhookPublisher.__MAX_EMBEDS):
            chunk_embeds = embeds[i : i + WebhookPublisher.__MAX_EMBEDS]
            payload = { "embeds": chunk_embeds }
            if i == 0: payload["content"] = WebhookPublisher.__generate_content(display_data)
            
            response = requests.post(webhook_url, json=payload)
            if response.status_code in (200, 204):
                print("Info: Webhook sent successfully.")
            else:
                print(f"Warning: Webhook failed: {response.status_code}\n{response.text}")
        
    @staticmethod
    def __get_info_from_users(steam_web_api_key: str, user_data: SteamUserData) -> list[AppEmbeddableInfo]:
        # Get apps that have been removed or added by any users
        app_data = {}
        for user in user_data.steam_users:
            user_apps = user.game_data
            for appid in user_apps.added_app_ids:
                if appid not in app_data:
                    app_data[appid] = {"added": [], "removed": [], "owned": []}
                app_data[appid]["added"].append(user.steam_id)
            for appid in user_apps.removed_app_ids:
                if appid not in app_data:
                    app_data[appid] = {"added": [], "removed": [], "owned": []}
                app_data[appid]["removed"].append(user.steam_id) 
        if not app_data:
            return {}

        # Get cli results for apps in bulk
        cli_data_results = SteamApi.get_app_details_cli([app_id for app_id in app_data])

        # If family shared exclusive, ignore
        for app_id in list(app_data.keys()):
            app_cli_data = cli_data_results[app_id]
            if int(app_cli_data["common"].get("exfgls", 0)) > 0:
                del app_data[app_id]
        if not app_data:
            return {}
        
        # Get which users already own the app
        for app_id, app in app_data.items():
            for user in user_data.steam_users:
                if user.steam_id in app["added"] or user.steam_id in app["removed"]:
                    continue

                if app_id in user.game_data.apps:
                    app_data[app_id]["owned"].append(user.steam_id) 

        # Get user info in bulk
        mentioned_users = set()
        for _, app in app_data.items():
            mentioned_users = mentioned_users | set(app["added"]) | set(app["removed"]) | set(app["owned"])
        user_info = SteamApi.get_user_info(steam_web_api_key, list(mentioned_users))

        # For each app
        output = []
        for app_id, app in app_data.items():
            # Get non-bulk user data
            app_web_data = SteamApi.get_app_details_web(app_id)

            # Add to output
            output.append(AppEmbeddableInfo(
                name=app_web_data["name"],
                icon_url=WebhookPublisher.__get_icon_url(app_id, user_data.app_data[app_id]),
                banner_url=app_web_data["header_image"],
                store_url=f"https://store.steampowered.com/app/{app_id}",
                added_by=WebhookPublisher.__user_id_list_to_names(app["added"], user_info),
                removed_by=WebhookPublisher.__user_id_list_to_names(app["removed"], user_info),
                owned_by=WebhookPublisher.__user_id_list_to_names(app["owned"], user_info)
            ))

        return output
    
    @staticmethod
    def __get_icon_url(app_id: str, app_data: SteamAppData) -> str | None:
        # Try icon hash
        if app_data.icon_hash:
            return f"http://media.steampowered.com/steamcommunity/public/images/apps/{app_id}/{app_data.icon_hash}.jpg"

        # Todo: try steam.client data

        # Return None found
        return None
    
    
    @staticmethod
    def __user_id_list_to_names(ids: list[str], user_info: dict) -> list[str]:
        output = []
        for id in ids:
            output.append(user_info[id]["personaname"])
        return output

    @staticmethod
    def __generate_content(data: list[AppEmbeddableInfo]):
        changes = len(data)
        return f"⠀\nThe Steam family library has had {changes} change{"s" if changes > 1 else ""} today!"
    
    @staticmethod
    def __generate_embeds(data: list[AppEmbeddableInfo]):
        output = []
        for app in data:
            output.append(WebhookPublisher.__generate_embed(app))
        output.sort(key=WebhookPublisher.__sort_embeds)
        return output
    
    @staticmethod
    def __sort_embeds(embed: dict):
        """ Sort by (added/removed/modified) and then alphabetical """
        
        def field_value_from_name(name):
            for field in embed["fields"]:
                if field["name"] == name:
                    return field["value"]
            return {}
        
        added = WebhookPublisher.__count_lines(field_value_from_name("Added_by"))
        removed = next((WebhookPublisher.__count_lines(value) for value in field_value_from_name("Removed_by")), 0)
        priority = (
            0 if added > removed else
            1 if removed < added else
            2
        )
        return (priority, embed["author"]["name"].lower())
    
    @staticmethod
    def __generate_embed(data: AppEmbeddableInfo):
        return {
            "description": WebhookPublisher.__generate_embed_description(data),
            "color": WebhookPublisher.__generate_embed_color(data),
            "fields": WebhookPublisher.__generate_embed_fields(data),
            "author": WebhookPublisher.__generate_embed_author(data),
            "thumbnail": WebhookPublisher.__generate_embed_thumbnail(data)
        }
    
    @staticmethod
    def __generate_embed_description(data: AppEmbeddableInfo):
        added = len(data.added_by)
        removed = len(data.removed_by)
        owned = len(data.owned_by)
        copies = owned + added - removed

        one_change = added + removed == 1
        new_game = owned == 0 and copies > 0
        gained = added > removed
        exhausted = copies <= 0
        lost = removed > added

        change_type = (
            "New addition!"         if new_game and one_change else
            "New additions!"        if new_game else

            "Another copy added!"   if gained and one_change else
            "More copies added!"    if gained else

            "Last copy removed!"    if exhausted and one_change else
            "All copies removed!"   if exhausted else

            "Copy lost!"            if lost and one_change else
            "Copies lost!"          if lost else

            "Collections updated!"
        )

        return f"{change_type} We now have {copies} {"copy" if copies == 1 else "copies"}."

    @staticmethod
    def __generate_embed_color(data: AppEmbeddableInfo) -> int:
        # Try get color from icon
        if data.icon_url:
            return WebhookPublisher.__generate_color_from_image(data.icon_url)

        # Try get color from banner
        if data.banner_url:
            return WebhookPublisher.__generate_color_from_image(data.icon_url)
        
        # Return black as default TODO: do something else?
        return 0
    
    @staticmethod
    def __generate_color_from_image(image_url: str) -> int:
        response = requests.get(image_url)
        response.raise_for_status() # TODO: Make non lethal, this app must stay alive

        # Create ColorThief object from bytes
        color_thief = ColorThief(BytesIO(response.content))

        # Get palette
        palette = color_thief.get_palette(color_count=10)

        # Get a color that is a balance of most popular and vibrant
        best_color = None
        best_score = -1
        for index, color in enumerate(palette):
            r, g, b = color
            _, s, _ = colorsys.rgb_to_hsv(r/255, g/255, b/255)
            score = s * (1 / (1 + index))
            if score > best_score:
                best_score = score
                best_color = color

        # Return in a format that discord can use
        r, g, b = best_color
        color_integer = (r << 16) + (g << 8) + b
        return color_integer

    @staticmethod
    def __generate_embed_fields(data: AppEmbeddableInfo):
        return [
            field
            for field in [
                WebhookPublisher.__generate_embed_field_added_list(data),
                WebhookPublisher.__generate_embed_field_removed_list(data),
                WebhookPublisher.__generate_embed_field_owned_list(data)
            ]
            if field is not None
        ]
    
    @staticmethod
    def __generate_embed_author(data: AppEmbeddableInfo):
        return {
            "name": data.name,
            "url": data.store_url,
            "icon_url": data.icon_url
        }
    
    @staticmethod
    def __generate_embed_thumbnail(data: AppEmbeddableInfo):
        return {
            "url": data.banner_url
        }
    
    @staticmethod
    def __generate_embed_field_added_list(data: AppEmbeddableInfo):
        if not data.added_by: return None
        return {
            "name": "Added by",
            "value": "\n".join(data.added_by),
            "inline": "true"
        }
    
    @staticmethod
    def __generate_embed_field_removed_list(data: AppEmbeddableInfo):
        if not data.removed_by: return None
        return {
            "name": "Removed by",
            "value": "\n".join(data.removed_by),
            "inline": "true"
        } 
    
    @staticmethod
    def __generate_embed_field_owned_list(data: AppEmbeddableInfo):
        if not data.owned_by: return None
        return {
            "name": "Owned by",
            "value": "\n".join(data.owned_by),
            "inline": True
        } 
    
    @staticmethod
    def __count_lines(value: str) -> int:
        if not value or not value.strip():
            return 0
        return value.strip().count("\n") + 1
        