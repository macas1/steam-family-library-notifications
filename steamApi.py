import csv, os
from datetime import date
from structs import SteamUserAppData, SteamAppData, SteamUserApps, SteamUserData, SteamUser
from steam.client import SteamClient
from steam.enums import EResult
from requests import Response, get as get_request

class SteamApi:
    """Static utility class for interacting with the Steam API."""

    __API_GET_OWNED_GAMES = "https://api.steampowered.com/IPlayerService/GetOwnedGames/v0001/"
    __API_GET_APP_DETAILS = "https://store.steampowered.com/api/appdetails"
    __API_GET_USERS = "https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v0002"
    __CSV_HEADER_ID = "app_id"
    __CSV_HEADER_DATE_FIRST_SEEN = "date_first_seen"
    __CSV_HEADER_DATE_LAST_SEEN = "date_last_seen"
    __CSV_HEADER_DATE_LAST_REMOVED = "date_last_removed"
    __CLI_APP_DETAILS_CHUNK_SIZE = 100
    __REQUEST_TIMEOUT = 60

    __requests_cache = {}
    __cli_app_details_cache = {}

    steamClient = None
    
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
            new_app_data = SteamApi.__create_updated_user_csv_data(user_id, previous_games, added_ids, removed_ids)
            
            # Group relevant data from above sources
            steam_user_apps = {}
            for appid, row in new_app_data.items():
                # User data
                steam_user_apps[appid] = SteamUserAppData(
                    date_first_seen=row[SteamApi.__CSV_HEADER_DATE_FIRST_SEEN],
                    date_last_seen=row[SteamApi.__CSV_HEADER_DATE_LAST_SEEN],
                    date_last_removed=row[SteamApi.__CSV_HEADER_DATE_LAST_REMOVED],
                    playtime=current_games[appid]["playtime"] if appid in current_games else None,
                    time_last_played=current_games[appid]["time_last_played"] if appid in current_games else None
                )
                # App data
                if appid not in game_data:
                    game_data[appid] = SteamAppData(
                        icon_hash=current_games[appid]["icon_hash"] if appid in current_games else None
                    )

            # Store relevant user and user app data
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
    def update_stored_user_data(user_data: SteamUserData) -> None:
        script_dir = os.path.dirname(os.path.abspath(__file__))

        for user in user_data.steam_users:
            file_path = os.path.join(
                script_dir,
                "user_data",
                f"{user.steam_id}.csv"
            )

            with open(file_path, "w", newline="", encoding="utf-8") as f:
                # Create write and write headers
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

                # Reconstruct csv rows for this user and write them
                for appid, app_data in user.game_data.apps.items():
                    writer.writerow({
                        SteamApi.__CSV_HEADER_ID: appid,
                        SteamApi.__CSV_HEADER_DATE_FIRST_SEEN: app_data.date_first_seen,
                        SteamApi.__CSV_HEADER_DATE_LAST_SEEN: app_data.date_last_seen,
                        SteamApi.__CSV_HEADER_DATE_LAST_REMOVED: app_data.date_last_removed
                    })

    @staticmethod
    def get_app_details_cli(app_ids: list[int]) -> dict:
        # Init SteamClient
        SteamApi.__init_steam_client()

        # Get from cache
        app_ids_missing = []
        result = {}
        for app_id in app_ids:
            if app_id in SteamApi.__cli_app_details_cache:
                result[app_id] = SteamApi.__cli_app_details_cache[app_id]
            else:
                app_ids_missing.append(app_id)

        # Get from call
        if app_ids_missing:
            for i in range(0, len(app_ids_missing), SteamApi.__CLI_APP_DETAILS_CHUNK_SIZE):
                chunk = app_ids_missing[i:i + SteamApi.__CLI_APP_DETAILS_CHUNK_SIZE]
                apps_info = SteamApi.steamClient.get_product_info(apps=chunk).get("apps", {})
                for app_id, app_info in apps_info.items():
                    SteamApi.__cli_app_details_cache[app_id] = app_info
                    result[app_id] = app_info

        return result
    
    @staticmethod
    def __init_steam_client() -> None:
        if not SteamApi.steamClient:
            steamClient = SteamClient()
            result = steamClient.anonymous_login()
            if result != EResult.OK:
                raise RuntimeError(f"Steam anonymous login failed: {result}")
            SteamApi.steamClient = steamClient

    @staticmethod
    def __is_app_family_shared(app_id: int) -> bool:
        app_cli_data = SteamApi.get_app_details_cli([app_id])[app_id]
        return int(app_cli_data.get("common", {}).get("exfgls", 0)) == 0
    
    @staticmethod
    def get_app_details_web(app_id: int):
        params = {
            "appids": app_id,
        }
        response = SteamApi.__cached_get(SteamApi.__API_GET_APP_DETAILS, params=params, timeout=SteamApi.__REQUEST_TIMEOUT)
        response.raise_for_status()
        data = response.json()
        return data[str(app_id)]["data"]
    
    @staticmethod
    def get_user_info(api_key: str, user_ids: list[int]) -> list[dict]:
        params = {
            "key": api_key,
            "steamids": ",".join(map(str, user_ids)),
        }
        response = SteamApi.__cached_get(SteamApi.__API_GET_USERS, params=params, timeout=SteamApi.__REQUEST_TIMEOUT)
        response.raise_for_status()
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
            # Make api call
            params = {
                "key": api_key,
                "steamid": user_id,
                "include_appinfo": "true",
                "skip_unvetted_apps": "false",
                "format": "json"
            }
            response = SteamApi.__cached_get(
                SteamApi.__API_GET_OWNED_GAMES,
                params=params,
                timeout=SteamApi.__REQUEST_TIMEOUT
            )

            # Validate Response
            response.raise_for_status()
            response_data = response.json().get("response")
            if response_data is None:
                raise RuntimeError("Steam GetOwnedGames response is missing 'response'")

            # Store result
            games = {
                game["appid"]: {
                    "playtime": game.get("playtime_forever", 0),
                    "time_last_played": game.get("rtime_last_played", 0),
                    "icon_hash": game.get("img_icon_url"),
                }
                for game in response_data.get("games", []) or []
            }
            results.append(games)

        if not results:
            return {}

        # Get app ids shared by all API key results
        common_app_ids = set(results[0].keys())

        for games in results[1:]:
            common_app_ids &= set(games.keys())

        # Make bulk cli app details call if needed. The resulting cache will be used in __is_app_family_shared
        SteamApi.get_app_details_cli(common_app_ids)

        # Return as dict while filtering out non family shared apps
        return {
            app_id: results[0][app_id]
            for app_id in common_app_ids
            if SteamApi.__is_app_family_shared(app_id)
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
    def __create_updated_user_csv_data(user_id: int, old_csv_data: list[dict], new_ids: set, removed_ids: set) -> list[dict]:
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

        return rows