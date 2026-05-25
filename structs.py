from dataclasses import dataclass

@dataclass
class SteamUserAppData:
    date_first_seen: str    # The date this application first observed the app in the users owned games
    date_last_seen: str     # The date this application most recently observed the app in the users owned games
    date_last_removed: str  # The date this application first observed the app had been removed from the users owned games (or empty)
    playtime: int           # Minuets the user has had this application open
    time_last_played: int   # ISO time since the user has last had this application open

@dataclass
class SteamUserApps:      
    apps: dict[                 # A dict of owned and previously owned steam apps
        int,                    # The Steam Id of the app
        SteamUserAppData        # The users data relevant to the app
    ]             
    added_app_ids: set[int]     # A list of ids of the applications that are newly added
    removed_app_ids: set[int]   # A list of ids of the applications that are newly removed

@dataclass
class SteamUser:
    steam_id: str
    game_data: SteamUserApps

@dataclass
class SteamAppData:
    icon_hash: str

@dataclass
class SteamUserData:
    steam_users: list[SteamUser] # User specific data
    app_data: dict[              # App specific data for apps owned by at least one user in steam_users
        int,
        SteamAppData
    ]

@dataclass
class AppEmbeddableInfo:
    name: str 
    icon_url: str 
    banner_url: str
    store_url: str
    added_by: list[str]     
    removed_by: list[str]
    owned_by: list[str]