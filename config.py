"""Configuration via pydantic-settings. Reads from .env or environment."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # ===== PROVIDER SELECTION =====
    # Choose which provider to use for each capability
    llm_provider: str = "bedrock"  # bedrock | ollama | openai_compat
    image_provider: str = "fal"  # fal | comfyui | sdwebui
    video_provider: str = "heygen"  # heygen | cogvideo

    # ===== AWS BEDROCK (Cloud LLM) =====
    aws_region: str = "us-east-1"
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_bearer_token_bedrock: str = ""
    bedrock_model_id: str = "anthropic.claude-sonnet-4-20250514-v1:0"

    # ===== OLLAMA (Local LLM) =====
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:14b"  # Good for 12GB VRAM (RTX 3060)

    # ===== OPENAI-COMPATIBLE (vLLM, LM Studio, etc.) =====
    openai_compat_base_url: str = "http://localhost:8000/v1"
    openai_compat_model: str = "qwen2.5-14b"
    openai_compat_api_key: str = ""  # Optional, if server requires auth

    # ===== FAL.AI (Cloud Image) =====
    fal_key: str = ""

    # ===== COMFYUI (Local Image) =====
    comfyui_base_url: str = "http://localhost:8188"

    # ===== SD WEBUI (Local Image) =====
    sdwebui_base_url: str = "http://localhost:7860"

    # ===== HEYGEN (Cloud Video) =====
    heygen_api_key: str = ""
    heygen_avatar_id_founder: str = ""
    heygen_avatar_id_professional: str = ""
    heygen_video_agent_enabled: bool = True

    # ===== COGVIDEOX (Local Video - Experimental) =====
    cogvideo_base_url: str = "http://localhost:8000"

    # ===== VEO3 (Cloud Video) =====
    google_api_key: str = ""

    # ===== OUTPUT DIRECTORIES (for local providers) =====
    image_output_dir: str = ""  # Default: ./generated_images
    video_output_dir: str = ""  # Default: ./generated_videos

    # ===== PUBLISHING =====
    upload_post_api_key: str = ""
    upload_post_user: str = "autopilot-001"

    # ===== SYSTEM =====
    database_url: str = "sqlite+aiosqlite:///./autopilot.db"
    log_level: str = "INFO"
    port: int = 8001

    # ===== DEMO/PRODUCTION MODE =====
    demo_mode: bool = True  # If true, use demo data and disable live agents
    seed_on_startup: bool = True  # Auto-seed demo data when app starts (only if demo_mode=true)
    daily_cost_limit: float = 5.00  # Stop agents if daily cost exceeds this (USD)

    # ===== AGENT INTERVALS (seconds) =====
    scout_interval: int = 1800  # 30 minutes
    tracker_interval: int = 3600  # 60 minutes
    engagement_interval: int = 1800  # 30 minutes
    feedback_interval: int = 86400  # 24 hours
    reviewer_interval: int = 604800  # 7 days


settings = Settings()
