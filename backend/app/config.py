from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "localdevpassword"

    redis_url: str = "redis://localhost:6379/0"

    # Model IDs shift fast — check ai.google.dev/gemini-api/docs/models for the
    # current flash-tier model before deploying; these are current as of Jul 2026.
    gemini_api_key: str = ""
    embedding_model: str = "gemini-embedding-001"
    embedding_dimensions: int = 768
    extraction_model: str = "gemini-3.6-flash"
    chat_model: str = "gemini-3.6-flash"

    turnstile_secret_key: str = ""
    admin_token: str = "changeme-local-dev-token"

    max_upload_mb: int = 20
    max_upload_pages: int = 20

    upload_rate_limit: str = "5/hour"
    chat_rate_limit: str = "20/hour"

    daily_cost_budget_usd: float = 5.0
    per_ip_daily_cost_budget_usd: float = 0.5

    cors_origins: list[str] = ["http://localhost:5173"]


settings = Settings()
