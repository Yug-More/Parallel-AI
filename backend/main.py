import os
import uuid
import asyncio
import json
from datetime import datetime
from typing import Dict, List, Literal, Optional

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import SessionLocal, engine, Base
from models import (
    AgentProfile as AgentORM,
    InboxTask as InboxTaskORM,
    MemoryRecord as MemoryORM,
    Message as MessageORM,
    Organization as OrganizationORM,
    Room as RoomORM,
    User as UserORM,
)

from config import CLIENTS, OPENAI_MODEL
from openai import OpenAI

# Which implementation to use:
#   official -> uses spoon_official.build_team_graph (Spoon OS StateGraph)
#   local    -> uses spoon_os ask_one/ask_team/synthesize (Windows-friendly)
SPOON_IMPL = os.getenv("SPOON_IMPL", "local").lower()
if SPOON_IMPL == "official":
    from spoon_official import build_team_graph
else:
    from spoon_os import ask_one, ask_team, synthesize

SUBSCRIBERS: set[asyncio.Queue] = set()
PROPAGATE_ERRORS = os.getenv("PROPAGATE_ERRORS", "false").lower() == "true"

TEAM = [
    {"id": "yug",     "name": "Yug"},
    {"id": "sean",    "name": "Sean"},
    {"id": "severin", "name": "Severin"},
    {"id": "nayab",   "name": "Nayab"},
]

# ============================================================
# API schemas
# ============================================================

class MessageOut(BaseModel):
    id: str
    sender_id: str
    sender_name: str
    role: Literal["user", "assistant", "system"]
    content: str
    created_at: datetime

    class Config:
        from_attributes = True

class CreateRoomRequest(BaseModel):
    room_name: str

class CreateRoomResponse(BaseModel):
    room_id: str
    room_name: str

class AskModeRequest(BaseModel):
    user_id: str
    user_name: str
    content: str
    mode: Literal["self", "teammate", "team"] = "self"
    target_agent: Optional[Literal["yug","sean","severin","nayab"]] = None  # used for self/teammate

class RoomResponse(BaseModel):
    room_id: str
    room_name: str
    project_summary: str
    memory_summary: str
    memory_count: int
    messages: List[MessageOut]

    class Config:
        from_attributes = True

class MemoryQueryRequest(BaseModel):
    question: str
    user_name: str = "System"

class CreateUserRequest(BaseModel):
    email: str
    name: str

class UserOut(BaseModel):
    id: str
    email: str
    name: str
    created_at: datetime

    class Config:
        from_attributes = True

class CreateOrgRequest(BaseModel):
    name: str
    owner_user_id: str

class OrgOut(BaseModel):
    id: str
    name: str
    owner_user_id: str
    created_at: datetime

    class Config:
        from_attributes = True

class CreateAgentRequest(BaseModel):
    user_id: str
    name: str
    persona_json: Dict = {}

class AgentOut(BaseModel):
    id: str
    user_id: str
    name: str
    persona_json: Dict
    persona_embedding: Optional[List[float]] = None
    created_at: datetime

    class Config:
        from_attributes = True

class InboxCreateRequest(BaseModel):
    content: str
    room_id: Optional[str] = None
    source_message_id: Optional[str] = None
    priority: Optional[str] = None
    tags: List[str] = []

class InboxUpdateRequest(BaseModel):
    status: Literal["open","done","archived"]
    priority: Optional[str] = None

class InboxTaskOut(BaseModel):
    id: str
    user_id: str
    content: str
    room_id: Optional[str] = None
    source_message_id: Optional[str] = None
    status: str
    priority: Optional[str] = None
    tags: List[str] = []
    created_at: datetime

    class Config:
        from_attributes = True

class PersonaImportRequest(BaseModel):
    raw_text: str

class MemoryOut(BaseModel):
    id: str
    agent_id: str
    room_id: Optional[str]
    content: str
    importance_score: float = 0.0
    embedding: Optional[List[float]] = None
    created_at: datetime

    class Config:
        from_attributes = True

# ============================================================
# FastAPI app + CORS
# ============================================================

app = FastAPI(title="Parallel Workspace with Shared Memory")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # open for local dev
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# Helpers
# ============================================================

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)
    seed_demo(SessionLocal())

