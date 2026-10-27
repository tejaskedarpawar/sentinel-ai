"""
Central configuration for Sentinel AI, read from environment variables
(with sane local-dev defaults). Copy .env.example to .env and adjust
if your Postgres/Redis/Ollama setup differs from the defaults below.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Postgres — structured metadata, risk scores, graph edges
    database_url: str = (
        "postgresql+psycopg://sentinel:sentinel_dev_password@localhost:5432/sentinel"
    )

    # Redis — lightweight queue between the metadata collector and the
    # event-processing / detection stage (stands in for Kafka/RabbitMQ
    # at this scale)
    redis_url: str = "redis://localhost:6379/0"
    redis_stream_key: str = "sentinel:events:raw"

    # AI Investigation Agent. "template" needs nothing extra and always
    # works; "ollama" calls a locally running Ollama server for
    # richer natural-language explanations.
    agent_mode: str = "ollama"  # "ollama" | "fallback"
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "gemma4:31b-cloud"


    # Behavioural baseline window used by the profiling engine
    baseline_window_days: int = 7

    # CORS — the Vite dev server's default origin
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # Alerts Streaming & Outbound Notifications
    alerts_channel: str = "sentinel:alerts"
    notifier_min_tier: str = "Critical"  # "Critical" | "High"
    dashboard_base_url: str = "http://localhost:5173"

    # Slack Incoming Webhook
    slack_webhook_url: str | None = None

    # Telegram Bot
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None

    # SMTP Email
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_from: str | None = None
    smtp_to: str | None = None
    smtp_tls: bool = True

    # Authentication & JWT Session Security
    secret_key: str = "sentinel_secret_key_change_in_production_2026"
    token_expire_hours: int = 72


settings = Settings()
