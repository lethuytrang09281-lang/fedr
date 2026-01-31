"""
FEDRESURS RADAR - Configuration Management
Использует Pydantic Settings для типобезопасной конфигурации
"""

from typing import List
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Централизованная конфигурация приложения"""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # ============================================================================
    # EFRSB API
    # ============================================================================
    efrsb_env: str = Field("DEMO", description="DEMO or PROD")
    
    # Demo credentials
    efrsb_demo_login: str = "demowebuser"
    efrsb_demo_password: str = "Ax!761BN"
    efrsb_demo_base_url: str = "https://bank-publications-demo.fedresurs.ru"
    
    # Production credentials
    efrsb_prod_login: str = ""
    efrsb_prod_password: str = ""
    efrsb_prod_base_url: str = "https://bank-publications-prod.fedresurs.ru"
    
    # ============================================================================
    # Rate Limiting (CRITICAL!)
    # ============================================================================
    max_reqs_per_second: int = Field(6, ge=1, le=8)
    api_page_limit: int = Field(500, ge=1, le=500)
    max_date_window_days: int = Field(31, ge=1, le=31)
    
    # ============================================================================
    # Database
    # ============================================================================
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "fedresurs_radar"
    db_user: str = "fedresurs_user"
    db_password: str = "fedresurs_secure_pass_2024"
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_timeout: int = 10
    
    @property
    def database_url(self) -> str:
        """Async PostgreSQL connection string"""
        return (
            f"postgresql+asyncpg://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )
    
    # ============================================================================
    # Redis
    # ============================================================================
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: str = ""
    
    @property
    def redis_url(self) -> str:
        """Redis connection string"""
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"
    
    # ============================================================================
    # Semantic Filters
    # ============================================================================
    classifier_codes_land: str = "0108001,0402006,0402003,0402004"
    classifier_codes_buildings: str = "0101014,0101016,0103,0101009"
    
    keywords_include: str = "многоквартирн,жилая застройка,Ж-1,Ж-2,высотная,комплексное освоение,РНС,ГПЗУ"
    keywords_exclude: str = "СНТ,ЛПХ,сельскохозяйств,садоводство,гараж,ДНП"
    
    @property
    def land_codes(self) -> List[str]:
        """Parsed land classifier codes"""
        return [c.strip() for c in self.classifier_codes_land.split(",")]
    
    @property
    def building_codes(self) -> List[str]:
        """Parsed building classifier codes"""
        return [c.strip() for c in self.classifier_codes_buildings.split(",")]
    
    @property
    def include_keywords(self) -> List[str]:
        """Parsed include keywords"""
        return [k.strip().lower() for k in self.keywords_include.split(",")]
    
    @property
    def exclude_keywords(self) -> List[str]:
        """Parsed exclude keywords"""
        return [k.strip().lower() for k in self.keywords_exclude.split(",")]
    
    # ============================================================================
    # Processing
    # ============================================================================
    poll_interval_minutes: int = 15
    worker_count: int = 4
    enable_ocr: bool = False
    
    # ============================================================================
    # Enrichment
    # ============================================================================
    rosreestr_api_key: str = ""
    enable_nalog_check: bool = False
    enable_court_check: bool = False
    enable_social_monitoring: bool = False
    telegram_bot_token: str = ""
    vk_api_key: str = ""
    
    # ============================================================================
    # Notifications
    # ============================================================================
    telegram_chat_id: str = ""
    telegram_alert_threshold: int = 50
    
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    alert_email_to: str = ""
    
    # ============================================================================
    # Logging
    # ============================================================================
    log_level: str = "INFO"
    log_format: str = "json"
    log_file: str = "logs/fedresurs_radar.log"
    
    # ============================================================================
    # Advanced
    # ============================================================================
    max_retries: int = 3
    retry_backoff_factor: int = 2
    api_timeout: int = 30
    cold_start_days_ago: int = 30
    tz: str = "Europe/Moscow"
    
    # ============================================================================
    # Dynamic Properties
    # ============================================================================
    @property
    def api_base_url(self) -> str:
        """Current API base URL based on environment"""
        if self.efrsb_env.upper() == "PROD":
            return self.efrsb_prod_base_url
        return self.efrsb_demo_base_url
    
    @property
    def api_login(self) -> str:
        """Current API login based on environment"""
        if self.efrsb_env.upper() == "PROD":
            return self.efrsb_prod_login
        return self.efrsb_demo_login
    
    @property
    def api_password(self) -> str:
        """Current API password based on environment"""
        if self.efrsb_env.upper() == "PROD":
            return self.efrsb_prod_password
        return self.efrsb_demo_password


# Singleton instance
settings = Settings()


if __name__ == "__main__":
    """Quick config check"""
    print("=== FEDRESURS RADAR Configuration ===")
    print(f"Environment: {settings.efrsb_env}")
    print(f"API URL: {settings.api_base_url}")
    print(f"Database: {settings.database_url}")
    print(f"Rate Limit: {settings.max_reqs_per_second} req/sec")
    print(f"Land Codes: {settings.land_codes}")
    print(f"Include Keywords: {settings.include_keywords[:3]}...")
