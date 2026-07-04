# Lemtik Security — Master AI Agent Specification
### Service 5 of 6 — The Orchestration Brain
**Classification:** Internal Engineering
**Version:** 1.0
**Status:** Build-Ready

---

## 1. What This Service Is

The Master AI Agent is the intelligence layer that sits above
all other services. It is the only service in the platform
that thinks rather than just executes.

Every other service does one specific job:
- OSINT Brain collects and classifies intelligence
- Inventory Service tracks resources
- Route Calculator finds fastest paths
- Proximity Finder identifies closest responders
- Autonomous Control executes hardware commands

The Master Agent does none of those things directly.
It reads a raw incident, understands what it means,
decides what data is needed to respond to it,
assembles that data from the other services,
and structures it into a recommendation a human
commander can act on in seconds.

It does five things:

1. **Understands** raw incident input and extracts
   structured meaning from unstructured descriptions
2. **Decides** which services need to be called and
   what to ask each one — the job manifest
3. **Orchestrates** parallel data collection through
   the Relationship API
4. **Reasons** over the combined data to produce
   a structured response recommendation
5. **Structures** the output into an actionable
   dashboard panel with one-click controls

---

## 2. Position in the Full Architecture

```
C4I Dashboard (operator logs incident)
        ↓
Relationship API receives incident
        ↓
Relationship API → Master Agent
(first call — what jobs are needed?)
        ↓
Master Agent analyses raw incident
returns job manifest:
{
  "jobs_needed": [
    "osint_query",
    "proximity_search",
    "inventory_check",
    "route_calculation"
  ],
  "job_parameters": { ... }
}
        ↓
Relationship API executes all jobs
in parallel across services
        ↓
Relationship API collects all results
sends combined data package back to Master Agent
(second call — structure the response)
        ↓
Master Agent reasons over all data
returns structured recommendation panel
        ↓
Relationship API returns panel to Dashboard
        ↓
Operator sees complete picture
approves with one click
```

The Master Agent is called twice per incident:
once to decide what data is needed,
once to reason over the data and produce output.
This two-step design keeps the agent fast and focused.

---

## 3. The AI Model

### Model: Groq API — Llama 3.3 70B

**Why Groq:**
- Inference speed: 500–800 tokens/second
  (significantly faster than OpenAI for real-time use)
- Llama 3.3 70B is genuinely excellent at structured
  reasoning and JSON output
- Free tier: 14,400 requests/day, 500,000 tokens/minute
- Nigerian context: Llama 3 handles Nigerian English,
  pidgin phrases, and local place names better than
  most people expect from a Western-trained model
- Cost at scale: approximately $0.59 per million tokens
  — essentially free at MVP stage

**Why not OpenAI GPT-4:**
- 10–20x more expensive for the same reasoning quality
- Slower inference — unacceptable for emergency response
- Data privacy concerns for sensitive security data

**Why not a trained custom model:**
- Not needed at launch — see AI model document
- Llama 3.3 70B is powerful enough for structured
  reasoning with a well-designed prompt
- Fine-tune on Lagos data at Month 12–18 when
  you have enough verified incident data

### Model Configuration

```python
import os
from groq import Groq

client = Groq(api_key=os.environ["GROQ_API_KEY"])

def call_agent(
    system_prompt: str,
    user_message: str,
    temperature: float = 0.1,
    max_tokens: int = 2000
) -> str:
    """
    Temperature 0.1 — near-deterministic output.
    Emergency response is not a creative writing task.
    We want consistent, structured, predictable responses.
    """
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ],
        temperature=temperature,
        max_tokens=max_tokens,
        response_format={"type": "json_object"}
    )
    return response.choices[0].message.content
```

---

## 4. The Two-Step Agent Design

### Step 1 — Triage Call (What do we need?)

The agent reads the raw incident and returns a job manifest.
This call is fast — the agent is not reasoning deeply yet,
just classifying and deciding.

**System prompt for triage:**

