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

    # Telegram
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""

    # Parser API
    PARSER_API_KEY: str = ""

    # Checko API
    CHECKO_API_KEY: str = ""

    # Moscow Open Data API
    MOSCOW_API_KEY: str = "a32c7b59-183e-4643-ba40-6259eeb9c8b7"

    # FTP Archive Access (demo credentials)
    FTP_HOST: str = "ftp.fedresurs.ru"
    FTP_USER: str = "demo"
    FTP_PASSWORD: str = "demo"
    FTP_DOWNLOAD_LIMIT_MB: int = 50

    # Orchestrator settings
    SCAN_INTERVAL_HOURS: int = 1  # Интервал сканирования в часах
    SLIDING_WINDOW_DAYS: int = 90  # Количество дней для скользящего окна
    SLIDING_WINDOW_STEP_DAYS: int = 7  # Шаг скользящего окна в днях
    BATCH_SIZE: int = 500  # Размер пакета для обработки

    @computed_field
    @property
    def database_url(self) -> str:
        # Используем PostgreSQL для локальной разработки и продакшена
        return f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    @property
    def base_url(self) -> str:
        return self.EFRSB_BASE_URL


settings = Settings()