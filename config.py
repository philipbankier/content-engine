"""Configuration via pydantic-settings. Reads from .env or environment."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # AWS Bedrock
    aws_region: str = "us-east-1"
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_bearer_token_bedrock: str = ""
    bedrock_model_id: str = "anthropic.claude-sonnet-4-20250514-v1:0"

    # Image generation
    fal_key: str = ""

    # Video - HeyGen
    heygen_api_key: str = ""
    heygen_avatar_id_founder: str = ""
    heygen_avatar_id_professional: str = ""
    heygen_video_agent_enabled: bool = True

    # Video - Veo3
    google_api_key: str = ""

    # Publishing - upload-post.com (unified)
    upload_post_api_key: str = ""
    upload_post_user: str = "autopilot-001"

    # System
    database_url: str = "sqlite+aiosqlite:///./autopilot.db"
    log_level: str = "INFO"
    port: int = 8001

    # Demo/Production Mode
    demo_mode: bool = True  # If true, use demo data and disable live agents
    seed_on_startup: bool = True  # Auto-seed demo data when app starts (only if demo_mode=true)
    daily_cost_limit: float = 5.00  # Stop agents if daily cost exceeds this (USD)

    # Agent intervals (in seconds)
    scout_interval: int = 1800  # 30 minutes
    tracker_interval: int = 3600  # 60 minutes
    engagement_interval: int = 1800  # 30 minutes
    feedback_interval: int = 86400  # 24 hours
    reviewer_interval: int = 604800  # 7 days


settings = Settings()
