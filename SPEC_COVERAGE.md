# Master AI Spec Coverage

This folder now contains the implementation and support artifacts for the Master AI spec.

## Covered Areas

- Architecture and orchestration flow: `app.py`, `service.py`
- Groq model integration and fallback path: `service.py`
- Relationship API shim and health probing: `relationship_client.py`, `service.py`
- Triage contract: `schemas.py`, `service.py`
- Synthesis contract: `schemas.py`, `service.py`
- Relationship API compatibility routes and agent-task normalization: `app.py`, `service.py`, `schemas.py`
- Non-incident task handling: `service.py`
- Session persistence and schema: `storage.py`, `schema.sql`
- API endpoints: `app.py`
- Environment variables: `.env.example`, `config.py`
- Deployment config: `render.yaml`
- Procfile and module entrypoint: `Procfile`, `main.py`
- Local verification: `test_app.py`
- Operator-facing summary: `README.md`

## Notes

- The service prefers the Groq SDK when installed.
- It falls back to the standard library HTTP client and heuristic reasoning when dependencies or API access are unavailable.
