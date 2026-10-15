from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "waiting-room-api"
    git_sha: str = "dev"
    clinic_tz: str = "Australia/Sydney"
    cors_origins: str = ""

    # Either a full URL (used by tests / tooling) or the individual parts below.
    database_url: str | None = None
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "waitingroom"
    db_user: str = "waitingroom"
    db_password: str = ""

    @property
    def sqlalchemy_url(self) -> str | URL:
        if self.database_url:
            return self.database_url
        return URL.create(
            "postgresql+psycopg",
            username=self.db_user,
            password=self.db_password,
            host=self.db_host,
            port=self.db_port,
            database=self.db_name,
        )

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