```
You are the triage intelligence for Lemtik Security,
a Nigerian urban security C4I platform. Your job is to
read a security incident report and decide what data
needs to be gathered to respond to it effectively.

You understand Lagos geography, Nigerian security threat
patterns, and urban emergency response operations.

Given an incident, return a JSON object specifying:
1. What type of incident this is
2. How urgent it is (1-5)
3. Which services need to be called
4. What parameters to pass to each service
5. Whether autonomous infrastructure actions
   should be pre-scanned

Rules:
- If the incident description is vague or unclear,
  set confidence low and flag for human verification
- If no officers or vehicles are needed
  (e.g. a report with no active threat),
  do not request proximity or route calculations
- Always request OSINT for any incident severity 3+
- Never request autonomous actions for severity 1-2
- Return only valid JSON, no commentary
- If you cannot parse the incident, return an error
  object with a clear reason
```

**Input to Step 1:**

```json
{
  "incident_raw": {
    "description": "Customer called in. Man being stabbed in the toilet. North West Wing Floor 3. Suspect still on premises. One victim down.",
    "reported_by": "Front Desk Operator",
    "location_stated": "North West Wing Floor 3",
    "building": "Eko Hotel",
    "org_id": "org_abc123",
    "timestamp": "ISO8601"
  }
}
```

**Output from Step 1 — Job Manifest:**

```json
{
  "triage": {
    "incident_type": "assault_with_weapon",
    "severity": 4,
    "urgency": "immediate",
    "armed_threat": true,
    "suspect_on_premises": true,
    "victim_count": 1,
    "victim_status": "injured",
    "location_confirmed": true,
    "location_indoor": true,
    "confidence": 91,
    "flags": ["weapon_involved", "suspect_contained", "medical_needed"]
  },
  "jobs_needed": [
    {
      "service": "osint_brain",
      "priority": 1,
      "parameters": {
        "area": "Victoria Island",
        "building": "Eko Hotel",
        "radius_km": 2,
        "days_back": 30,
        "incident_context": {
          "type": "assault_with_weapon",
          "keywords": ["stabbing", "assault", "weapon", "hotel"]
        },
        "include_heatmap": true
      }
    },
    {
      "service": "proximity_finder",
      "priority": 1,
      "parameters": {
        "incident_location": {
          "name": "North West Wing Floor 3, Eko Hotel",
          "lat": 6.4281,
          "lng": 3.4219,
          "indoor": true,
          "building_id": "BLDG-EKO-HOTEL",
          "floor": 3
        },
        "requirements": {
          "officers_needed": 3,
          "armed_required": false,
          "certifications_preferred": ["first_aid", "tactical"],
          "vehicles_needed": 0
        },
        "search_radius_km": 0.5
      }
    },
    {
      "service": "inventory_check",
      "priority": 2,
      "parameters": {
        "check_type": "operational_readiness",
        "operation_requirements": {
          "officers_needed": 3,
          "armed_required": false,
          "equipment": ["first_aid_kit", "radio", "handcuffs"]
        }
      }
    },
    {
      "service": "autonomous_scan",
      "priority": 2,
      "parameters": {
        "location": {
          "building_id": "BLDG-EKO-HOTEL",
          "floor": 3,
          "zone": "north_west_wing"
        },
        "scan_types": ["cctv", "elevator", "smart_door", "smart_lock"],
        "purpose": "suspect_containment_and_officer_access"
      }
    }
  ],
  "route_calculation_deferred": true,
  "route_calculation_note": "Indoor incident — route to be calculated after officers identified by proximity finder",
  "requires_human_verification": false,
  "verification_reason": null
}
```

---

### Step 2 — Synthesis Call (What do we do?)

After the Relationship API has collected all service data,
it sends everything back to the Master Agent for synthesis.
This is the deep reasoning call.

**System prompt for synthesis:**

```
You are the command intelligence for Lemtik Security,
a Nigerian urban security C4I platform operating in Lagos.

You have received data from multiple intelligence services
about an active security incident. Your job is to synthesise
all this data into a clear, actionable recommendation panel
that a security commander can review and act on in under
10 seconds.

Your recommendation must be:
- Specific: name actual officers, vehicles, routes
- Honest: acknowledge gaps in data or low confidence items
- Prioritised: most important actions first
- Safe: always recommend human approval for high-risk actions
- Concise: commanders are under pressure, no waffle

You understand:
- Lagos traffic patterns and how they affect response time
- Nigerian security threat patterns and escalation behaviour
- How hotels, estates, and corporate security teams operate
- When to recommend armed vs unarmed response
- When to recommend autonomous infrastructure actions

Structure your output as a JSON recommendation panel.
Include confidence scores for your key recommendations.
If data from any service was unavailable or low quality,
flag it explicitly. Never invent data. Never assume
a resource is available if the inventory says otherwise.

Return only valid JSON.
```

