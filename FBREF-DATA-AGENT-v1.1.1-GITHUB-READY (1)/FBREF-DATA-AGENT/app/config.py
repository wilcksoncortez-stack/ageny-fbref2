from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_name: str = "FBREF DATA AGENT"
    app_env: str = "development"
    database_url: str = "sqlite:///./fbref_agent.db"
    admin_api_key: str = ""
    football_data_token: str = ""
    football_data_base_url: str = "https://api.football-data.org/v4"
    sync_interval_hours: int = 24
    request_timeout: int = 25
    stats_bomb_open_data: bool = True
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

settings = Settings()
