import csv, os
from datetime import date
from structs import SteamUserAppData, SteamAppData, SteamUserApps, SteamUserData, SteamUser
from steam.client import SteamClient
from requests import Response, get as get_request

class SteamApi:
    __API_GET_OWNED_GAMES = "https://api.steampowered.com/IPlayerService/GetOwnedGames/v0001/"
    __API_GET_APP_DETAILS = "https://store.steampowered.com/api/appdetails"
    __API_GET_USERS = "https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v0002"
    __CSV_HEADER_ID = "app_id"
    __CSV_HEADER_DATE_FIRST_SEEN = "date_first_seen"
    __CSV_HEADER_DATE_LAST_SEEN = "date_last_seen"
    __CSV_HEADER_DATE_LAST_REMOVED = "date_last_removed"

    __requests_cache = {}

    @staticmethod
    def get_user_owned_apps(api_keys: list[str], user_ids: list[int]) -> SteamUserData:
        """ Returns the users owned apps and any changes from the previous call as well as some game specific data returned by the same call """  
        game_data = {}
        user_data = []
        for user_id in user_ids:
            # Get changes between games lists
            current_games = SteamApi.__get_user_owned_games(api_keys, user_id)
            previous_games = SteamApi.__read_user_csv(user_id)

            current_ids = {game_id for game_id in current_games}
            previous_ids = {row[SteamApi.__CSV_HEADER_ID] for row in previous_games if not row[SteamApi.__CSV_HEADER_DATE_LAST_REMOVED]}

            added_ids = current_ids - previous_ids
            removed_ids = previous_ids - current_ids

            # Write updated games list and get new data
            new_app_data = SteamApi.__write_user_csv(user_id, previous_games, added_ids, removed_ids)
            
            steam_user_apps = {}
            for appid, row in new_app_data.items():
                # Write user data:
                steam_user_apps[appid] = SteamUserAppData(
                    date_first_seen=row[SteamApi.__CSV_HEADER_DATE_FIRST_SEEN],
                    date_last_seen=row[SteamApi.__CSV_HEADER_DATE_LAST_SEEN],
                    date_last_removed=row[SteamApi.__CSV_HEADER_DATE_LAST_REMOVED],
                    playtime=current_games[appid]["playtime"] if appid in current_games else None,
                    time_last_played=current_games[appid]["time_last_played"] if appid in current_games else None
                )
                # Write app data
                if appid not in game_data:
                    game_data[appid] = SteamAppData(
                        icon_hash=current_games[appid]["icon_hash"] if appid in current_games else None
                    )

            user_game_data = SteamUserApps(
                apps=steam_user_apps,
                added_app_ids=added_ids,
                removed_app_ids=removed_ids
            )
            user_data.append(
                SteamUser(
                    steam_id=user_id,
                    game_data=user_game_data
                )
            )

        return SteamUserData(
            steam_users=user_data,
            app_data=game_data
        )
    
    @staticmethod
    def get_app_details_cli(app_ids: list[int]) -> dict:
        client = SteamClient()
        client.anonymous_login()
        app_info = client.get_product_info(apps=app_ids)["apps"]
        return app_info
    
    @staticmethod
    def get_app_details_web(app_id: int):
        params = {
            "appids": app_id,
        }
        response = SteamApi.__cached_get(SteamApi.__API_GET_APP_DETAILS, params=params, timeout=10)
        response.raise_for_status() # TODO Is this lethal? also check for success false in response?
        data = response.json()
        return data[str(app_id)]["data"]
    
    @staticmethod
    def get_user_info(api_key: str, user_ids: list[int]) -> list[dict]:
        params = {
            "key": api_key,
            "steamids": ",".join(map(str, user_ids)),
        }
        response = SteamApi.__cached_get(SteamApi.__API_GET_USERS, params=params, timeout=10)
        response.raise_for_status() # TODO Is this lethal? also check for success false in response?
        data = response.json()

        # Convert to map
        user_info_map = {}
        for user in data["response"]["players"]:
            user_info_map[user["steamid"]] = user
        return user_info_map
    
    @staticmethod
    def __cached_get(url: str, params: dict | None = None, **kwargs) -> Response:
        params = params or {}
        key = (url, frozenset(params.items()))

        if key in SteamApi.__requests_cache:
            return SteamApi.__requests_cache[key]

        response = get_request(url, params=params, **kwargs)
        SteamApi.__requests_cache[key] = response
        return response

    @staticmethod
    def __get_user_owned_games(api_keys: list[str], user_id: int) -> dict:
        """ Will make a call with each api_key and only return common apps that were found """
        results = []

        for api_key in api_keys:
            params = {
                "key": api_key,
                "steamid": user_id,
                "include_appinfo": "true",
                "format": "json"
            }

            response = SteamApi.__cached_get(
                SteamApi.__API_GET_OWNED_GAMES,
                params=params,
                timeout=10
            )

            response.raise_for_status()

            data = response.json()

            games = {
                game["appid"]: {
                    "playtime": game.get("playtime_forever", 0),
                    "time_last_played": game.get("rtime_last_played", 0),
                    "icon_hash": game.get("img_icon_url"),
                }
                for game in data.get("response", {}).get("games", []) or []
            }

            results.append(games)

        if not results:
            return {}

        # Get app ids shared by all API key results
        common_app_ids = set(results[0].keys())

        for games in results[1:]:
            common_app_ids &= set(games.keys())

        # Return as dict
        return {
            appid: results[0][appid]
            for appid in common_app_ids
        }

    @staticmethod
    def __read_user_csv(user_id: int) -> list[dict]:
        """ Gets recorded data from last time the users apps were observed """
        script_dir = os.path.dirname(os.path.abspath(__file__))
        file_path = os.path.join(script_dir, "user_data", f"{user_id}.csv")
        games_data = []

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                if reader.fieldnames != [
                    SteamApi.__CSV_HEADER_ID, 
                    SteamApi.__CSV_HEADER_DATE_FIRST_SEEN, 
                    SteamApi.__CSV_HEADER_DATE_LAST_SEEN, 
                    SteamApi.__CSV_HEADER_DATE_LAST_REMOVED
                ]:
                    raise KeyError("Invalid CSV column layout")
                for row in reader:
                    games_data.append({
                        SteamApi.__CSV_HEADER_ID: int(row[SteamApi.__CSV_HEADER_ID]),
                        SteamApi.__CSV_HEADER_DATE_FIRST_SEEN: row[SteamApi.__CSV_HEADER_DATE_FIRST_SEEN],
                        SteamApi.__CSV_HEADER_DATE_LAST_SEEN: row[SteamApi.__CSV_HEADER_DATE_LAST_SEEN],
                        SteamApi.__CSV_HEADER_DATE_LAST_REMOVED: row[SteamApi.__CSV_HEADER_DATE_LAST_REMOVED]
                    })
        except FileNotFoundError:
            print(f"Info: File does not exist for user {user_id}")
        except (KeyError, ValueError, csv.Error):
            print(f"Info: File for user {user_id} is corrupted or in an invalid format")
        return games_data

    @staticmethod
    def __write_user_csv(user_id: int, old_csv_data: list[dict], new_ids: set, removed_ids: set) -> list[dict]:
        """ Writes user game data to record what has been observed. Returns new observation data. """
        today = date.today().isoformat()

        # Copy old data
        rows = {row[SteamApi.__CSV_HEADER_ID]: row.copy() for row in old_csv_data}

        # Update rows
        for appid, row in rows.items():
            if appid in removed_ids:
                row[SteamApi.__CSV_HEADER_DATE_LAST_REMOVED] = today
            elif appid in new_ids:
                row[SteamApi.__CSV_HEADER_DATE_LAST_REMOVED] = ""
                row[SteamApi.__CSV_HEADER_DATE_LAST_SEEN] = today
            else:
                row[SteamApi.__CSV_HEADER_DATE_LAST_SEEN] = today
        
        # Add new rows
        for appid in new_ids:
            if appid not in rows:
                rows[appid] = {
                    SteamApi.__CSV_HEADER_ID: appid,
                    SteamApi.__CSV_HEADER_DATE_FIRST_SEEN: today,
                    SteamApi.__CSV_HEADER_DATE_LAST_SEEN: today,
                    SteamApi.__CSV_HEADER_DATE_LAST_REMOVED: ""
                }

        # Write data
        script_dir = os.path.dirname(os.path.abspath(__file__))
        file_path = os.path.join(script_dir, "user_data", f"{user_id}.csv")
        with open(file_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    SteamApi.__CSV_HEADER_ID,
                    SteamApi.__CSV_HEADER_DATE_FIRST_SEEN,
                    SteamApi.__CSV_HEADER_DATE_LAST_SEEN,
                    SteamApi.__CSV_HEADER_DATE_LAST_REMOVED
                ]
            )

            writer.writeheader()
            writer.writerows(rows.values())

        return rows