**Input to Step 2 — Combined Data Package:**

```json
{
  "incident": {
    "id": "INC-2024-001",
    "type": "assault_with_weapon",
    "severity": 4,
    "description": "Man being stabbed in the toilet. North West Wing Floor 3. Suspect still on premises.",
    "location": "North West Wing Floor 3, Eko Hotel",
    "triage": { ... }
  },
  "service_results": {
    "osint_brain": {
      "status": "success",
      "data": {
        "intelligence_items": [
          {
            "summary": "Three armed robbery incidents reported near Victoria Island in last 30 days",
            "severity": 4,
            "confidence": 88
          }
        ],
        "heatmap": {
          "area_risk_score": 72,
          "historical_pattern": {
            "assault_frequency": "medium",
            "typical_escape_route": "towards Ozumba Mbadiwe Avenue"
          }
        }
      }
    },
    "proximity_finder": {
      "status": "success",
      "data": {
        "recommended_officers": [
          {
            "rank": 1,
            "officer_id": "OFF-001",
            "name": "Ahmed Bello",
            "armed": true,
            "certifications": ["armed_response", "first_aid"],
            "eta_seconds": 81,
            "eta_display": "1 min 21 sec",
            "current_location_description": "Hotel Lobby",
            "fit_score": 94
          },
          {
            "rank": 2,
            "officer_id": "OFF-003",
            "name": "Grace Okonkwo",
            "armed": false,
            "certifications": ["first_aid", "tactical"],
            "eta_seconds": 189,
            "eta_display": "3 min 9 sec",
            "current_location_description": "Car Park Level 2",
            "fit_score": 86
          }
        ],
        "recommended_vehicles": []
      }
    },
    "inventory_check": {
      "status": "success",
      "data": {
        "ready": true,
        "first_aid_kits_available": 3,
        "radios_available": 8,
        "handcuffs_available": 5,
        "gaps": []
      }
    },
    "autonomous_scan": {
      "status": "success",
      "data": {
        "devices_found": [
          {
            "device_id": "CCTV-EKO-NW-302",
            "type": "cctv",
            "name": "CCTV North Wing Floor 3",
            "recommended_action": "activate_and_stream",
            "requires_approval": false
          },
          {
            "device_id": "ELEV-EKO-002",
            "type": "smart_elevator",
            "name": "Elevator Block B",
            "recommended_action": "hold_at_ground_floor",
            "requires_approval": true,
            "approval_level": "supervisor"
          },
          {
            "device_id": "DOOR-EKO-NW-301",
            "type": "smart_door",
            "name": "North Wing Security Door Floor 3",
            "recommended_action": "unlock_for_officer_access",
            "requires_approval": true,
            "approval_level": "supervisor"
          }
        ]
      }
    }
  }
}
```

**Output from Step 2 — Recommendation Panel:**

