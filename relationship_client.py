from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib import error as urllib_error
from urllib import request as urllib_request


@dataclass(frozen=True)
class RelationshipAPISettings:
    base_url: str | None
    api_key: str | None
    timeout_seconds: float = 5.0


class RelationshipAPIClient:
    def __init__(self, settings: RelationshipAPISettings) -> None:
        self.settings = settings

    @property
    def configured(self) -> bool:
        return bool(self.settings.base_url and self.settings.api_key)

    def health(self) -> dict[str, Any]:
        if not self.configured:
            return {"configured": False, "reachable": False}
        try:
            req = urllib_request.Request(
                f"{self.settings.base_url.rstrip('/')}/health",
                headers={"X-Internal-Key": self.settings.api_key or ""},
                method="GET",
            )
            with urllib_request.urlopen(req, timeout=self.settings.timeout_seconds) as response:
                body = response.read().decode("utf-8")
            return {"configured": True, "reachable": True, "response": json.loads(body) if body else None}
        except Exception as exc:
            return {"configured": True, "reachable": False, "error": str(exc)}

    def post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.configured:
            raise RuntimeError("relationship api is not configured")
        req = urllib_request.Request(
            f"{self.settings.base_url.rstrip('/')}/{path.lstrip('/')}",
            data=json.dumps(payload, ensure_ascii=True, default=str).encode("utf-8"),
            headers={
                "X-Internal-Key": self.settings.api_key or "",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib_request.urlopen(req, timeout=self.settings.timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8") or "{}")
        except urllib_error.HTTPError as exc:
            error_body = exc.read().decode("utf-8") if exc.fp else ""
            return {"status": "error", "message": error_body or str(exc), "code": exc.code}

    def submit_triage(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.post("/triage", payload)

    def submit_synthesis(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.post("/synthesise", payload)

    def submit_process(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.post("/process", payload)

