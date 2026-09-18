from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Wallet Service"

    postgres_user: str = "wallet"
    postgres_password: str = "wallet"
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "wallet"

    db_pool_size: int = 10
    db_max_overflow: int = 10
    db_echo: bool = False

    @property
    def database_url(self) -> str:
        return (
            "postgresql+asyncpg://"
            f"{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}"
            f"/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
