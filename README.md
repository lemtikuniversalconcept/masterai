# Lemtik Security Master AI Agent

Orchestration brain for the Lemtik Security platform.

## Endpoints

- `POST /triage`
- `POST /synthesise`
- `POST /process`
- `GET /session/{id}`
- `GET /health`

## Behavior

- Triage parses raw incident text into structured incident types and job manifests.
- Synthesis combines upstream service results into an operator-ready recommendation panel.
- Non-incident tasks are handled directly:
  - routine reports
  - OSINT alerts
  - inventory alerts
- When Groq is unavailable, the service falls back to deterministic heuristic reasoning.

## Environment

Use [`.env.example`](./.env.example) as the template.

## Data

Session state is stored in SQLite locally or PostgreSQL when `DATABASE_URL` is set.
The Postgres schema is mirrored in [`schema.sql`](./schema.sql).

## Relationship API

This service is designed to be called by the Relationship API twice per incident:

1. `POST /triage` to get the job manifest
2. `POST /synthesise` to get the recommendation panel

`POST /process` is available for one-shot orchestration when the caller already has everything in hand.

The local shim in [`relationship_client.py`](./relationship_client.py) can be used to probe or call a Relationship API instance when one is deployed.

## Deployment Files

- [`Procfile`](./Procfile)
- [`main.py`](./main.py)

## License

Proprietary — All Rights Reserved. See [LICENSE](./LICENSE). This code is
shared publicly for evaluation purposes only; it is not licensed for reuse,
modification, or redistribution.

---

© 2026 Lemtik Security. All rights reserved.
