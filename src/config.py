from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import PostgresDsn, computed_field
from typing import Literal


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # API Settings
    EFRSB_ENV: Literal["DEMO", "PROD"] = "DEMO"  # PROD или DEMO
    EFRSB_LOGIN: str
    EFRSB_PASSWORD: str
    EFRSB_BASE_URL: str
    MAX_REQS_PER_SECOND: int = 8

    # Database
    DB_HOST: str = "localhost"  # Для локального запуска
    DB_PORT: int = 5432
    DB_USER: str = "postgres"
    DB_PASSWORD: str = "password"
    DB_NAME: str = "fedresurs_db"

    @computed_field
    @property
    def database_url(self) -> str:
        # Используем SQLite для локальной разработки
        # Для запуска в Docker измените на PostgreSQL URL
        if self.DB_HOST == "db":
            # Конфигурация для Docker
            return f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        else:
            # Конфигурация для локальной разработки
            return "sqlite+aiosqlite:///./fedresurs.db"

    @property
    def base_url(self) -> str:
        return self.EFRSB_BASE_URL


settings = Settings()