from __future__ import annotations

import atexit
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import load_settings
from schemas import ProcessRequest, SynthesiseRequest, TriageRequest
from service import create_service
from storage import create_store

try:  # Optional in stripped-down local environments.
    from fastapi import Depends, FastAPI, Header, HTTPException, Request
    from fastapi.responses import JSONResponse
except Exception:  # pragma: no cover - optional dependency
    FastAPI = None  # type: ignore
    Depends = None  # type: ignore
    Header = None  # type: ignore
    HTTPException = None  # type: ignore
    Request = None  # type: ignore
    JSONResponse = None  # type: ignore


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_response(status: int, payload: dict[str, Any]) -> tuple[int, list[tuple[str, str]], bytes]:
    body = json.dumps(payload, separators=(",", ":"), ensure_ascii=True, default=str).encode("utf-8")
    return status, [("content-type", "application/json"), ("content-length", str(len(body))), ("access-control-allow-origin", "*")], body


settings = load_settings(Path(__file__).resolve().parent)
store = create_store(settings.database_url, settings.local_database_path)
atexit.register(store.close)
service = create_service(settings, store)


def _check_internal_key(x_internal_key: str | None) -> None:
    if x_internal_key != settings.internal_api_key:
        raise PermissionError("invalid internal api key")


class MasterAIASGIApp:
    def __init__(self) -> None:
        self.settings = settings
        self.service = service

    async def _receive_body(self, receive) -> bytes:
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] != "http.request":
                continue
            body.extend(message.get("body", b""))
            if not message.get("more_body", False):
                break
        return bytes(body)

    def _headers(self, scope: dict[str, Any]) -> dict[str, str]:
        headers: dict[str, str] = {}
        for key, value in scope.get("headers", []):
            headers[key.decode("latin1").lower()] = value.decode("latin1")
        return headers

    async def handle(self, method: str, path: str, headers: dict[str, str], body: bytes) -> tuple[int, list[tuple[str, str]], bytes]:
        normalized_path = path.rstrip("/") or "/"
        if normalized_path.startswith("/api/v1"):
            normalized_path = normalized_path[len("/api/v1") :] or "/"
        try:
            if method == "GET" and normalized_path == "/health":
                return _json_response(200, self.service.health())
            if method == "GET" and normalized_path == "/ready":
                return _json_response(200, self.service.health())
            if method == "GET" and normalized_path.startswith("/health/"):
                return _json_response(200, self.service.health())
            if method == "GET" and normalized_path == "/":
                return _json_response(200, {"status": "ok", "service": "masterai", "endpoints": ["/health", "/triage", "/synthesise", "/process", "/session/{id}", "/ai/analyze-incident", "/ai/analyze-image", "/ai/process-radio", "/ai/parse-report", "/ai/recommend-response", "/ai/correlate-events", "/ai/generate-summary", "/ai/query", "/ai/converse", "/ai/device-recommendations"]})

            if method == "POST" and normalized_path in {"/triage", "/synthesise", "/process"}:
                _check_internal_key(headers.get("x-internal-key"))
                payload = json.loads(body.decode("utf-8") or "{}")
                if normalized_path == "/triage":
                    model = TriageRequest.model_validate(payload)
                    result = self.service.triage(model)
                    session_id = self.service.persist_triage(model.request_id, model.org_id, None, payload, result)
                    self.service.store.update_session(model.request_id, status="completed", step="triage", confidence=result.get("confidence"))
                    result["session_id"] = session_id
                    return _json_response(200, result)
                if normalized_path == "/synthesise":
                    model = SynthesiseRequest.model_validate(payload)
                    result = self.service.synthesise(model)
                    session_id = self.service.persist_synthesis(model.request_id, model.org_id, model.incident.id, payload, model.incident.triage, result, model.service_results)
                    self.service.store.update_session(
                        model.request_id,
                        status="completed",
                        step="synthesis",
                        model_used=result.get("model"),
                        tokens_used=result.get("tokens_used"),
                        confidence=result.get("panel", {}).get("confidence"),
                        latency_ms=result.get("latency_ms"),
                    )
                    result["session_id"] = session_id
                    return _json_response(200, result)
                model = ProcessRequest.model_validate(payload)
                result = self.service.process(model)
                if result.get("step") == "triage":
                    session_id = self.service.persist_triage(model.request_id, model.org_id, None, payload, result)
                    self.service.store.update_session(model.request_id, status="completed", step="triage", confidence=result.get("confidence"))
                    result["session_id"] = session_id
                    return _json_response(200, result)
                if not model.incident or model.service_results is None:
                    return _json_response(400, {"status": "error", "message": "process synthesis requires incident and service_results"})
                session_id = self.service.persist_synthesis(model.request_id, model.org_id, model.incident.id, payload, model.incident.triage, result, model.service_results)
                self.service.store.update_session(
                    model.request_id,
                    status="completed",
                    step="synthesis",
                    model_used=result.get("model"),
                    tokens_used=result.get("tokens_used"),
                    confidence=result.get("panel", {}).get("confidence"),
                    latency_ms=result.get("latency_ms"),
                )
                result["session_id"] = session_id
                return _json_response(200, result)

            if method == "POST" and normalized_path in {
                "/ai/analyze-incident",
                "/ai/analyze-image",
                "/ai/process-radio",
                "/ai/parse-report",
                "/ai/recommend-response",
                "/ai/correlate-events",
                "/ai/generate-summary",
                "/ai/query",
                "/ai/converse",
                "/ai/device-recommendations",
            }:
                _check_internal_key(headers.get("x-internal-key"))
                payload = json.loads(body.decode("utf-8") or "{}")
                handlers = {
                    "/ai/analyze-incident": self.service.analyze_incident,
                    "/ai/analyze-image": self.service.analyze_image,
                    "/ai/process-radio": self.service.process_radio,
                    "/ai/parse-report": self.service.parse_report,
                    "/ai/recommend-response": self.service.recommend_response,
                    "/ai/correlate-events": self.service.correlate_events,
                    "/ai/generate-summary": self.service.generate_summary,
                    "/ai/query": self.service.query,
                    "/ai/converse": self.service.converse,
                    "/ai/device-recommendations": self.service.device_recommendations,
                }
                return _json_response(200, handlers[normalized_path](payload))

            if method == "GET" and normalized_path.startswith("/session/"):
                _check_internal_key(headers.get("x-internal-key"))
                request_id = normalized_path.rsplit("/", 1)[-1]
                record = self.service.fetch_session(request_id)
                if not record:
                    return _json_response(404, {"detail": "session not found"})
                return _json_response(200, {"status": "success", "request_id": request_id, "session": record})

            if method == "GET" and normalized_path.startswith("/agent/jobs/"):
                _check_internal_key(headers.get("x-internal-key"))
                request_id = normalized_path.rsplit("/", 1)[-1]
                jobs = self.service.fetch_jobs(request_id)
                if not jobs:
                    return _json_response(404, {"detail": "jobs not found"})
                return _json_response(200, {"status": "success", "request_id": request_id, "jobs": jobs})

            if method == "POST" and normalized_path.startswith("/agent/approve/"):
                _check_internal_key(headers.get("x-internal-key"))
                request_id = normalized_path.rsplit("/", 1)[-1]
                payload = json.loads(body.decode("utf-8") or "{}")
                result = self.service.approve_jobs(
                    request_id,
                    approved_by=payload.get("approved_by"),
                    approval_role=payload.get("approval_level"),
                    note=payload.get("note"),
                )
                if not result:
                    return _json_response(404, {"detail": "session not found"})
                return _json_response(200, result)

            return _json_response(404, {"status": "error", "message": "endpoint not found"})
        except PermissionError as exc:
            return _json_response(401, {"status": "error", "message": str(exc)})
        except json.JSONDecodeError:
            return _json_response(400, {"status": "error", "message": "invalid JSON body"})
        except ValueError as exc:
            return _json_response(400, {"status": "error", "message": str(exc)})
        except Exception as exc:
            return _json_response(500, {"status": "error", "message": f"internal server error: {exc}"})

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await send({"type": "http.response.start", "status": 500, "headers": [(b"content-type", b"text/plain")]})
            await send({"type": "http.response.body", "body": b"Unsupported scope"})
            return
        body = await self._receive_body(receive)
        status, headers, response_body = await self.handle(scope["method"].upper(), scope["path"], self._headers(scope), body)
        await send({"type": "http.response.start", "status": status, "headers": [(key.encode("latin1"), value.encode("latin1")) for key, value in headers]})
        await send({"type": "http.response.body", "body": response_body})


