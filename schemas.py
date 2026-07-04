from __future__ import annotations

from datetime import datetime
from typing import Any, get_args, get_origin

try:
    from pydantic import BaseModel, Field
except Exception:  # pragma: no cover - optional dependency in local dev
    class Field:  # type: ignore[override]
        def __init__(self, default: Any = None, default_factory: Any | None = None):
            self.default = default
            self.default_factory = default_factory

    class BaseModel:  # type: ignore[override]
        def __init__(self, **data: Any) -> None:
            for name, annotation in self.__annotations__.items():
                if name in data:
                    value = data[name]
                else:
                    default = getattr(self.__class__, name, None)
                    if isinstance(default, Field) and default.default_factory is not None:
                        value = default.default_factory()
                    elif isinstance(default, Field):
                        value = default.default
                    else:
                        value = default
                converted = self._convert_value(annotation, value)
                setattr(self, name, converted)

        @classmethod
        def _convert_value(cls, annotation: Any, value: Any) -> Any:
            if value is None:
                return None
            origin = get_origin(annotation)
            if origin in {list, list[str], dict}:
                return value
            if origin is None and isinstance(annotation, type) and issubclass(annotation, BaseModel) and isinstance(value, dict):
                return annotation(**value)
            args = get_args(annotation)
            for arg in args:
                if isinstance(arg, type) and issubclass(arg, BaseModel) and isinstance(value, dict):
                    return arg(**value)
            return value

        @classmethod
        def model_validate(cls, data: Any):
            if isinstance(data, cls):
                return data
            if not isinstance(data, dict):
                raise TypeError(f"{cls.__name__} requires a mapping")
            return cls(**data)

        def model_dump(self, mode: str = "python") -> dict[str, Any]:
            result: dict[str, Any] = {}
            for name in self.__annotations__:
                value = getattr(self, name)
                if isinstance(value, BaseModel):
                    result[name] = value.model_dump(mode=mode)
                else:
                    result[name] = value
            return result


class IncidentRaw(BaseModel):
    description: str = ""
    reported_by: str = ""
    location_stated: str = ""
    building: str | None = None
    floor: int | None = None
    zone: str | None = None
    lat: float | None = None
    lng: float | None = None
    timestamp: datetime | str = ""
    source: str = "operator_log"


class OrgContext(BaseModel):
    org_type: str = ""
    location_name: str = ""
    area: str = ""


class TriageRequest(BaseModel):
    request_type: str = Field(default="agent_triage")
    request_id: str = ""
    org_id: str = ""
    incident_raw: IncidentRaw = Field(default_factory=IncidentRaw)
    org_context: OrgContext = Field(default_factory=OrgContext)


class SynthesiseIncident(BaseModel):
    id: str | None = None
    type: str | None = None
    severity: int | None = None
    description: str = ""
    location: str = ""
    triage: dict[str, Any] = Field(default_factory=dict)


class SynthesiseRequest(BaseModel):
    request_type: str = Field(default="agent_synthesise")
    request_id: str = ""
    org_id: str = ""
    incident: SynthesiseIncident = Field(default_factory=SynthesiseIncident)
    service_results: dict[str, Any] = Field(default_factory=dict)


class ProcessRequest(BaseModel):
    request_type: str = Field(default="agent_process")
    request_id: str = ""
    org_id: str = ""
    task_type: str | None = None
    alert_type: str | None = None
    message: str = ""
    raw_input: dict[str, Any] = Field(default_factory=dict)
    available_services: list[str] = Field(default_factory=list)
    constraints: dict[str, Any] = Field(default_factory=dict)
    incident_raw: IncidentRaw | None = None
    org_context: OrgContext | None = None
    incident: SynthesiseIncident | None = None
    service_results: dict[str, Any] | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class TriageResponse(BaseModel):
    request_id: str
    status: str = "success"
    step: str = "triage"
    triage: dict[str, Any]
    jobs_needed: list[dict[str, Any]]
    confidence: int
    requires_human_verification: bool


class SynthesisResponse(BaseModel):
    request_id: str
    status: str = "success"
    step: str = "synthesis"
    panel: dict[str, Any]
    tokens_used: int
    model: str
    latency_ms: int
