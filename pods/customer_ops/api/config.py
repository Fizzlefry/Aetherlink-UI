"""Clean, minimal settings used by tests.

This file intentionally keeps validations small and deterministic.
"""
from __future__ import annotations

import os
import re
from functools import lru_cache
from typing import Any, Literal, List, Optional, Dict

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


Env = Literal["dev", "staging", "prod"]
RATE_RE = re.compile(r"^\d+/(second|minute|hour|day)$", re.IGNORECASE)


def _split_csv(value: str) -> list[str]:
    return [v.strip() for v in (value or "").split(",") if v.strip()]


class Settings(BaseSettings):
    # Allow extra unrelated environment variables to be present (ignore them).
    model_config = SettingsConfigDict(env_file=(".env",), case_sensitive=False, extra="ignore")

    APP_NAME: str = "CustomerOps"
    ENV: Env = "dev"
    DEBUG: bool = False

    cors_origins: str = Field(default="*")
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_METHODS: str = Field(default="GET,POST,OPTIONS")
    CORS_HEADERS: str = Field(default="*")

    # Security
    REQUIRE_API_KEY: bool = True

    # Map of api_key -> tenant (e.g., {"ABC123": "EXPERTCO"})
    API_KEYS: Dict[str, str] = Field(default_factory=dict)

    # Optional legacy CSV support (comma-separated list)
    # e.g., API_KEYS_CSV="ABC123,XYZ789" (tenant becomes "LEGACY")
    API_KEYS_CSV: Optional[str] = None

    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    # Hosts and admin
    ALLOWED_HOSTS: str = "localhost,127.0.0.1"
    API_ADMIN_KEY: Optional[str] = None

    # PII-safe memory flags
    ENABLE_PII_REDACTION: bool = True
    # CSV of extra regex patterns (Python-style without surrounding / /)
    # e.g. r"\b\d{9}\b"  (9-digit ids)
    PII_EXTRA_PATTERNS: str = ""

    # Auto follow-up engine
    FOLLOWUP_ENABLED: bool = True
    FOLLOWUP_QUEUE: str = "followups"
    FOLLOWUP_RULE_TOP_P: float = 0.70  # pred_prob threshold
    FOLLOWUP_SCHEDULES: str = "30m,2h"  # comma list; supports m/h/d

    RATE_LIMIT_FALLBACK: str = "60/minute"
    RATE_LIMIT_FAQ: str = "10/minute"
    RATE_LIMIT_CHAT: str = "30/minute"

    # Connection strings
    REDIS_URL: str = "redis://localhost:6379/0"
    DATABASE_URL: Optional[str] = "sqlite:///./local.db"
    
    REDIS_SOCKET_TIMEOUT: float = 2.0
    REDIS_SOCKET_CONNECT_TIMEOUT: float = 2.0

    # Lifelike agent knobs
    AGENT_PERSONALITY: str = "A friendly and helpful assistant."
    RESPONSE_STYLE: Literal["concise", "detailed"] = "concise"
    UNCERTAINTY_THRESHOLD: float = 0.75
    ENABLE_PROACTIVE_FOLLOWUPS: bool = True
    ENABLE_MEMORY_SUMMARIES: bool = True
    
    # Feature flags for A/B testing and hot-disable
    ENABLE_MEMORY: bool = True
    ENABLE_ENRICHMENT: bool = True

    # --- Model provider config ---
    MODEL_PROVIDER: str = "ollama"  # "openai" | "gemini" | "ollama"
    MODEL_NAME: str = "llama3"
    OPENAI_API_KEY: Optional[str] = None
    GOOGLE_API_KEY: Optional[str] = None
    OLLAMA_BASE_URL: str = "http://localhost:11434"

    # --- RAG / Embeddings ---
    RAG_ENABLED: bool = True
    RAG_TOP_K: int = 4
    RAG_MIN_SCORE: float = 0.15  # cosine sim threshold 0..1

    EMBED_PROVIDER: str = "gemini"  # "openai" | "gemini" | "ollama"  (gemini has fallback for dev)
    EMBED_MODEL: str = "text-embedding-3-small"  # openai default; e.g., "nomic-embed-text" for ollama

    @property
    def cors_origins_list(self) -> list[str]:
        if (self.cors_origins or "").strip() == "*":
            return ["*"]
        return _split_csv(self.cors_origins)

    @property
    def cors_methods_list(self) -> list[str]:
        return _split_csv(self.CORS_METHODS)

    @property
    def cors_headers_list(self) -> list[str]:
        if (self.CORS_HEADERS or "").strip() == "*":
            return ["*"]
        return _split_csv(self.CORS_HEADERS)

    @field_validator("cors_origins")
    def _validate_origins(cls, v: str) -> str:
        if v == "*":
            return v
        for origin in _split_csv(v):
            if not origin.startswith(("http://", "https://")):
                raise ValueError(f"Invalid origin URL: {origin}")
        return v

    def model_post_init(self, __context: Any) -> None:
        if getattr(self, "ENV", "dev") in ("prod", "staging") and (self.cors_origins or "").strip() == "*":
            raise ValueError("Wildcard CORS not allowed outside dev")
        for name in ("RATE_LIMIT_FALLBACK", "RATE_LIMIT_FAQ", "RATE_LIMIT_CHAT"):
            val = getattr(self, name, "")
            if not RATE_RE.match(val):
                raise ValueError(f"Invalid rate '{val}' for {name}")

        # 1) Load per-tenant keys: any env named API_KEY_<TENANT>=<KEY>
        prefix = "API_KEY_"
        for k, v in os.environ.items():
            if k.startswith(prefix) and v:
                tenant = k[len(prefix):].strip()
                key = v.strip()
                if tenant and key:
                    self.API_KEYS[key] = tenant

        # 2) Legacy CSV fallback (no tenant names)
        if self.API_KEYS_CSV:
            for token in self.API_KEYS_CSV.split(","):
                key = token.strip()
                if key:
                    # Use generic tenant label for legacy keys
                    self.API_KEYS.setdefault(key, "LEGACY")

        # 3) Backward-compat: if someone set API_KEYS as CSV via env or .env
        # Pydantic may parse it as a string; treat like CSV above
        if isinstance(self.API_KEYS, str):
            parsed: Dict[str, str] = {}
            for token in self.API_KEYS.split(","):
                key = token.strip()
                if key:
                    parsed[key] = "LEGACY"
            # Avoid reassign lint warning by using __setattr__ directly
            object.__setattr__(self, "API_KEYS", parsed)


@lru_cache(maxsize=1)
def get_settings():
    # construct and return Settings()
    return Settings()

def reload_settings():
    get_settings.cache_clear()
    return get_settings()