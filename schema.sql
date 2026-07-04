CREATE TABLE IF NOT EXISTS agent_sessions (
    id BIGSERIAL PRIMARY KEY,
    request_id VARCHAR(100) UNIQUE NOT NULL,
    incident_id VARCHAR(100),
    org_id VARCHAR(100) NOT NULL,
    step VARCHAR(50) NOT NULL,
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

CREATE TABLE IF NOT EXISTS agent_decisions (
    id BIGSERIAL PRIMARY KEY,
    session_id BIGINT REFERENCES agent_sessions(id),
    incident_id VARCHAR(100),
    org_id VARCHAR(100) NOT NULL,
    decision_type VARCHAR(100),
    recommended JSONB NOT NULL,
    approved_by VARCHAR(100),
    approved_at TIMESTAMPTZ,
    executed BOOLEAN DEFAULT FALSE,
    executed_at TIMESTAMPTZ,
    outcome VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

