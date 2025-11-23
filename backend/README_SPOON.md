# Parallel-AI Backend — Official Spoon OS Mode

This repo can run in two modes:

1) **Local Orchestrator (Windows-friendly)** — `spoon_os.py`
2) **Official Spoon OS Graph (Linux container)** — `spoon_official.py` using `spoon_ai.graph.StateGraph`

## Run Official Spoon OS with Docker

```bash
cd backend
# Ensure backend/.env contains your rotated keys
docker compose up --build
```

The server will be at http://localhost:8000

## Switching main.py between modes

Set an env var:

- `SPOON_IMPL=official` → use `spoon_official.build_team_graph()`
- anything else (default) → use local orchestrator functions in `spoon_os.py`

## Endpoints

- `POST /rooms` → create a room
- `GET /rooms/{id}` → fetch state
- `POST /rooms/{id}/ask` → { mode: "teammate" | "team", target_agent?: "yug"|"sean"|"severin"|"nayab" }
- `GET /rooms/{id}/memory`
- `POST /rooms/{id}/memory/query`
