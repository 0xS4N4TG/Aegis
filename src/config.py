"""
Application configuration — loads environment variables and provides defaults.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, Field

# Load .env from project root
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env")


class Settings(BaseModel):
    """Global application settings."""

    # ── Gemini API ──────────────────────────────────────────────
    gemini_api_key: str = Field(
        default_factory=lambda: os.getenv("GEMINI_API_KEY", ""),
    )
    gemini_model: str = Field(
        default_factory=lambda: os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
    )
    available_models: list[str] = [
        "gemini-2.5-pro",
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",
        "gemini-2.0-flash",
        "gemini-2.0-flash-lite",
        
    ]

    gemini_rpm: int = Field(
        default_factory=lambda: int(os.getenv("GEMINI_RPM", "15")),
    )
    gemini_retry_max: int = Field(
        default_factory=lambda: int(os.getenv("GEMINI_RETRY_MAX", "3")),
    )

    # ── Safety settings toggle ──────────────────────────────────

    disable_safety_filters: bool = True

    # ── Database ────────────────────────────────────────────────
    db_path: Path = Field(
        default_factory=lambda: _PROJECT_ROOT
        / os.getenv("DB_PATH", "data/results.db"),
    )

    # ── Paths ───────────────────────────────────────────────────
    project_root: Path = _PROJECT_ROOT
    templates_dir: Path = _PROJECT_ROOT / "src" / "templates" / "prompts"
    reports_dir: Path = _PROJECT_ROOT / "reports"

    # ── Scoring ─────────────────────────────────────────────────
    judge_model: str = Field(
        default_factory=lambda: os.getenv("JUDGE_MODEL", "gemini-2.0-flash"),
    )

    def validate_api_key(self) -> bool:
        """Check that an API key is configured."""
        return bool(self.gemini_api_key) and self.gemini_api_key != "your_api_key_here"


# Singleton
settings = Settings()
