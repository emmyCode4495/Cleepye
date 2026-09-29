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
    host: str = "127.0.0.1"
    port: int = 8741
    debug: bool = True

    # Security
    secret_key: str = ""
    encryption_key: str = ""

    # AI
    ai_provider: str = "local"  # local | openrouter | openai | anthropic
    openrouter_api_key: str = ""
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b"

    # Whisper
    whisper_model: str = "medium"
    whisper_device: str = "auto"
    whisper_compute_type: str = "int8"

    # Paths
    data_dir: Path = Path("./data")
    storage_dir: Path = Path("./data/storage")
    db_path: Path = Path("./data/clipmine.db")

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