```json
{
  "panel_type": "incident_response",
  "incident_id": "INC-2024-001",
  "generated_at": "ISO8601",
  "confidence": 89,

  "situation_summary": "Active assault with weapon on Floor 3 North West Wing. Suspect confirmed on premises. One victim injured. Area risk score: 72/100 — elevated. Recommend immediate response. No vehicle needed — officers in building can respond on foot faster.",

  "threat_assessment": {
    "level": "high",
    "confidence": 89,
    "armed_suspect": "unknown — treat as armed until confirmed otherwise",
    "suspect_contained": true,
    "escape_risk": "medium — elevator access and stairwell are potential escape routes",
    "escalation_risk": "low — single suspect, indoor, security response imminent",
    "historical_context": "Victoria Island area has had 3 armed incidents in 30 days. This building has no prior incidents on record."
  },

  "recommended_actions": [
    {
      "priority": 1,
      "action_type": "dispatch_officer",
      "officer_id": "OFF-001",
      "officer_name": "Ahmed Bello",
      "reason": "Closest officer, first aid certified, armed. ETA 1m 21s from Hotel Lobby.",
      "eta": "1 min 21 sec",
      "equipment_to_carry": ["radio", "first_aid_kit", "handcuffs"],
      "instructions": "Proceed immediately to North West Wing Floor 3. Approach suspect with caution — treat as armed. Victim requires first aid on arrival.",
      "ping_button": true,
      "requires_approval": false
    },
    {
      "priority": 2,
      "action_type": "dispatch_officer",
      "officer_id": "OFF-003",
      "officer_name": "Grace Okonkwo",
      "reason": "First aid and tactical certified. ETA 3m 9s. Unarmed — send as support.",
      "eta": "3 min 9 sec",
      "equipment_to_carry": ["radio", "first_aid_kit"],
      "instructions": "Follow Ahmed to Floor 3. Primary role: first aid to victim. Secondary: secure perimeter with Ahmed.",
      "ping_button": true,
      "requires_approval": false
    },
    {
      "priority": 3,
      "action_type": "autonomous_action",
      "device_id": "CCTV-EKO-NW-302",
      "device_name": "CCTV North Wing Floor 3",
      "action": "activate_and_stream",
      "reason": "Activate CCTV to get visual on suspect before officers arrive. Feed routed to dashboard.",
      "requires_approval": false,
      "auto_execute": true,
      "benefit": "Visual confirmation of suspect location and description before officers commit"
    },
    {
      "priority": 4,
      "action_type": "autonomous_action",
      "device_id": "ELEV-EKO-002",
      "device_name": "Elevator Block B",
      "action": "hold_at_ground_floor",
      "reason": "Hold elevator at ground floor so Ahmed can use it immediately. Prevents suspect using elevator to escape.",
      "requires_approval": true,
      "approval_level": "supervisor",
      "benefit": "Saves Ahmed approximately 45 seconds wait time. Cuts escape route.",
      "approve_button": true,
      "deny_button": true
    },
    {
      "priority": 5,
      "action_type": "autonomous_action",
      "device_id": "DOOR-EKO-NW-301",
      "device_name": "North Wing Security Door Floor 3",
      "action": "unlock_for_officer_access",
      "reason": "Unlock security door so Ahmed does not lose time at access point.",
      "requires_approval": true,
      "approval_level": "supervisor",
      "benefit": "Removes 15 second access delay at secured door.",
      "approve_button": true,
      "deny_button": true
    }
  ],

  "medical_alert": {
    "required": true,
    "urgency": "immediate",
    "message": "One victim with stab wound. Dispatch first aid immediately. Consider calling Lagos State Ambulance Service (LASAMBUS: 767) if injury is severe.",
    "first_aider_dispatched": "Grace Okonkwo (certified)"
  },

  "intelligence_note": {
    "message": "CCTV North Wing Floor 3 is now streaming. Review footage to get suspect description before Ahmed arrives. Share description with Ahmed via radio.",
    "cctv_streaming": true,
    "osint_alert": "Victoria Island area risk elevated (72/100). Monitor for accomplices outside the building."
  },

  "escalation_options": [
    {
      "option": "Call Nigeria Police Force",
      "contact": "199",
      "recommended_if": "Suspect is confirmed armed or resists officers"
    },
    {
      "option": "Call LASAMBUS",
      "contact": "767",
      "recommended_if": "Victim's condition is critical"
    }
  ],

  "gaps_and_warnings": [],

  "requires_human_approval_count": 2,
  "auto_executable_count": 1,
  "total_actions": 5
}
```

---

## 5. Incident Type Classification

The agent classifies every incident into a structured type
before deciding what services to call. This drives the
entire response logic.

