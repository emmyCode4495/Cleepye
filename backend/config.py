from pathlib import Path
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Server
    host: str = "0.0.0.0"
    port: int = 8741
    debug: bool = False

    # Security
    secret_key: str = ""
    encryption_key: str = ""

    # AI
    ai_provider: str = "heuristic"  # heuristic | local | openrouter
    openrouter_api_key: str = ""
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b"

    # Whisper
    whisper_model: str = "small"
    whisper_device: str = "auto"
    whisper_compute_type: str = "int8"

    # Paths
    data_dir: Path = Path("./data")
    storage_dir: Path = Path("./data/storage")
    db_path: Path = Path("./data/clipmine.db")

    # Supabase (auth + credits)
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""
    # When false, mining works without login (local/dev mode)
    auth_required: bool = False

    # Payments (NGN) — order: Flutterwave → Paystack → Korapay
    flutterwave_secret_key: str = ""
    flutterwave_public_key: str = ""
    paystack_secret_key: str = ""
    paystack_public_key: str = ""
    korapay_secret_key: str = ""
    korapay_public_key: str = ""
    payment_webhook_url: str = ""
    payment_redirect_url: str = "http://localhost:5173/pricing?paid=1"

    # Performance
    max_concurrent_jobs: int = 2

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        (self.storage_dir / "videos").mkdir(exist_ok=True)
        (self.storage_dir / "clips").mkdir(exist_ok=True)
        (self.storage_dir / "transcripts").mkdir(exist_ok=True)
        (self.storage_dir / "temp").mkdir(exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_dirs()
    return settings
