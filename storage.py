from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

try:
    import psycopg
except Exception:  # pragma: no cover - optional dependency in local dev
    psycopg = None  # type: ignore


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"), default=str)


@dataclass
class SessionRecord:
    request_id: str
    incident_id: str | None
    org_id: str
    step: str
    raw_input: dict[str, Any]
    triage_output: dict[str, Any] | None = None
    synthesis_output: dict[str, Any] | None = None
    jobs_manifest: dict[str, Any] | None = None
    service_results: dict[str, Any] | None = None
    model_used: str | None = None
    tokens_used: int | None = None
    confidence: int | None = None
    latency_ms: int | None = None
    status: str = "processing"
    error_message: str | None = None


class MasterAIStore:
    def __init__(self, database_url: str | None, local_database_path: Path) -> None:
        self.database_url = database_url
        self.local_database_path = local_database_path
        self.use_postgres = bool(database_url and database_url.startswith(("postgres://", "postgresql://")) and psycopg is not None)
        if not self.use_postgres:
            self.local_database_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @contextmanager
    def _connect(self):
        if self.use_postgres:
            assert psycopg is not None
            conn = psycopg.connect(self.database_url)  # type: ignore[arg-type]
            try:
                yield conn
                conn.commit()
            finally:
                conn.close()
        else:
            conn = sqlite3.connect(self.local_database_path)
            conn.row_factory = sqlite3.Row
            try:
                yield conn
                conn.commit()
            finally:
                conn.close()

    def _init_schema(self) -> None:
        session_sql = """
        CREATE TABLE IF NOT EXISTS agent_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id TEXT UNIQUE NOT NULL,
            incident_id TEXT,
            org_id TEXT NOT NULL,
            step TEXT NOT NULL,
            raw_input TEXT NOT NULL,
            triage_output TEXT,
            synthesis_output TEXT,
            jobs_manifest TEXT,
            service_results TEXT,
            model_used TEXT,
            tokens_used INTEGER,
            confidence INTEGER,
            latency_ms INTEGER,
            status TEXT DEFAULT 'processing',
            error_message TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
        decision_sql = """
        CREATE TABLE IF NOT EXISTS agent_decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER,
            incident_id TEXT,
            org_id TEXT NOT NULL,
            decision_type TEXT,
            recommended TEXT NOT NULL,
            approved_by TEXT,
            approved_at TEXT,
            executed INTEGER DEFAULT 0,
            executed_at TEXT,
            outcome TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
        if self.use_postgres:
            session_sql = session_sql.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "BIGSERIAL PRIMARY KEY")
            session_sql = session_sql.replace("TEXT DEFAULT CURRENT_TIMESTAMP", "TIMESTAMPTZ DEFAULT NOW()")
            decision_sql = decision_sql.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "BIGSERIAL PRIMARY KEY")
            decision_sql = decision_sql.replace("session_id INTEGER", "session_id BIGINT")
            decision_sql = decision_sql.replace("INTEGER DEFAULT 0", "BOOLEAN DEFAULT FALSE")
            decision_sql = decision_sql.replace("TEXT DEFAULT CURRENT_TIMESTAMP", "TIMESTAMPTZ DEFAULT NOW()")
            with self._connect() as conn:
                with conn.cursor() as cur:  # type: ignore[attr-defined]
                    cur.execute(session_sql)
                    cur.execute(decision_sql)
            return
        with self._connect() as conn:
            conn.execute(session_sql)
            conn.execute(decision_sql)

    def create_session(self, record: SessionRecord) -> int:
        if self.use_postgres:
            sql = """
            INSERT INTO agent_sessions (
                request_id, incident_id, org_id, step, raw_input,
                triage_output, synthesis_output, jobs_manifest, service_results,
                model_used, tokens_used, confidence, latency_ms, status, error_message
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """
            params = (
                record.request_id,
                record.incident_id,
                record.org_id,
                record.step,
                _json(record.raw_input),
                _json(record.triage_output) if record.triage_output is not None else None,
                _json(record.synthesis_output) if record.synthesis_output is not None else None,
                _json(record.jobs_manifest) if record.jobs_manifest is not None else None,
                _json(record.service_results) if record.service_results is not None else None,
                record.model_used,
                record.tokens_used,
                record.confidence,
                record.latency_ms,
                record.status,
                record.error_message,
            )
            with self._connect() as conn:
                with conn.cursor() as cur:  # type: ignore[attr-defined]
                    cur.execute(sql, params)
                    row = cur.fetchone()
                    return int(row[0]) if row else 0

        sql = """
        INSERT INTO agent_sessions (
            request_id, incident_id, org_id, step, raw_input,
            triage_output, synthesis_output, jobs_manifest, service_results,
            model_used, tokens_used, confidence, latency_ms, status, error_message
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        with self._connect() as conn:
            cur = conn.execute(
                sql,
                (
                    record.request_id,
                    record.incident_id,
                    record.org_id,
                    record.step,
                    _json(record.raw_input),
                    _json(record.triage_output) if record.triage_output is not None else None,
                    _json(record.synthesis_output) if record.synthesis_output is not None else None,
                    _json(record.jobs_manifest) if record.jobs_manifest is not None else None,
                    _json(record.service_results) if record.service_results is not None else None,
                    record.model_used,
                    record.tokens_used,
                    record.confidence,
                    record.latency_ms,
                    record.status,
                    record.error_message,
                ),
            )
            return int(cur.lastrowid or 0)

    def update_session(self, request_id: str, **fields: Any) -> None:
        if not fields:
            return
        columns = []
        values: list[Any] = []
        for key, value in fields.items():
            columns.append(f"{key} = {'%s' if self.use_postgres else '?'}")
            if isinstance(value, (dict, list)):
                values.append(_json(value))
            else:
                values.append(value)
        values.append(request_id)
        if self.use_postgres:
            sql = f"UPDATE agent_sessions SET {', '.join(columns)}, updated_at = NOW() WHERE request_id = %s"
            with self._connect() as conn:
                with conn.cursor() as cur:  # type: ignore[attr-defined]
                    cur.execute(sql, tuple(values))
            return
        sql = f"UPDATE agent_sessions SET {', '.join(columns)}, updated_at = CURRENT_TIMESTAMP WHERE request_id = ?"
        with self._connect() as conn:
            conn.execute(sql, tuple(values))

    def fetch_session(self, request_id: str) -> dict[str, Any] | None:
        if self.use_postgres:
            sql = "SELECT * FROM agent_sessions WHERE request_id = %s"
            with self._connect() as conn:
                with conn.cursor() as cur:  # type: ignore[attr-defined]
                    cur.execute(sql, (request_id,))
                    row = cur.fetchone()
                    if row is None:
                        return None
                    columns = [desc[0] for desc in cur.description]
                    return self._row_to_dict(columns, row)
        sql = "SELECT * FROM agent_sessions WHERE request_id = ?"
        with self._connect() as conn:
            row = conn.execute(sql, (request_id,)).fetchone()
            if row is None:
                return None
            return self._row_to_dict(row.keys(), row)

    def create_decision(self, session_id: int | None, incident_id: str | None, org_id: str, decision_type: str, recommended: dict[str, Any]) -> None:
        sql_pg = """
        INSERT INTO agent_decisions (session_id, incident_id, org_id, decision_type, recommended)
        VALUES (%s, %s, %s, %s, %s)
        """
        sql_sqlite = """
        INSERT INTO agent_decisions (session_id, incident_id, org_id, decision_type, recommended)
        VALUES (?, ?, ?, ?, ?)
        """
        sql = sql_pg if self.use_postgres else sql_sqlite
        payload = (session_id, incident_id, org_id, decision_type, _json(recommended))
        if self.use_postgres:
            with self._connect() as conn:
                with conn.cursor() as cur:  # type: ignore[attr-defined]
                    cur.execute(sql, payload)
            return
        with self._connect() as conn:
            conn.execute(sql, payload)

    def health(self) -> dict[str, Any]:
        return {
            "status": "success",
            "database": "postgres" if self.use_postgres else "sqlite",
            "path": str(self.local_database_path),
        }

    @staticmethod
    def _row_to_dict(columns: list[str] | Any, row: Any) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        for idx, key in enumerate(columns):
            value = row[idx]
            if key in {"raw_input", "triage_output", "synthesis_output", "jobs_manifest", "service_results"} and isinstance(value, str):
                try:
                    payload[key] = json.loads(value)
                except json.JSONDecodeError:
                    payload[key] = value
            else:
                payload[key] = value
        return payload


def create_store(database_url: str | None, local_database_path: Path) -> MasterAIStore:
    return MasterAIStore(database_url=database_url, local_database_path=local_database_path)