```python
INCIDENT_TYPES = {

    # Physical threats — require proximity + route + OSINT
    "robbery_armed":          {"severity_floor": 4, "armed": True,  "vehicle_likely": True},
    "robbery_unarmed":        {"severity_floor": 3, "armed": False, "vehicle_likely": False},
    "assault_with_weapon":    {"severity_floor": 4, "armed": True,  "vehicle_likely": False},
    "assault_unarmed":        {"severity_floor": 3, "armed": False, "vehicle_likely": False},
    "kidnapping_attempt":     {"severity_floor": 5, "armed": True,  "vehicle_likely": True},
    "intrusion":              {"severity_floor": 3, "armed": False, "vehicle_likely": False},
    "suspicious_activity":    {"severity_floor": 2, "armed": False, "vehicle_likely": False},
    "civil_unrest":           {"severity_floor": 3, "armed": False, "vehicle_likely": True},
    "pursuit_vehicle":        {"severity_floor": 4, "armed": True,  "vehicle_likely": True},
    "pursuit_foot":           {"severity_floor": 4, "armed": False, "vehicle_likely": False},

    # Medical — require proximity + first aid cert filter
    "medical_emergency":      {"severity_floor": 4, "armed": False, "vehicle_likely": True},
    "fire":                   {"severity_floor": 5, "armed": False, "vehicle_likely": True},

    # Intelligence — require OSINT only, no dispatch
    "threat_report":          {"severity_floor": 2, "armed": False, "vehicle_likely": False},
    "suspicious_vehicle":     {"severity_floor": 2, "armed": False, "vehicle_likely": False},

    # Resolved — no services needed
    "suspect_apprehended":    {"severity_floor": 1, "armed": False, "vehicle_likely": False},
    "false_alarm":            {"severity_floor": 1, "armed": False, "vehicle_likely": False},
    "routine_report":         {"severity_floor": 1, "armed": False, "vehicle_likely": False},
}
```

---

## 6. Non-Incident Tasks

The Master Agent handles more than emergency incidents.
It processes any task sent to it by the Relationship API.

### 6.1 Routine Report Processing

```
Input: "Suspect apprehended. Two individuals detained at Gate A.
        Police called. Awaiting collection."

Agent response:
  - No dispatch needed
  - No services called
  - Recommended actions: log completion, notify supervisor,
    update incident status to "contained"
  - No autonomous actions
```

### 6.2 OSINT Alert Processing

When the OSINT brain sends a high-confidence threat alert,
the agent processes it:

```
Input: OSINT alert — "High confidence signals of planned
       protest near Lekki Phase 1 in next 48 hours.
       Multiple social media sources. Confidence: 87%."

Agent response:
  - No immediate dispatch
  - Recommended actions:
    1. Brief security manager on threat
    2. Recommend increased patrol in affected areas
    3. Pre-position additional officers for the period
    4. Review vehicle fuel levels now
  - Risk advisory: elevated for next 48 hours
```

### 6.3 Inventory Alert Processing

When inventory flags a critical resource shortage:

```
Input: Inventory alert — "Critical: Only 1 of 5 vehicles
       fuelled. Minimum threshold: 3."

Agent response:
  - No dispatch
  - Recommended actions:
    1. Immediate notification to fleet manager
    2. If active incidents exist in the area,
       flag as operational risk
    3. Recommend deferring non-urgent deployments
       until resolved
  - Urgency: high if active incidents, medium otherwise
```

---

## 7. Confidence & Uncertainty Handling

The agent must be honest about uncertainty.
It never fabricates confidence it does not have.

```python
CONFIDENCE_THRESHOLDS = {
    "auto_execute_autonomous": 85,
    # Below this, always require human approval
    # even for normally auto-executable actions

    "recommend_dispatch": 70,
    # Below this, flag recommendation as low confidence
    # and require commander to manually verify

    "full_response": 60,
    # Below this, return partial analysis and
    # explicitly ask human to fill the gaps

    "reject_incident": 30,
    # Below this, return error and ask operator
    # to re-describe the incident more clearly
}
```

When confidence is low:

```json
{
  "confidence": 45,
  "low_confidence_flag": true,
  "low_confidence_reason": "Incident description is vague — location not confirmed, threat type unclear",
  "recommended_action": "Ask operator to confirm: Is suspect still on premises? Is there a weapon? Exact floor and zone?",
  "partial_actions_available": [
    "Activate CCTV in reported area for visual confirmation"
  ],
  "full_response_blocked_until": "Location and threat type confirmed"
}
```

---

## 8. Input & Output Contract

### 8.1 Step 1 Input (Triage Request)

```json
{
  "request_type": "agent_triage",
  "request_id": "req_agent_001",
  "org_id": "org_abc123",
  "incident_raw": {
    "description": "string — raw incident description",
    "reported_by": "string",
    "location_stated": "string",
    "building": "string or null",
    "floor": "integer or null",
    "zone": "string or null",
    "lat": "decimal or null",
    "lng": "decimal or null",
    "timestamp": "ISO8601",
    "source": "operator_log / distress_call / sensor / osint_alert / officer_report"
  },
  "org_context": {
    "org_type": "hotel / estate / corporate / police / government",
    "location_name": "string",
    "area": "string"
  }
}
```