def seed_demo(db: Session):
    existing = db.query(UserORM).first()
    if existing:
        return
    demo_user = UserORM(id=str(uuid.uuid4()), email="demo@parallel.local", name="Demo User")
    db.add(demo_user)
    db.flush()
    org = OrganizationORM(id=str(uuid.uuid4()), name="Demo Org", owner_user_id=demo_user.id)
    db.add(org)
    agent = AgentORM(
        id=str(uuid.uuid4()),
        user_id=demo_user.id,
        name="Parallel Brain",
        persona_json={"tone": "calm", "detail_level": "medium"},
    )
    db.add(agent)
    room = RoomORM(id=str(uuid.uuid4()), org_id=org.id, name="Demo Room")
    db.add(room)
    db.commit()

def client_for(agent_id: str) -> OpenAI:
    if agent_id not in CLIENTS:
        raise HTTPException(400, f"Unknown agent '{agent_id}'")
    return CLIENTS[agent_id]

def summary_update_from(text: str) -> Optional[str]:
    marker = "SUMMARY_UPDATE:"
    if marker not in text:
        return None
    return text.split(marker, 1)[1].strip() or None

def make_assistant_msg(agent_id: str, agent_name: str, content: str, room_id: Optional[str] = None) -> MessageORM:
    return MessageORM(
        id=str(uuid.uuid4()),
        room_id=room_id or "",
        sender_id=f"agent:{agent_id}",
        sender_name=agent_name,
        role="assistant",
        content=content,
        created_at=datetime.utcnow(),
    )

def append_memory_note(room: RoomORM, note: str):
    timestamp = datetime.utcnow().isoformat(timespec="seconds")
    summary = room.memory_summary or ""
    room.memory_summary = summary
    # store as MemoryRecord with low importance
    mem = MemoryORM(
        id=str(uuid.uuid4()),
        agent_id="coordinator",
        room_id=room.id,
        content=f"[{timestamp}] {note}",
        importance_score=0.1,
        created_at=datetime.utcnow(),
    )
    return mem

def build_system_context(db: Session, room: RoomORM) -> str:
    personas = []
    agents = db.query(AgentORM).all()
    for agent in agents:
        if agent.persona_json:
            personas.append(f"{agent.name}: {agent.persona_json}")

    persona_block = "\n".join(personas) if personas else "(none)"

    return f"""Shared Memory Summary (not auto-shown to users unless asked):
{room.memory_summary or "(empty yet)"}

Known personas:
{persona_block}

Team members:
- Yug (Frontend)
- Sean (Backend)
- Severin (Full stack/PM)
- Nayab (Coordination & Infra)

Guidelines:
- When answering, you may rely on the summary above to know what teammates are doing.
- Do not interrupt or change others' work unless asked; offer handoff steps or integration tips instead.
- If you think the memory summary should be updated, include at the end:

SUMMARY_UPDATE:
<1–3 sentences>
"""

def chat(client: OpenAI, messages: List[Dict[str, str]], temperature=0.4) -> str:
    try:
        resp = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            temperature=temperature,
        )
        return resp.choices[0].message.content
    except Exception as e:
        detail = str(e)
        resp = getattr(e, "response", None)
        if resp:
            try:
                detail = resp.json()
            except Exception:
                status = getattr(resp, "status_code", "?")
                detail = f"OpenAI error (status {status}): {e}"
        raise HTTPException(status_code=502, detail={"provider": "openai", "error": detail})

def to_message_out(msg: MessageORM) -> MessageOut:
    return MessageOut(
        id=msg.id,
        sender_id=msg.sender_id,
        sender_name=msg.sender_name,
        role=msg.role,  # type: ignore
        content=msg.content,
        created_at=msg.created_at,
    )

def room_to_response(db: Session, room: RoomORM) -> RoomResponse:
    msgs = (
        db.query(MessageORM)
        .filter(MessageORM.room_id == room.id)
        .order_by(MessageORM.created_at.asc())
        .all()
    )
    memories = db.query(MemoryORM).filter(MemoryORM.room_id == room.id).count()
    return RoomResponse(
        room_id=room.id,
        room_name=room.name,
        project_summary=room.project_summary or "",
        memory_summary=room.memory_summary or "",
        memory_count=memories,
        messages=[to_message_out(m) for m in msgs],
    )

# ============================================================
# Event stream (SSE)
# ============================================================

def publish_event(payload: Dict):
    """Push events to SSE subscribers when propagation is enabled."""
    if not PROPAGATE_ERRORS:
        return
    for q in list(SUBSCRIBERS):
        try:
            q.put_nowait(payload)
        except asyncio.QueueFull:
            continue

