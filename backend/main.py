import os
import uuid
from datetime import datetime
from typing import Dict, List, Literal, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

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

# ============================================================
# Data models / in-memory store (hackathon simple)
# ============================================================

class Message(BaseModel):
    id: str
    sender_id: str           # e.g. "user:severin", "agent:yug"
    sender_name: str         # "Severin", "Yug", etc.
    role: Literal["user", "assistant", "system"]
    content: str
    created_at: datetime

class RoomState(BaseModel):
    id: str
    name: str
    project_summary: str = ""
    messages: List[Message] = []
    # shared memory (not auto-shown; only used when asked)
    memory_summary: str = ""              # 1–3 sentence rolling summary
    memory_notes: List[str] = []          # append-only log of important notes

ROOMS: Dict[str, RoomState] = {}

TEAM = [
    {"id": "yug",     "name": "Yug"},
    {"id": "sean",    "name": "Sean"},
    {"id": "severin", "name": "Severin"},
    {"id": "nayab",   "name": "Nayab"},
]

# ============================================================
# API schemas
# ============================================================

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
    messages: List[Message]

class MemoryQueryRequest(BaseModel):
    question: str
    user_name: str = "System"

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

def client_for(agent_id: str) -> OpenAI:
    if agent_id not in CLIENTS:
        raise HTTPException(400, f"Unknown agent '{agent_id}'")
    return CLIENTS[agent_id]

def summary_update_from(text: str) -> Optional[str]:
    marker = "SUMMARY_UPDATE:"
    if marker not in text:
        return None
    return text.split(marker, 1)[1].strip() or None

def make_assistant_msg(agent_id: str, agent_name: str, content: str) -> Message:
    return Message(
        id=str(uuid.uuid4()),
        sender_id=f"agent:{agent_id}",
        sender_name=agent_name,
        role="assistant",
        content=content,
        created_at=datetime.utcnow(),
    )

def append_memory_note(room: RoomState, note: str) -> None:
    room.memory_notes.append(f"[{datetime.utcnow().isoformat(timespec='seconds')}] {note}")

def build_system_context(room: RoomState) -> str:
    # memory_summary is concise; memory_notes are only summarized when asked
    return f"""Shared Memory Summary (not auto-shown to users unless asked):
{room.memory_summary or "(empty yet)"}

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

@app.post("/rooms", response_model=CreateRoomResponse)
def create_room(payload: CreateRoomRequest):
    room_id = str(uuid.uuid4())
    room = RoomState(id=room_id, name=payload.room_name)
    ROOMS[room_id] = room
    return CreateRoomResponse(room_id=room_id, room_name=room.name)

@app.get("/rooms/{room_id}", response_model=RoomResponse)
def get_room(room_id: str):
    room = ROOMS.get(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    return RoomResponse(
        room_id=room.id,
        room_name=room.name,
        project_summary=room.project_summary,
        memory_summary=room.memory_summary,
        memory_count=len(room.memory_notes),
        messages=room.messages,
    )

@app.post("/rooms/{room_id}/ask", response_model=RoomResponse)
def ask(room_id: str, payload: AskModeRequest):
    room = ROOMS.get(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    # 1) store human message
    human = Message(
        id=str(uuid.uuid4()),
        sender_id=f"user:{payload.user_id}",
        sender_name=payload.user_name,
        role="user",
        content=payload.content,
        created_at=datetime.utcnow(),
    )
    room.messages.append(human)

    sys_ctx = build_system_context(room)
    mode = payload.mode or "self"

    # 2) routing (official Spoon OS vs. local orchestrator)
    if SPOON_IMPL == "official":
        graph = build_team_graph()

        if mode in ("self", "teammate"):
            target = payload.target_agent or "yug"

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
            room.messages.append(make_assistant_msg(target, target.title(), drafts[target]))

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
                append_memory_note(room, "Coordinator updated summary (from single-ask).")

        else:  # mode == "team"
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
                room.messages.append(make_assistant_msg(member, member.title(), text))

            # synthesize
            graph.set_entry_point("synthesize")
            app_graph = graph.compile()
            synth = run_graph(app_graph, {
                "asker": payload.user_name,
                "prompt": payload.content,
                "sys_ctx": sys_ctx,
                "drafts": drafts
            })["synthesis"]

            room.messages.append(make_assistant_msg("coordinator", "Coordinator", synth))

            if (upd := summary_update_from(synth)):
                room.project_summary = upd
                room.memory_summary = upd
                append_memory_note(room, "Coordinator updated summary.")

    else:
        # Local orchestrator (Windows friendly)
        if mode in ("self", "teammate"):
            agent_id = payload.target_agent or "yug"
            drafts = ask_one(payload.user_name, payload.content, sys_ctx, agent_id)
            room.messages.append(make_assistant_msg(agent_id, agent_id.title(), drafts[agent_id]))

            synth = synthesize(payload.user_name, payload.content, sys_ctx, drafts)
            if (upd := summary_update_from(synth)):
                room.project_summary = upd
                room.memory_summary = upd
                append_memory_note(room, "Coordinator updated summary (from single-ask).")

        else:  # mode == "team"
            drafts = ask_team(payload.user_name, payload.content, sys_ctx)
            for member, text in drafts.items():
                room.messages.append(make_assistant_msg(member, member.title(), text))

            synth = synthesize(payload.user_name, payload.content, sys_ctx, drafts)
            room.messages.append(make_assistant_msg("coordinator", "Coordinator", synth))

            if (upd := summary_update_from(synth)):
                room.project_summary = upd
                room.memory_summary = upd
                append_memory_note(room, "Coordinator updated summary.")

    return RoomResponse(
        room_id=room.id,
        room_name=room.name,
        project_summary=room.project_summary,
        memory_summary=room.memory_summary,
        memory_count=len(room.memory_notes),
        messages=room.messages,
    )

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
    room = ROOMS.get(room_id)
    if not room:
        raise HTTPException(404, "Room not found")
    # Simple QA over memory_summary + notes (concatenate for now)
    context = room.memory_summary + "\n\n" + "\n".join(room.memory_notes[-200:])
    msgs = [
        {"role": "system", "content": "You are the project memory. Answer using only the provided memory context."},
        {"role": "system", "content": f"MEMORY CONTEXT:\n{context or '(empty)'}"},
        {"role": "user", "content": f"{payload.user_name} asks: {payload.question}"},
    ]
    answer = chat(client_for("coordinator"), msgs, temperature=0.2)
    append_memory_note(room, f"Memory was queried: {payload.question}")
    return {"answer": answer}
