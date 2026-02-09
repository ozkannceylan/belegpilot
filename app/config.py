"""Application configuration using pydantic-settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # App
    environment: str = "development"
    log_level: str = "INFO"
    secret_key: str = "change-me-in-production"
    allowed_origins: str = "*"
    api_key_admin_secret: str = "change-me-admin"

    # Database
    db_host: str = "db"
    db_port: int = 5432
    db_name: str = "belegpilot"
    db_user: str = "belegpilot"
    db_password: str = "devpassword"

    # OpenRouter
    openrouter_api_key: str = ""
    openrouter_default_model: str = "qwen/qwen2.5-vl-72b-instruct"
    openrouter_fallback_model: str = "openai/gpt-4o-mini"
    openrouter_monthly_budget_usd: float = 5.0
    openrouter_daily_budget_usd: float = 1.0
    openrouter_per_request_max_usd: float = 0.05

    # Observability
    phoenix_collector_endpoint: str = "http://phoenix:4317"
    otel_service_name: str = "BelegPilot"

    # File upload
    max_upload_size_mb: int = 10

    @property
    def database_url(self) -> str:
        """Async PostgreSQL connection URL."""
        return (
            f"postgresql+asyncpg://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @property
    def sync_database_url(self) -> str:
        """Sync PostgreSQL connection URL for scripts."""
        return (
            f"postgresql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )


settings = Settings()
