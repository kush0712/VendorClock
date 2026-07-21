from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Literal


class Settings(BaseSettings):
    # Application
    APP_ENV: Literal["development", "staging", "production"] = "development"
    SECRET_KEY: str = "change-me-to-a-long-random-string"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    FRONTEND_URL: str = "http://localhost:3000"

    # Database — use SQLite for local dev without Docker; switch to PostgreSQL in production
    DATABASE_URL: str = "sqlite:///./vendorclock.db"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # LLM — Groq is PRIMARY (safe for real vendor data: no training on prompts)
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.3-70b-versatile"

    # LLM — Gemini is FALLBACK ONLY (⚠ free tier trains on prompts — real data must NOT go here)
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.5-flash"

    # Email (internal alerts — NEVER vendor-facing)
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_NAME: str = "VendorClock"
    ALERT_DEFAULT_RECIPIENT: str = ""

    # Slack
    SLACK_WEBHOOK_URL: str = ""

    # Statutory rates
    # ⚠ Update when RBI changes the Bank Rate (currently 6.50% as of mid-2026)
    RBI_BANK_RATE_PERCENT: float = 6.50

    # CA-Confirmation Flags — do NOT change without CA/lawyer sign-off
    # Whether GST is included in the taxable base for disallowance calc.
    # Pending CA confirmation; defaulting to False (GST excluded).
    GST_INCLUDED_IN_TAXABLE_BASE: bool = False

    # Dispute clock reset trigger — pending CA/lawyer confirmation
    DISPUTE_CLOCK_RESET_TRIGGER: Literal["objection_raised", "dispute_resolved"] = "objection_raised"

    # Dual statutory citation — both must appear on every export and label
    SECTION_CITATION_OLD: str = "Section 43B(h)"          # FY ≤ 2025-26
    SECTION_CITATION_NEW: str = "Section 37(2)(g)"         # FY ≥ 2026-27
    SECTION_CITATION_COMBINED: str = "Section 43B(h) / Section 37(2)(g), Income Tax Act 2025"

    # Upload directory (local dev)
    UPLOAD_DIR: str = "./uploads"

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
