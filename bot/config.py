from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import PostgresDsn
from typing import Optional

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    BOT_TOKEN: str
    DB_DSN: PostgresDsn
    
    # Directus settings are optional now; runtime reads справочники from PostgreSQL.
    DIRECTUS_URL: str = ""
    DIRECTUS_TOKEN: str = ""
    
    # Optional: Log level
    LOG_LEVEL: str = "INFO"

settings = Settings()