async def event_generator():
    queue: asyncio.Queue = asyncio.Queue()
    SUBSCRIBERS.add(queue)
    try:
        while True:
            data = await queue.get()
            yield f"data: {json.dumps(data)}\n\n"
    finally:
        SUBSCRIBERS.discard(queue)

def run_graph(app_graph, inputs):
    """
    Runs a Spoon graph call whether the SDK returns a sync result or a coroutine.
    """
    try:
        res = app_graph.invoke(inputs)
        if hasattr(res, "__await__"):
            import asyncio
            return asyncio.run(res)
        return res
    except TypeError:
        import asyncio
        return asyncio.run(app_graph.ainvoke(inputs))

# ============================================================
# Routes
# ============================================================

def publish_status(room_id: str, step: str, meta: Optional[Dict] = None):
    publish_event({
        "type": "status",
        "room_id": room_id,
        "step": step,
        "meta": meta or {},
        "ts": datetime.utcnow().isoformat(),
    })

def publish_error(room_id: str, message: str, meta: Optional[Dict] = None):
    publish_event({
        "type": "error",
        "room_id": room_id,
        "message": message,
        "meta": meta or {},
        "ts": datetime.utcnow().isoformat(),
    })

@app.get("/events")
async def events():
    """
    Server-Sent Events stream for status/error propagation.
    """
    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.post("/users", response_model=UserOut)
def create_user(payload: CreateUserRequest, db: Session = Depends(get_db)):
    user = UserORM(
        id=str(uuid.uuid4()),
        email=payload.email,
        name=payload.name,
        created_at=datetime.utcnow(),
    )
    db.add(user)
    db.commit()
    return user

@app.post("/organizations", response_model=OrgOut)
def create_org(payload: CreateOrgRequest, db: Session = Depends(get_db)):
    owner = db.get(UserORM, payload.owner_user_id)
    if not owner:
        raise HTTPException(404, "Owner user not found")
    org = OrganizationORM(
        id=str(uuid.uuid4()),
        name=payload.name,
        owner_user_id=payload.owner_user_id,
        created_at=datetime.utcnow(),
    )
    db.add(org)
    db.commit()
    return org

@app.post("/agents", response_model=AgentOut)
def create_agent(payload: CreateAgentRequest, db: Session = Depends(get_db)):
    user = db.get(UserORM, payload.user_id)
    if not user:
        raise HTTPException(404, "User not found")
    agent = AgentORM(
        id=str(uuid.uuid4()),
        user_id=payload.user_id,
        name=payload.name,
        persona_json=payload.persona_json or {},
        created_at=datetime.utcnow(),
    )
    db.add(agent)
    db.commit()
    return agent

@app.get("/users/{user_id}/inbox", response_model=List[InboxTaskOut])
def list_inbox(user_id: str, db: Session = Depends(get_db)):
    tasks = (
        db.query(InboxTaskORM)
        .filter(InboxTaskORM.user_id == user_id)
        .order_by(InboxTaskORM.created_at.desc())
        .all()
    )
    return tasks