### 8.2 Step 1 Output (Job Manifest)

```json
{
  "request_id": "req_agent_001",
  "status": "success",
  "step": "triage",
  "triage": { ... },
  "jobs_needed": [ ... ],
  "confidence": 89,
  "requires_human_verification": false
}
```

### 8.3 Step 2 Input (Synthesis Request)

```json
{
  "request_type": "agent_synthesise",
  "request_id": "req_agent_001",
  "org_id": "org_abc123",
  "incident": { ... },
  "service_results": {
    "osint_brain": { ... },
    "proximity_finder": { ... },
    "inventory_check": { ... },
    "route_calculator": { ... },
    "autonomous_scan": { ... }
  }
}
```

### 8.4 Step 2 Output (Recommendation Panel)

```json
{
  "request_id": "req_agent_001",
  "status": "success",
  "step": "synthesis",
  "panel": { ... full recommendation panel ... },
  "tokens_used": 1840,
  "model": "llama-3.3-70b-versatile",
  "latency_ms": 1200
}
```

---

## 9. Database Schema

```sql
-- services schema

CREATE TABLE agent_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id VARCHAR(100) UNIQUE NOT NULL,
    incident_id VARCHAR(100),
    org_id UUID NOT NULL,
    step VARCHAR(50) NOT NULL,
    -- triage / synthesis / completed
    raw_input JSONB NOT NULL,
    triage_output JSONB,
    synthesis_output JSONB,
    jobs_manifest JSONB,
    service_results JSONB,
    model_used VARCHAR(100),
    tokens_used INTEGER,
    confidence INTEGER,
    latency_ms INTEGER,
    status VARCHAR(50) DEFAULT 'processing',
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE agent_decisions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES agent_sessions(id),
    incident_id VARCHAR(100),
    org_id UUID NOT NULL,
    decision_type VARCHAR(100),
    -- dispatch / autonomous_action / alert / escalation
    recommended JSONB NOT NULL,
    approved_by VARCHAR(100),
    approved_at TIMESTAMPTZ,
    executed BOOLEAN DEFAULT FALSE,
    executed_at TIMESTAMPTZ,
    outcome VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 10. API Endpoints

```
POST /triage        — Step 1: analyse incident, return job manifest
POST /synthesise    — Step 2: reason over data, return panel
POST /process       — Combined: runs both steps sequentially
                      (use when Relationship API wants one call)
GET  /session/:id   — Get full session including both step outputs
GET  /health        — Service health + Groq API connectivity
```

---

## 11. Tech Stack

```
Language:      Python 3.11+
Framework:     FastAPI
AI Model:      Groq API — Llama 3.3 70B Versatile
               (llama-3.3-70b-versatile)
Groq SDK:      groq Python library
Validation:    Pydantic (input/output schema validation)
Database:      Supabase PostgreSQL (services schema)
HTTP Client:   httpx (async)
Hosting:       Render web service
Cost:          $7/month hosting + ~$0 Groq (free tier)

Groq free tier: 14,400 requests/day
                500,000 tokens/minute
                Sufficient for MVP with hundreds of incidents/day
```

---

## 12. Environment Variables

```env
DATABASE_URL=
INTERNAL_API_KEY=
RELATIONSHIP_API_URL=
RELATIONSHIP_API_KEY=

# Groq
GROQ_API_KEY=

# Agent behaviour
AGENT_MODEL=llama-3.3-70b-versatile
AGENT_TEMPERATURE=0.1
AGENT_MAX_TOKENS_TRIAGE=1000
AGENT_MAX_TOKENS_SYNTHESIS=2500
AGENT_TIMEOUT_SECONDS=30

# Confidence thresholds
CONFIDENCE_AUTO_EXECUTE=85
CONFIDENCE_RECOMMEND_DISPATCH=70
CONFIDENCE_FULL_RESPONSE=60
CONFIDENCE_REJECT=30

ENVIRONMENT=production
PORT=8000
```

---

## 13. Prompt Engineering Guidelines

The quality of the agent's output depends entirely on
the quality of the prompts. These rules must be followed
when writing or modifying any system prompt.

```
1. Always specify output format explicitly
   "Return only valid JSON with this exact structure: ..."

