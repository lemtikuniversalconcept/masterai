from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    database_url: str | None
    local_database_path: Path
    internal_api_key: str
    relationship_api_url: str | None
    relationship_api_key: str | None
    environment: str
    host: str
    port: int
    groq_api_key: str | None
    groq_model: str
    groq_temperature: float
    groq_max_tokens_triage: int
    groq_max_tokens_synthesis: int
    agent_timeout_seconds: int
    confidence_auto_execute: int
    confidence_recommend_dispatch: int
    confidence_full_response: int
    confidence_reject: int


def load_settings(base_dir: Path | None = None) -> Settings:
    root = base_dir or Path(__file__).resolve().parent
    return Settings(
        database_url=os.getenv("DATABASE_URL", "").strip() or None,
        local_database_path=Path(os.getenv("LOCAL_DATABASE_PATH", root / "masterai.db")),
        internal_api_key=os.getenv("INTERNAL_API_KEY", "dev-internal-key").strip(),
        relationship_api_url=os.getenv("RELATIONSHIP_API_URL", "").strip() or None,
        relationship_api_key=os.getenv("RELATIONSHIP_API_KEY", "").strip() or None,
        environment=os.getenv("ENVIRONMENT", "production").strip(),
        host=os.getenv("HOST", "0.0.0.0").strip(),
        port=int(os.getenv("PORT", "8000")),
        groq_api_key=os.getenv("GROQ_API_KEY", "").strip() or None,
        groq_model=os.getenv("AGENT_MODEL", "llama-3.3-70b-versatile").strip(),
        groq_temperature=float(os.getenv("AGENT_TEMPERATURE", "0.1")),
        groq_max_tokens_triage=int(os.getenv("AGENT_MAX_TOKENS_TRIAGE", "1000")),
        groq_max_tokens_synthesis=int(os.getenv("AGENT_MAX_TOKENS_SYNTHESIS", "2500")),
        agent_timeout_seconds=int(os.getenv("AGENT_TIMEOUT_SECONDS", "30")),
        confidence_auto_execute=int(os.getenv("CONFIDENCE_AUTO_EXECUTE", "85")),
        confidence_recommend_dispatch=int(os.getenv("CONFIDENCE_RECOMMEND_DISPATCH", "70")),
        confidence_full_response=int(os.getenv("CONFIDENCE_FULL_RESPONSE", "60")),
        confidence_reject=int(os.getenv("CONFIDENCE_REJECT", "30")),
    )

