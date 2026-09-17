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
    agent_mode: str = "template"  # "template" | "ollama"
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:8b"

    # Behavioural baseline window used by the profiling engine
    baseline_window_days: int = 7

    # CORS — the Vite dev server's default origin
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]


settings = Settings()
