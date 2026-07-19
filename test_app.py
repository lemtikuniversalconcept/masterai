from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path


class MasterAITestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        os.environ["LOCAL_DATABASE_PATH"] = str(Path(self._tmp.name) / "masterai.db")
        os.environ["INTERNAL_API_KEY"] = "dev-internal-key"
        self.app_module = importlib.import_module("app")
        self.app_module = importlib.reload(self.app_module)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_health(self) -> None:
        body = self.app_module.service.health()
        self.assertEqual(body["status"], "success")
        self.assertEqual(body["service"], "masterai")
        self.assertIn("groq", body)
        self.assertIn("relationship_api", body)

    def test_triage(self) -> None:
        payload = {
            "request_type": "agent_triage",
            "request_id": "req_agent_001",
            "org_id": "org_abc123",
            "incident_raw": {
                "description": "Customer called in. Man being stabbed in the toilet. North West Wing Floor 3. Suspect still on premises. One victim down.",
                "reported_by": "Front Desk Operator",
                "location_stated": "North West Wing Floor 3",
                "building": "Eko Hotel",
                "floor": 3,
                "zone": "north_west_wing",
                "timestamp": "2026-06-17T12:00:00Z",
                "source": "operator_log",
            },
            "org_context": {
                "org_type": "hotel",
                "location_name": "Eko Hotel",
                "area": "Victoria Island",
            },
        }
        model = self.app_module.TriageRequest.model_validate(payload)
        body = self.app_module.service.triage(model)
        self.assertEqual(body["triage"]["incident_type"], "assault_with_weapon")
        self.assertIn("proximity_finder", [job["service"] for job in body["jobs_needed"]])
        self.assertIn("osint_brain", [job["service"] for job in body["jobs_needed"]])

    def test_process_synthesis(self) -> None:
        payload = {
            "request_type": "agent_process",
            "request_id": "req_agent_002",
            "org_id": "org_abc123",
            "incident": {
                "id": "INC-2024-001",
                "type": "assault_with_weapon",
                "severity": 4,
                "description": "Man being stabbed in the toilet.",
                "location": "North West Wing Floor 3, Eko Hotel",
                "triage": {
                    "incident_type": "assault_with_weapon",
                    "severity": 4,
                    "urgency": "immediate",
                    "armed_threat": True,
                    "suspect_on_premises": True,
                    "victim_count": 1,
                    "victim_status": "injured",
                    "location_confirmed": True,
                    "location_indoor": True,
                    "confidence": 91,
                    "flags": ["weapon_involved", "suspect_contained", "medical_needed"],
                },
            },
            "service_results": {
                "osint_brain": {"status": "success", "data": {"heatmap": {"area_risk_score": 72, "historical_pattern": {"typical_escape_route": "towards Ozumba Mbadiwe Avenue"}}}},
                "proximity_finder": {
                    "status": "success",
                    "data": {
                        "recommended_officers": [
                            {
                                "rank": 1,
                                "officer_id": "OFF-001",
                                "name": "Ahmed Bello",
                                "armed": True,
                                "certifications": ["armed_response", "first_aid"],
                                "eta_seconds": 81,
                                "eta_display": "1 min 21 sec",
                                "current_location_description": "Hotel Lobby",
                                "fit_score": 94,
                            }
                        ]
                    },
                },
                "inventory_check": {"status": "success", "data": {"ready": True, "first_aid_kits_available": 3, "radios_available": 8, "handcuffs_available": 5, "gaps": []}},
                "autonomous_scan": {"status": "success", "data": {"devices_found": [{"device_id": "CCTV-EKO-NW-302", "type": "cctv", "name": "CCTV North Wing Floor 3", "recommended_action": "activate_and_stream", "requires_approval": False}]}},
            },
        }
        model = self.app_module.SynthesiseRequest.model_validate(payload)
        body = self.app_module.service.synthesise(model)
        self.assertEqual(body["step"], "synthesis")
        self.assertEqual(body["panel"]["panel_type"], "incident_response")
        self.assertGreaterEqual(body["panel"]["total_actions"], 2)

    def test_low_confidence_triage(self) -> None:
        payload = {
            "request_type": "agent_triage",
            "request_id": "req_agent_003",
            "org_id": "org_abc123",
            "incident_raw": {
                "description": "Help needed maybe at the lobby.",
                "reported_by": "Operator",
                "location_stated": "",
                "building": None,
                "timestamp": "2026-06-17T12:00:00Z",
                "source": "operator_log",
            },
            "org_context": {
                "org_type": "hotel",
                "location_name": "Unknown",
                "area": "Lagos",
            },
        }
        model = self.app_module.TriageRequest.model_validate(payload)
        body = self.app_module.service.triage(model)
        self.assertTrue(body["requires_human_verification"])
        self.assertIn("low_confidence_flag", body["triage"])
        self.assertIn("partial_actions_available", body["triage"])

    def test_routine_report(self) -> None:
        payload = {
            "request_type": "routine_report",
            "request_id": "req_agent_004",
            "org_id": "org_abc123",
            "task_type": "routine_report",
            "message": "Suspect apprehended. Two individuals detained at Gate A. Police called. Awaiting collection.",
        }
        model = self.app_module.ProcessRequest.model_validate(payload)
        result = self.app_module.service.process(model)
        self.assertEqual(result["panel"]["panel_type"], "routine_report")
        self.assertEqual(result["panel"]["threat_assessment"]["level"], "low")

    def test_osint_alert(self) -> None:
        payload = {
            "request_type": "osint_alert",
            "request_id": "req_agent_005",
            "org_id": "org_abc123",
            "alert_type": "osint",
            "message": "High confidence signals of planned protest near Lekki Phase 1 in next 48 hours. Multiple social media sources. Confidence: 87%.",
        }
        model = self.app_module.ProcessRequest.model_validate(payload)
        result = self.app_module.service.process(model)
        self.assertEqual(result["panel"]["panel_type"], "osint_alert")
        self.assertEqual(result["panel"]["situation_summary"], payload["message"])

    def test_inventory_alert(self) -> None:
        payload = {
            "request_type": "inventory_alert",
            "request_id": "req_agent_006",
            "org_id": "org_abc123",
            "alert_type": "inventory",
            "message": "Critical: Only 1 of 5 vehicles fuelled. Minimum threshold: 3.",
            "payload": {"active_incidents": True},
        }
        model = self.app_module.ProcessRequest.model_validate(payload)
        result = self.app_module.service.process(model)
        self.assertEqual(result["panel"]["panel_type"], "inventory_alert")
        self.assertEqual(result["panel"]["urgency"], "high")

    def test_threat_report_requests_osint_only(self) -> None:
        payload = {
            "request_type": "agent_triage",
            "request_id": "req_agent_007",
            "org_id": "org_abc123",
            "incident_raw": {
                "description": "Threat report: planned protest near Lekki Phase 1 in next 48 hours.",
                "reported_by": "Analyst",
                "location_stated": "Lekki Phase 1",
                "building": None,
                "timestamp": "2026-06-17T12:00:00Z",
                "source": "osint_alert",
            },
            "org_context": {
                "org_type": "corporate",
                "location_name": "Lekki Phase 1",
                "area": "Lekki",
            },
        }
        model = self.app_module.TriageRequest.model_validate(payload)
        body = self.app_module.service.triage(model)
        services = [job["service"] for job in body["jobs_needed"]]
        self.assertEqual(services, ["osint_brain"])

    def test_route_calculation_requested_for_outdoor_dispatch(self) -> None:
        payload = {
            "request_type": "agent_triage",
            "request_id": "req_agent_008",
            "org_id": "org_abc123",
            "incident_raw": {
                "description": "Armed robbery at the gate. Suspect outside and fleeing.",
                "reported_by": "Operator",
                "location_stated": "Gate A",
                "building": "Warehouse 12",
                "lat": 6.5,
                "lng": 3.4,
                "timestamp": "2026-06-17T12:00:00Z",
                "source": "operator_log",
            },
            "org_context": {
                "org_type": "estate",
                "location_name": "Warehouse 12",
                "area": "Ikeja",
            },
        }
        model = self.app_module.TriageRequest.model_validate(payload)
        body = self.app_module.service.triage(model)
        services = [job["service"] for job in body["jobs_needed"]]
        self.assertIn("route_calculation", services)

    def test_agent_task_request_normalizes_to_triage(self) -> None:
        payload = {
            "request_type": "agent_task",
            "request_id": "req_agent_009",
            "org_id": "org_abc123",
            "task_type": "incident_dispatch",
            "raw_input": {
                "source": "distress_call",
                "content": "Robbery at Lekki Phase 1 Gate A",
                "caller_id": "caller-123",
                "location_confirmed": True,
                "location": {
                    "name": "Lekki Phase 1 Gate A",
                    "lat": 6.438,
                    "lng": 3.472,
                },
            },
            "available_services": ["osint_brain", "ai_analysis", "autonomous_control", "proximity_finder"],
            "constraints": {
                "autonomous_actions_require_approval": True,
                "max_response_time_seconds": 30,
                "approval_officer_id": "OFF-APPROVER-01",
            },
        }
        model = self.app_module.ProcessRequest.model_validate(payload)
        result = self.app_module.service.process(model)
        self.assertEqual(result["stage"], "triage")
        self.assertEqual(result["request_type"], "agent_task")
        self.assertIn("raw_input", result)
        self.assertIn("proximity_finder", [job["service"] for job in result["jobs_needed"]])
        self.assertEqual(result["available_services"], payload["available_services"])

    def test_analyze_incident_uses_heuristic_fallback_without_ai_keys(self) -> None:
        payload = {
            "request_id": "req_ai_001",
            "incident": {
                "description": "Suspicious person at the lobby entrance.",
                "location": "Lobby",
            },
            "context": {
                "org_type": "hotel",
                "location_name": "Eko Hotel",
            },
        }
        result = self.app_module.service.analyze_incident(payload)
        self.assertEqual(result["step"], "analysis")
        self.assertEqual(result["model_provider"], "heuristic-fallback")
        self.assertIn("analysis", result)

    def test_ai_analyze_incident_route(self) -> None:
        if getattr(self.app_module, "FastAPI", None) is None:
            self.skipTest("FastAPI is not available in this environment")
        from fastapi.testclient import TestClient

        client = TestClient(self.app_module.app)
        response = client.post(
            "/ai/analyze-incident",
            headers={"X-Internal-Key": "dev-internal-key"},
            json={
                "request_id": "req_ai_002",
                "incident": {
                    "description": "Radio report of a fire alarm at the loading bay.",
                    "location": "Loading Bay",
                },
                "context": {
                    "org_type": "warehouse",
                    "location_name": "Warehouse 12",
                },
            },
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["step"], "analysis")
        self.assertIn("model_provider", body)


if __name__ == "__main__":
    unittest.main()
