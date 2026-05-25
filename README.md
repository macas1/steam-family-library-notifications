TODO:
    Readme
        Setup instructions
    Migrate from dataclass to pydantic
    Anti spam measures? 
        Max game count in 1 day, if over, ignore
        Ignore if no previous user file existed?
    Games do not hide if hidden by the owner of the API key
    Run with multiple sets of data (webhook and users)
        We'd not want to make the same calls multiple times if the same users are for some reason in different sets.
            Lazy way would be a caching library with a small (relatively, maybe an hour) lifespan, otherwise track it ourselves