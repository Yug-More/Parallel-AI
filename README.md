<p align="center">
  <img src="parallel-frontend/public/parallel-logo.png" alt="Parallel" width="400" />
</p>

<h3 align="center">The AI Operating System for Remote Teams</h3>

<p align="center">
  Parallel unifies AI agents, shared workspaces, task management, and real-time collaboration into a single platform — giving every team member their own AI representative.
</p>

---

## What is Parallel?

Parallel is a collaborative workspace where each team member is paired with a dedicated AI agent. These agents operate inside shared rooms, see the full conversation history, and can take actions on behalf of their human — from answering questions and managing tasks to executing workflows through third-party integrations.

### Key capabilities

- **Per-member AI agents** — Each person gets a dedicated OpenAI-powered agent with their own system prompt and context
- **Shared rooms** — Collaborative spaces where humans and agents interact together with full message history
- **Task management** — Create, assign, and track tasks directly from the workspace with automatic notifications
- **Voice agent** — Pipecat + Gemini Live voice agent with Plivo telephony, call recording, and Whisper transcription
- **Composio integrations** — Connect agents to external tools (Google Docs, Google Drive, and more) for real action execution
- **Memory system** — Agents store and retrieve long-term memories with embedding-based semantic search
- **Real-time updates** — Server-sent events for live status propagation across the workspace

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | React 19, Vite, Framer Motion, Three.js |
| **Backend** | FastAPI, SQLAlchemy 2.0, Uvicorn |
| **Database** | PostgreSQL 16 (production) / SQLite (development) |
| **AI** | OpenAI GPT-4.1-mini, Gemini Live (voice) |
| **Voice** | Pipecat, Plivo, Whisper |
| **Integrations** | Composio (Google Docs, Drive, etc.) |
| **Auth** | JWT (python-jose), bcrypt |
| **Infra** | Docker, Docker Compose |

## Getting Started

### Prerequisites

- Python 3.9+
- Node.js 18+
- Docker & Docker Compose (optional, for PostgreSQL)

### 1. Clone the repo

```bash
git clone https://github.com/Yug-More/Parallel-AI.git
cd Parallel-AI
```

### 2. Backend setup

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: .\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Create a `.env` file in `backend/`:

```env
OPENAI_API_KEY_A=sk-...        # Team member 1 (Yug)
OPENAI_API_KEY_B=sk-...        # Team member 2 (Sean)
OPENAI_MODEL=gpt-4.1-mini
SECRET_KEY=your-jwt-secret

# Optional
DATABASE_URL=sqlite:///./parallel.db
COMPOSIO_API_KEY=...
PLIVO_AUTH_ID=...
PLIVO_AUTH_TOKEN=...
PLIVO_PHONE_NUMBER=...
GEMINI_API_KEY=...
AGI_API_KEY=...
```

Start the backend:

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 3. Frontend setup

```bash
cd parallel-frontend
npm install
npm run dev
```

### 4. Docker (alternative)

```bash
cd backend
docker compose up --build
```

This starts PostgreSQL and the FastAPI backend together. Then run the frontend separately with `npm run dev`.

### Access

| Service | URL |
|---------|-----|
| Frontend | http://localhost:5173 |
| Backend API | http://localhost:8000 |
| API Docs | http://localhost:8000/docs |

## Project Structure

```
Parallel-AI/
├── backend/
│   ├── main.py              # FastAPI application
│   ├── config.py            # API keys & client setup
│   ├── database.py          # SQLAlchemy engine & sessions
│   ├── models.py            # ORM models
│   ├── voice_agent.py       # Pipecat + Gemini voice agent
│   ├── spoon_official.py    # Spoon OS agent graph
│   ├── seed.py              # Database seeding
│   ├── docker-compose.yml   # PostgreSQL + backend services
│   └── Dockerfile
│
├── parallel-frontend/
│   ├── src/
│   │   ├── App.jsx          # Router & app shell
│   │   ├── pages/
│   │   │   ├── Landing.jsx  # Landing page
│   │   │   ├── Login.jsx    # Authentication
│   │   │   ├── Signup.jsx   # Registration
│   │   │   └── Dashboard.jsx# Main workspace
│   │   ├── components/
│   │   │   ├── ChatPanel.jsx    # Room chat interface
│   │   │   ├── ChatBubble.jsx   # Message rendering
│   │   │   └── ThemeToggle.jsx  # Dark/light mode
│   │   └── context/
│   │       └── ThemeContext.jsx
│   ├── package.json
│   └── vite.config.js
│
└── README.md
```

## API Overview

| Endpoint | Description |
|----------|-------------|
| `POST /auth/register` | Create a new account |
| `POST /auth/login` | Authenticate and receive JWT |
| `POST /rooms` | Create a shared room |
| `POST /rooms/{id}/ask` | Send a message to a room (triggers AI agents) |
| `GET /rooms/{id}/memory` | Retrieve room memory records |
| `POST /tasks` | Create a task |
| `PATCH /tasks/{id}` | Update task status |
| `GET /team` | List team members |
| `GET /events` | SSE stream for real-time updates |

Full API documentation is available at `/docs` when the backend is running.

## License

This project is not currently licensed for redistribution. All rights reserved.
