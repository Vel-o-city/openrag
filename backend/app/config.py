from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "localdevpassword"

    redis_url: str = "redis://localhost:6379/0"

    # Model IDs shift fast — check ai.google.dev/gemini-api/docs/models for the
    # current flash-tier models before deploying; these are current as of Jul 2026.
    # Each free-tier Flash model/family has its own separate daily quota, so
    # extraction/chat calls fall back down this list on quota exhaustion or a
    # model being unavailable, rather than failing outright.
    # NOTE: gemini-2.0-flash(-lite) were deprecated and shut down June 1, 2026.
    # NOTE: the entire 2.5 generation (gemini-2.5-flash, gemini-2.5-flash-lite)
    # returns 404 "no longer available to new users" on freshly-created API
    # keys/projects — confirmed against this project's key. Only the 3.x
    # generation is reachable on a new key; don't add 2.5-series models back
    # without first confirming your specific key can actually reach them.
    gemini_api_key: str = ""
    embedding_model: str = "gemini-embedding-001"
    embedding_dimensions: int = 768
    extraction_models: list[str] = ["gemini-3.6-flash", "gemini-3.5-flash", "gemini-3.5-flash-lite"]
    chat_models: list[str] = ["gemini-3.6-flash", "gemini-3.5-flash", "gemini-3.5-flash-lite"]

    turnstile_secret_key: str = ""
    admin_token: str = "changeme-local-dev-token"

    max_upload_mb: int = 20
    max_upload_pages: int = 20

    upload_rate_limit: str = "5/hour"
    chat_rate_limit: str = "20/hour"
    flag_rate_limit: str = "10/hour"

    daily_cost_budget_usd: float = 5.0
    per_ip_daily_cost_budget_usd: float = 0.5

    # Rough Flash-tier per-token costs for budget-guard estimation only — not
    # billing-accurate, and moot while everything above runs on the free
    # tier. Verify against ai.google.dev/gemini-api/docs/pricing before
    # relying on this if the project ever moves to a paid plan.
    cost_per_1k_input_tokens_usd: float = 0.0003
    cost_per_1k_output_tokens_usd: float = 0.0025
    max_estimated_chat_output_tokens: int = 1500
    max_estimated_extraction_output_tokens: int = 800
    typical_chat_context_tokens: int = 2000  # rough upper bound on assembled retrieval context
    estimated_vision_input_tokens: int = 1500  # rough per-image cost — no raw text to measure upfront

    max_graph_nodes: int = 3000
    prune_check_interval_seconds: int = 21600  # 6 hours

    cors_origins: list[str] = ["http://localhost:5173"]


settings = Settings()
