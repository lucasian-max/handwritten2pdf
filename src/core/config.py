"""Application configuration via pydantic-settings."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="NOTES2LATEX_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM settings
    model: str = "openrouter/google/gemini-3-flash-preview"
    api_base: str | None = None  # OpenAI-compatible endpoint override
    api_key: str | None = None  # key for that endpoint
    temperature: float = 0.1
    max_tokens: int = 24576

    # Conversion mode: faithful transcription, or student-facing material
    mode: Literal["transcribe", "material"] = "transcribe"

    # Best-effort page-image hosting
    cdn_api_key: str | None = None

    # Pipeline settings
    max_retries: int = 3
    context_lines: int = 40  # lines of previous LaTeX to pass as context

    # Output settings
    output_dir: Path = Path("./output")

    # LaTeX settings
    latex_engine: str = "pdflatex"
    compile_timeout: int = 60  # seconds

    # Preprocessing
    dpi: int = 300


@lru_cache
def get_settings() -> Settings:
    """Singleton Settings instance loaded from environment."""
    return Settings()