@app.post("/users/{user_id}/inbox", response_model=InboxTaskOut)
def add_inbox(user_id: str, payload: InboxCreateRequest, db: Session = Depends(get_db)):
    user = db.get(UserORM, user_id)
    if not user:
        raise HTTPException(404, "User not found")
    task = InboxTaskORM(
        id=str(uuid.uuid4()),
        user_id=user_id,
        content=payload.content,
        room_id=payload.room_id,
        source_message_id=payload.source_message_id,
        priority=payload.priority,
        tags=payload.tags,
        created_at=datetime.utcnow(),
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task

@app.patch("/users/{user_id}/inbox/{task_id}", response_model=InboxTaskOut)
def update_inbox(user_id: str, task_id: str, payload: InboxUpdateRequest, db: Session = Depends(get_db)):
    task = db.get(InboxTaskORM, task_id)
    if not task or task.user_id != user_id:
        raise HTTPException(404, "Task not found")
    task.status = payload.status
    task.priority = payload.priority or task.priority
    db.add(task)
    db.commit()
    db.refresh(task)
    return task

@app.post("/users/{user_id}/import_persona")
def import_persona(user_id: str, payload: PersonaImportRequest, db: Session = Depends(get_db)):
    user = db.get(UserORM, user_id)
    if not user:
        raise HTTPException(404, "User not found")
    # Placeholder parser: derive tone/detail_level heuristically
    text = payload.raw_text
    tone = "calm"
    if any(word in text.lower() for word in ["urgent", "asap", "fast"]):
        tone = "direct"
    persona = {
        "tone": tone,
        "detail_level": "medium",
        "likes": [],
        "dislikes": [],
        "source": "import_persona_stub",
    }
    embedding = None  # placeholder until vector service is added
    return {"persona_json": persona, "persona_embedding": embedding}

@app.post("/rooms/{room_id}/memories", response_model=MemoryOut)
def add_memory(room_id: str, payload: MemoryQueryRequest, db: Session = Depends(get_db)):
    room = db.get(RoomORM, room_id)
    if not room:
        raise HTTPException(404, "Room not found")
    memory = MemoryORM(
        id=str(uuid.uuid4()),
        agent_id="coordinator",
        room_id=room_id,
        content=payload.question,
        importance_score=0.1,
        embedding=None,
        created_at=datetime.utcnow(),
    )
    db.add(memory)
    db.commit()
    db.refresh(memory)
    return memory

@app.get("/rooms/{room_id}/memories", response_model=List[MemoryOut])
def list_memories(room_id: str, db: Session = Depends(get_db)):
    room = db.get(RoomORM, room_id)
    if not room:
        raise HTTPException(404, "Room not found")
    memories = db.query(MemoryORM).filter(MemoryORM.room_id == room_id).all()
    return memories

@app.post("/rooms", response_model=CreateRoomResponse)
def create_room(payload: CreateRoomRequest, db: Session = Depends(get_db)):
    org = db.query(OrganizationORM).first()
    if not org:
        raise HTTPException(400, "No organization found; create one first.")
    room_id = str(uuid.uuid4())
    room = RoomORM(id=room_id, name=payload.room_name, org_id=org.id)
    db.add(room)
    db.commit()
    return CreateRoomResponse(room_id=room_id, room_name=room.name)

@app.get("/rooms/{room_id}", response_model=RoomResponse)
def get_room(room_id: str, db: Session = Depends(get_db)):
    room = db.get(RoomORM, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    return room_to_response(db, room)

@app.post("/rooms/{room_id}/ask", response_model=RoomResponse)
def ask(room_id: str, payload: AskModeRequest, db: Session = Depends(get_db)):
    room = db.get(RoomORM, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    publish_status(room_id, "ask_received", {"mode": payload.mode, "user": payload.user_name})

    # 1) store human message
    human = MessageORM(
        id=str(uuid.uuid4()),
        room_id=room.id,
        sender_id=f"user:{payload.user_id}",
        sender_name=payload.user_name,
        role="user",
        content=payload.content,
        created_at=datetime.utcnow(),
    )
    db.add(human)
    db.commit()

    sys_ctx = build_system_context(db, room)
    mode = payload.mode or "self"

    try:
        # 2) routing (official Spoon OS vs. local orchestrator)
        if SPOON_IMPL == "official":
            graph = build_team_graph()

            if mode in ("self", "teammate"):
                target = payload.target_agent or "yug"
                publish_status(room_id, "routing_agent", {"agent": target})

                # ask_one
                graph.set_entry_point("ask_one")
                app_graph = graph.compile()
                res = run_graph(app_graph, {
                    "asker": payload.user_name,
                    "prompt": payload.content,
                    "sys_ctx": sys_ctx,
                    "mode": mode,
                    "target": target,
                })
                drafts = res["drafts"]
                db.add(make_assistant_msg(target, target.title(), drafts[target], room.id))
                publish_status(room_id, "agent_reply", {"agent": target})

                # synthesize
                graph.set_entry_point("synthesize")
                app_graph = graph.compile()
                synth = run_graph(app_graph, {
                    "asker": payload.user_name,
                    "prompt": payload.content,
                    "sys_ctx": sys_ctx,
                    "drafts": drafts
                })["synthesis"]

                if (upd := summary_update_from(synth)):
                    room.project_summary = upd
                    room.memory_summary = upd
                    mem = append_memory_note(room, "Coordinator updated summary (from single-ask).")
                    db.add(mem)

            else:  # mode == "team"
                publish_status(room_id, "team_fanout_start", {"agents": [m["id"] for m in TEAM]})
                # ask_team
                graph.set_entry_point("ask_team")
                app_graph = graph.compile()
                res = run_graph(app_graph, {
                    "asker": payload.user_name,
                    "prompt": payload.content,
                    "sys_ctx": sys_ctx,
                })
                drafts: Dict[str, str] = res["drafts"]

                for member, text in drafts.items():
                    msg = make_assistant_msg(member, member.title(), text, room.id)
                    db.add(msg)

                # synthesize
                publish_status(room_id, "synthesizing", {"agent": "Coordinator"})
                graph.set_entry_point("synthesize")
                app_graph = graph.compile()
                synth = run_graph(app_graph, {
                    "asker": payload.user_name,
                    "prompt": payload.content,
                    "sys_ctx": sys_ctx,
                    "drafts": drafts
                })["synthesis"]

                synth_msg = make_assistant_msg("coordinator", "Coordinator", synth, room.id)
                db.add(synth_msg)
                publish_status(room_id, "synthesis_complete", {"agent": "Coordinator"})

                if (upd := summary_update_from(synth)):
                    room.project_summary = upd
                    room.memory_summary = upd
                    mem = append_memory_note(room, "Coordinator updated summary.")
                    db.add(mem)

        else:
            # Local orchestrator (Windows friendly)
            if mode in ("self", "teammate"):
                agent_id = payload.target_agent or "yug"
                publish_status(room_id, "routing_agent", {"agent": agent_id})
                drafts = ask_one(payload.user_name, payload.content, sys_ctx, agent_id)
                msg = make_assistant_msg(agent_id, agent_id.title(), drafts[agent_id], room.id)
                db.add(msg)
                publish_status(room_id, "agent_reply", {"agent": agent_id})

                synth = synthesize(payload.user_name, payload.content, sys_ctx, drafts)
                if (upd := summary_update_from(synth)):
                    room.project_summary = upd
                    room.memory_summary = upd
                    mem = append_memory_note(room, "Coordinator updated summary (from single-ask).")
                    db.add(mem)

            else:  # mode == "team"
                publish_status(room_id, "team_fanout_start", {"agents": [m["id"] for m in TEAM]})
                drafts = ask_team(payload.user_name, payload.content, sys_ctx)
                for member, text in drafts.items():
                    msg = make_assistant_msg(member, member.title(), text, room.id)
                    db.add(msg)

                publish_status(room_id, "synthesizing", {"agent": "Coordinator"})
                synth = synthesize(payload.user_name, payload.content, sys_ctx, drafts)
                synth_msg = make_assistant_msg("coordinator", "Coordinator", synth, room.id)
                db.add(synth_msg)
                publish_status(room_id, "synthesis_complete", {"agent": "Coordinator"})

                if (upd := summary_update_from(synth)):
                    room.project_summary = upd
                    room.memory_summary = upd
                    mem = append_memory_note(room, "Coordinator updated summary.")
                    db.add(mem)
        db.add(room)
        db.commit()
    except Exception as exc:
        publish_error(room_id, str(exc), {"mode": mode})
        raise

    db.refresh(room)
    return room_to_response(db, room)

@app.get("/rooms/{room_id}/memory")
def get_memory(room_id: str):
    room = ROOMS.get(room_id)
    if not room:
        raise HTTPException(404, "Room not found")
    # Return summary + last 20 notes
    return {
        "memory_summary": room.memory_summary,
        "notes": room.memory_notes[-20:],
        "count": len(room.memory_notes),
    }

@app.post("/rooms/{room_id}/memory/query")
def query_memory(room_id: str, payload: MemoryQueryRequest):
    db = SessionLocal()
    room = db.get(RoomORM, room_id)
    if not room:
        db.close()
        raise HTTPException(404, "Room not found")
    memories = db.query(MemoryORM).filter(MemoryORM.room_id == room_id).order_by(MemoryORM.created_at.desc()).all()
    context_block = "\n".join(m.content for m in memories[-200:])
    context = (room.memory_summary or "") + "\n\n" + context_block
    msgs = [
        {"role": "system", "content": "You are the project memory. Answer using only the provided memory context."},
        {"role": "system", "content": f"MEMORY CONTEXT:\n{context or '(empty)'}"},
        {"role": "user", "content": f"{payload.user_name} asks: {payload.question}"},
    ]
    answer = chat(client_for("coordinator"), msgs, temperature=0.2)
    note = append_memory_note(room, f"Memory was queried: {payload.question}")
    if note:
        db.add(note)
    db.commit()
    db.close()
    return {"answer": answer}