2. Always set temperature 0.1 for operational decisions
   Emergency response is not creative — be deterministic

3. Always include Nigerian context
   Lagos geography, Nigerian security patterns,
   local emergency numbers, pidgin awareness

4. Always define what to do when uncertain
   "If you cannot determine X, return confidence below 60
    and ask the operator to clarify"

5. Never ask the model to invent data
   "Never assume a resource is available unless the
    inventory data explicitly confirms it"

6. Always include negative constraints
   "Do not recommend autonomous actions for severity 1-2
    Do not request route calculations for indoor incidents
    until officers are identified"

7. Test every prompt change with 20+ real incident examples
   before deploying to production
```

---

## 14. Build Checklist

Before pushing to Render:

- [ ] Groq API key configured and tested
- [ ] Triage call tested with 20+ incident descriptions
      including vague, clear, indoor, outdoor, armed, unarmed
- [ ] Synthesis call tested with mock service data packages
- [ ] JSON output validated against Pydantic schemas
- [ ] Low confidence handling tested
- [ ] Confidence thresholds verified in output
- [ ] Non-incident tasks tested (report, OSINT alert, inventory)
- [ ] Session logging writing correctly
- [ ] Groq timeout handling (30 second max)
- [ ] Fallback response if Groq API is unavailable:
      return partial triage with human decision required
- [ ] Token usage within free tier limits verified
- [ ] Health endpoint returns Groq API connectivity status
- [ ] Internal API key validation working
- [ ] Response time under 3 seconds for triage call
- [ ] Response time under 5 seconds for synthesis call

---

## 15. What the Dashboard Panel Looks Like

This is what the operator sees after the Master Agent
completes synthesis. Every element is actionable.

```
┌──────────────────────────────────────────────────────────┐
│ 🔴 ACTIVE INCIDENT — INC-2024-001          Conf: 89%    │
│ Assault with Weapon · Floor 3 · Eko Hotel               │
│ Reported: 14:23:07 · 47 seconds ago                     │
├──────────────────────────────────────────────────────────┤
│ SITUATION                                                │
│ Active assault. Suspect on premises. Victim injured.    │
│ Area risk: 72/100 — elevated. No vehicle needed.        │
├──────────────────────────────────────────────────────────┤
│ DISPATCH                                                 │
│ #1 Ahmed Bello  🔫 Armed  ✅ First Aid  ETA: 1m 21s    │
│    Hotel Lobby → NW Wing Floor 3                        │
│    [PING AHMED ▶]  [SEND ROUTE ▶]  [ASSIGN ✓]          │
│                                                          │
│ #2 Grace Okonkwo  👊  ✅ First Aid  ✅ Tactical  3m 9s │
│    Car Park L2 → NW Wing Floor 3                        │
│    [PING GRACE ▶]  [SEND ROUTE ▶]  [ASSIGN ✓]          │
├──────────────────────────────────────────────────────────┤
│ ⚡ AUTONOMOUS ACTIONS                                    │
│                                                          │
│ AUTO  📷 Activate CCTV NW Wing Floor 3                  │
│       [EXECUTING...]                                     │
│                                                          │
│ 🛗 Hold Elevator B at Ground Floor                      │
│    Saves 45s · Cuts escape route                        │
│    [APPROVE ✓]  [DENY ✗]                                │
│                                                          │
│ 🚪 Unlock NW Wing Security Door Floor 3                 │
│    Removes 15s access delay                             │
│    [APPROVE ✓]  [DENY ✗]                                │
├──────────────────────────────────────────────────────────┤
│ 🏥 MEDICAL ALERT                                        │
│ Victim with stab wound. Grace carries first aid kit.    │
│ If critical: LASAMBUS 767                               │
├──────────────────────────────────────────────────────────┤
│ 📡 INTELLIGENCE                                          │
│ CCTV streaming — review for suspect description         │
│ VI area risk elevated. Watch for accomplices outside.   │
└──────────────────────────────────────────────────────────┘
```

---

*Version 1.0 — Lemtik Security Engineering*
*This service is the brain. Everything else is the body.*
*A weak prompt produces weak decisions.*
*Test the prompts as carefully as you test the code.*
*Lives depend on the quality of this service's output.*