fallback_app = MasterAIASGIApp()


if FastAPI is not None:
    app = FastAPI(title="Lemtik Security Master AI Agent", version="1.0.0")

    def require_internal_key(x_internal_key: str | None = Header(default=None, alias="X-Internal-Key")) -> None:  # type: ignore[valid-type]
        if x_internal_key != settings.internal_api_key:
            raise HTTPException(status_code=401, detail="invalid internal api key")

    @app.get("/health")
    @app.get("/ready")
    @app.get("/api/v1/health")
    @app.get("/api/v1/ready")
    @app.get("/health/{service_name}")
    @app.get("/api/v1/health/{service_name}")
    async def health(service_name: str | None = None) -> JSONResponse:  # type: ignore[valid-type]
        return JSONResponse(service.health())

    @app.get("/")
    async def root() -> JSONResponse:  # type: ignore[valid-type]
        return JSONResponse({"status": "ok", "service": "masterai", "endpoints": ["/health", "/triage", "/synthesise", "/process", "/session/{id}", "/ai/analyze-incident", "/ai/analyze-image", "/ai/process-radio", "/ai/parse-report", "/ai/recommend-response", "/ai/correlate-events", "/ai/generate-summary", "/ai/query", "/ai/converse", "/ai/device-recommendations"]})

    @app.post("/triage")
    @app.post("/api/v1/triage")
    async def triage(request: Request, _: None = Depends(require_internal_key)) -> JSONResponse:  # type: ignore[valid-type]
        payload = await request.json()
        model = TriageRequest.model_validate(payload)
        result = service.triage(model)
        session_id = service.persist_triage(model.request_id, model.org_id, None, payload, result)
        service.store.update_session(model.request_id, status="completed", step="triage", confidence=result.get("confidence"))
        result["session_id"] = session_id
        return JSONResponse(result)

    @app.post("/synthesise")
    @app.post("/api/v1/synthesise")
    async def synthesise(request: Request, _: None = Depends(require_internal_key)) -> JSONResponse:  # type: ignore[valid-type]
        payload = await request.json()
        model = SynthesiseRequest.model_validate(payload)
        result = service.synthesise(model)
        session_id = service.persist_synthesis(model.request_id, model.org_id, model.incident.id, payload, model.incident.triage, result, model.service_results)
        service.store.update_session(
            model.request_id,
            status="completed",
            step="synthesis",
            model_used=result.get("model"),
            tokens_used=result.get("tokens_used"),
            confidence=result.get("panel", {}).get("confidence"),
            latency_ms=result.get("latency_ms"),
        )
        result["session_id"] = session_id
        return JSONResponse(result)

    @app.post("/process")
    @app.post("/api/v1/process")
    @app.post("/agent/process")
    @app.post("/api/v1/agent/process")
    async def process(request: Request, _: None = Depends(require_internal_key)) -> JSONResponse:  # type: ignore[valid-type]
        payload = await request.json()
        model = ProcessRequest.model_validate(payload)
        result = service.process(model)
        if result.get("step") == "triage":
            session_id = service.persist_triage(model.request_id, model.org_id, None, payload, result)
            service.store.update_session(model.request_id, status="completed", step="triage", confidence=result.get("confidence"))
            result["session_id"] = session_id
            return JSONResponse(result)
        if not model.incident or model.service_results is None:
            raise HTTPException(status_code=400, detail="process synthesis requires incident and service_results")
        session_id = service.persist_synthesis(model.request_id, model.org_id, model.incident.id, payload, model.incident.triage, result, model.service_results)
        service.store.update_session(
            model.request_id,
            status="completed",
            step="synthesis",
            model_used=result.get("model"),
            tokens_used=result.get("tokens_used"),
            confidence=result.get("panel", {}).get("confidence"),
            latency_ms=result.get("latency_ms"),
        )
        result["session_id"] = session_id
        return JSONResponse(result)

    @app.get("/ai")
    @app.get("/api/v1/ai")
    async def ai_root() -> JSONResponse:  # type: ignore[valid-type]
        return JSONResponse(
            {
                "status": "success",
                "service": "masterai",
                "endpoints": [
                    "/ai/analyze-incident",
                    "/ai/analyze-image",
                    "/ai/process-radio",
                    "/ai/parse-report",
                    "/ai/recommend-response",
                    "/ai/correlate-events",
                    "/ai/generate-summary",
                    "/ai/query",
                    "/ai/converse",
                    "/ai/device-recommendations",
                ],
            }
        )

    @app.post("/ai/analyze-incident")
    @app.post("/api/v1/ai/analyze-incident")
    async def ai_analyze_incident(request: Request, _: None = Depends(require_internal_key)) -> JSONResponse:  # type: ignore[valid-type]
        payload = await request.json()
        return JSONResponse(service.analyze_incident(payload))

    @app.post("/ai/analyze-image")
    @app.post("/api/v1/ai/analyze-image")
    async def ai_analyze_image(request: Request, _: None = Depends(require_internal_key)) -> JSONResponse:  # type: ignore[valid-type]
        payload = await request.json()
        return JSONResponse(service.analyze_image(payload))

    @app.post("/ai/process-radio")
    @app.post("/api/v1/ai/process-radio")
    async def ai_process_radio(request: Request, _: None = Depends(require_internal_key)) -> JSONResponse:  # type: ignore[valid-type]
        payload = await request.json()
        return JSONResponse(service.process_radio(payload))

    @app.post("/ai/parse-report")
    @app.post("/api/v1/ai/parse-report")
    async def ai_parse_report(request: Request, _: None = Depends(require_internal_key)) -> JSONResponse:  # type: ignore[valid-type]
        payload = await request.json()
        return JSONResponse(service.parse_report(payload))

    @app.post("/ai/recommend-response")
    @app.post("/api/v1/ai/recommend-response")
    async def ai_recommend_response(request: Request, _: None = Depends(require_internal_key)) -> JSONResponse:  # type: ignore[valid-type]
        payload = await request.json()
        return JSONResponse(service.recommend_response(payload))

    @app.post("/ai/correlate-events")
    @app.post("/api/v1/ai/correlate-events")
    async def ai_correlate_events(request: Request, _: None = Depends(require_internal_key)) -> JSONResponse:  # type: ignore[valid-type]
        payload = await request.json()
        return JSONResponse(service.correlate_events(payload))

    @app.post("/ai/generate-summary")
    @app.post("/api/v1/ai/generate-summary")
    async def ai_generate_summary(request: Request, _: None = Depends(require_internal_key)) -> JSONResponse:  # type: ignore[valid-type]
        payload = await request.json()
        return JSONResponse(service.generate_summary(payload))

    @app.post("/ai/query")
    @app.post("/api/v1/ai/query")
    async def ai_query(request: Request, _: None = Depends(require_internal_key)) -> JSONResponse:  # type: ignore[valid-type]
        payload = await request.json()
        return JSONResponse(service.query(payload))

    @app.post("/ai/converse")
    @app.post("/api/v1/ai/converse")
    async def ai_converse(request: Request, _: None = Depends(require_internal_key)) -> JSONResponse:  # type: ignore[valid-type]
        payload = await request.json()
        return JSONResponse(service.converse(payload))

    @app.post("/ai/device-recommendations")
    @app.post("/api/v1/ai/device-recommendations")
    async def ai_device_recommendations(request: Request, _: None = Depends(require_internal_key)) -> JSONResponse:  # type: ignore[valid-type]
        payload = await request.json()
        return JSONResponse(service.device_recommendations(payload))

    @app.get("/session/{request_id}")
    @app.get("/api/v1/session/{request_id}")
    async def session(request_id: str, _: None = Depends(require_internal_key)) -> JSONResponse:  # type: ignore[valid-type]
        record = service.fetch_session(request_id)
        if not record:
            raise HTTPException(status_code=404, detail="session not found")
        return JSONResponse({"status": "success", "request_id": request_id, "session": record})

    @app.get("/agent/jobs/{request_id}")
    @app.get("/api/v1/agent/jobs/{request_id}")
    async def agent_jobs(request_id: str, _: None = Depends(require_internal_key)) -> JSONResponse:  # type: ignore[valid-type]
        record = service.fetch_jobs(request_id)
        if not record:
            raise HTTPException(status_code=404, detail="jobs not found")
        return JSONResponse({"status": "success", "request_id": request_id, "jobs": record})

    @app.post("/agent/approve/{request_id}")
    @app.post("/api/v1/agent/approve/{request_id}")
    async def agent_approve(request_id: str, request: Request, _: None = Depends(require_internal_key)) -> JSONResponse:  # type: ignore[valid-type]
        payload = await request.json()
        result = service.approve_jobs(
            request_id,
            approved_by=payload.get("approved_by"),
            approval_role=payload.get("approval_level"),
            note=payload.get("note"),
        )
        if not result:
            raise HTTPException(status_code=404, detail="session not found")
        return JSONResponse(result)
else:
    app = fallback_app


if __name__ == "__main__":
    if FastAPI is not None:
        import uvicorn

        uvicorn.run(app, host=settings.host, port=settings.port, reload=False)
    else:
        import uvicorn

        uvicorn.run(app, host=settings.host, port=settings.port, reload=False)
