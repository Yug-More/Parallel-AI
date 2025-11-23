# ============================================================
# main.py — Fully Rewritten Clean Backend (Part 1 of 3)
# ============================================================

import os, re, uuid, json
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Literal

from fastapi import FastAPI, Request, Response, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse, StreamingResponse
from pydantic import BaseModel
from jose import jwt, JWTError
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from sqlalchemy import func

from database import SessionLocal, engine, Base
from models import (
    User as UserORM,
    UserCredential as UserCredentialORM,
    Organization as OrganizationORM,
    Room as RoomORM,
    Message as MessageORM,
    InboxTask as InboxTaskORM,
    Notification as NotificationORM,
    MemoryRecord as MemoryORM,
    AgentProfile as AgentORM,
)

from openai import OpenAI
from config import CLIENTS, OPENAI_MODEL
from dotenv import load_dotenv

load_dotenv()

import logging

logger = logging.getLogger("parallel-backend")
logger.setLevel(logging.INFO)

# ============================================================
# App + CORS
# ============================================================

app = FastAPI(title="Parallel Workspace — Clean Rebuild")

ALLOWED_ORIGINS = ["http://localhost:5173"]
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 1440

# ============================================================
# Utility
# ============================================================

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_default_client():
    # Prefer an explicit "openai" client, fall back to coordinator, then any client
    if "openai" in CLIENTS:
        return CLIENTS["openai"]
    if "coordinator" in CLIENTS:
        return CLIENTS["coordinator"]
    for _, client in CLIENTS.items():
        return client
    raise HTTPException(500, "No OpenAI client configured")


def build_system_prompt_for_room(db: Session, room, user, mode: str = "team") -> str:
    """
    Fallback system prompt builder.
    """
    role = getattr(user, "role", None) or "Member"
    return (
        f"Room: {getattr(room, 'name', '')}\\n"
        f"User: {getattr(user, 'name', 'User')} (role: {role})\\n"
        f"Mode: {mode}\\n"
        "Be concise. Answer only the user's question. Do not add next steps unless asked."
    )

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=60))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def verify_password(plain: str, hashed: str) -> bool:
    try:
        return pwd_context.verify(plain, hashed)
    except Exception:
        return False


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


# ============================================================
# Current user
# ============================================================

def get_current_user(request: Request, db: Session) -> Optional[UserORM]:
    token = request.cookies.get("access_token")
    if not token:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        return db.get(UserORM, user_id)
    except JWTError:
        return None


def require_user(request: Request, db: Session) -> UserORM:
    user = get_current_user(request, db)
    if not user:
        raise HTTPException(401, "Not authenticated")
    return user

def get_or_create_org_for_user(db: Session, user: UserORM) -> OrganizationORM:
    """
    For now we treat the app as single-tenant:
    - If a 'Demo Org' (or any org) exists, everyone joins that org.
    - If no org exists yet, create one for the current user.

    This guarantees all users share the same org and avoids org-mismatch
    403s from legacy per-user org rows.
    """
    # Prefer a named demo org if it exists
    org = (
        db.query(OrganizationORM)
        .filter(OrganizationORM.name == "Demo Org")
        .first()
    )
    if org:
        # Optionally sync user.org_id to this org if the column exists
        if getattr(user, "org_id", None) != org.id:
            setattr(user, "org_id", org.id)
            db.add(user)
            db.commit()
        return org

    # Otherwise just grab the first org in the table, if any
    org = db.query(OrganizationORM).order_by(OrganizationORM.created_at.asc()).first()
    if org:
        if getattr(user, "org_id", None) != org.id:
            setattr(user, "org_id", org.id)
            db.add(user)
            db.commit()
        return org

    # No orgs yet — create the first one
    org = OrganizationORM(
        id=str(uuid.uuid4()),
        name=f"{user.name}'s Org" if user.name else "Workspace",
        owner_user_id=user.id,
        created_at=datetime.utcnow(),
    )
    db.add(org)
    db.commit()

    if hasattr(user, "org_id"):
        user.org_id = org.id
        db.add(user)
        db.commit()

    return org


def ensure_room_access(db: Session, user: UserORM, room: RoomORM, expected_label: str | None = None) -> RoomORM:
    """
    Make sure the room is attached to the same org as the current user.

    - If the room has no org_id, attach it to the user's org.
    - If the room org_id mismatches, reassign it (soft fix) and log a warning.
    - Optionally warn if the room name does not match the expected label,
      but NEVER block on name mismatch.
    """
    if room is None:
        raise HTTPException(status_code=404, detail="Room not found")

    org = get_or_create_org_for_user(db, user)

    if room.org_id is None:
        room.org_id = org.id
        db.add(room)
        db.commit()
        logger.info("Attached legacy room %s to org %s", room.id, org.id)
    elif room.org_id != org.id:
        logger.warning(
            "Room %s org mismatch (room.org_id=%s, user_org=%s). Reassigning.",
            room.id,
            room.org_id,
            org.id,
        )
        room.org_id = org.id
        db.add(room)
        db.commit()

    # Soft name check only
    if expected_label:
        canonical = f"{expected_label.title()} Room"
        if room.name.strip() != canonical:
            logger.warning(
                "Room %s name mismatch for label %s (room.name=%r, expected=%r)",
                room.id,
                expected_label,
                room.name,
                canonical,
            )

    return room


class AuthLoginRequest(BaseModel):
    email: str
    password: str


class UserOut(BaseModel):
    id: str
    email: str
    name: str
    created_at: datetime

    class Config:
        from_attributes = True


class CreateUserRequest(BaseModel):
    email: str
    name: str
    password: str


class CreateRoomRequest(BaseModel):
    room_name: str

    class Config:
        allow_population_by_field_name = True
        fields = {
            "room_name": "roomName",  # accept both room_name and roomName
        }


class CreateRoomResponse(BaseModel):
    room_id: str
    room_name: str


class AskModeRequest(BaseModel):
    user_id: str
    user_name: str
    content: str
    mode: Literal["self", "teammate", "team"] = "self"
    target_agent: Optional[str] = None


class MessageOut(BaseModel):
    id: str
    sender_id: str
    sender_name: str
    role: str
    content: str
    created_at: datetime

    class Config:
        from_attributes = True


class RoomResponse(BaseModel):
    room_id: str
    room_name: str
    project_summary: str
    memory_summary: str
    memory_count: int
    messages: List[MessageOut]

    class Config:
        from_attributes = True


class InboxCreateRequest(BaseModel):
    content: str
    room_id: Optional[str] = None
    source_message_id: Optional[str] = None
    priority: Optional[str] = None
    tags: List[str] = []


class InboxUpdateRequest(BaseModel):
    status: Literal["open", "done", "archived"]
    priority: Optional[str] = None


class InboxTaskOut(BaseModel):
    id: str
    content: str
    status: str
    priority: Optional[str]
    room_id: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class NotificationCreate(BaseModel):
    title: str
    message: Optional[str] = None
    room_id: Optional[str] = None
    source_message_id: Optional[str] = None
    priority: Optional[str] = None
    tags: List[str] = []


class NotificationOut(BaseModel):
    id: str
    user_id: str
    type: str
    title: str
    message: str
    created_at: datetime
    is_read: bool

    class Config:
        from_attributes = True


# ============================================================
# Helper: Convert ORM → Response
# ============================================================

def to_message_out(m: MessageORM) -> MessageOut:
    return MessageOut(
        id=m.id,
        sender_id=m.sender_id,
        sender_name=m.sender_name,
        role=m.role,
        content=m.content,
        created_at=m.created_at,
    )


def room_to_response(db: Session, room: RoomORM) -> RoomResponse:
    messages = (
        db.query(MessageORM)
        .filter(MessageORM.room_id == room.id)
        .order_by(MessageORM.created_at.asc())
        .all()
    )
    memory_count = (
        db.query(MemoryORM).filter(MemoryORM.room_id == room.id).count()
    )
    return RoomResponse(
        room_id=room.id,
        room_name=room.name,
        project_summary=room.project_summary or "",
        memory_summary=room.memory_summary or "",
        memory_count=memory_count,
        messages=[to_message_out(m) for m in messages],
    )


# ============================================================
# AUTH ROUTES (Fix #3)
# ============================================================

@app.post("/auth/register", response_model=UserOut)
def register(payload: CreateUserRequest, response: Response, db: Session = Depends(get_db)):
    exists = db.query(UserORM).filter(UserORM.email == payload.email).first()
    if exists:
        raise HTTPException(400, "Email already registered")

    user = UserORM(
        id=str(uuid.uuid4()),
        email=payload.email,
        name=payload.name,
        created_at=datetime.now(timezone.utc),
    )
    cred = UserCredentialORM(
        user_id=user.id,
        password_hash=hash_password(payload.password),
        created_at=datetime.now(timezone.utc),
    )
    db.add(user)
    db.add(cred)
    db.commit()

    # Auto-login
    token = create_access_token({"sub": user.id})
    response.set_cookie(
        "access_token",
        token,
        httponly=True,
        secure=False,
        samesite="lax",
        path="/",
    )

    return user


@app.post("/auth/login")
def login(payload: AuthLoginRequest, response: Response, db: Session = Depends(get_db)):
    user = db.query(UserORM).filter(UserORM.email == payload.email).first()
    if not user:
        raise HTTPException(401, "Invalid credentials")

    cred = db.get(UserCredentialORM, user.id)
    if not cred or not verify_password(payload.password, cred.password_hash):
        raise HTTPException(401, "Invalid credentials")

    token = create_access_token({"sub": user.id})
    response = JSONResponse({"ok": True})
    response.set_cookie(
        "access_token",
        token,
        httponly=True,
        secure=False,
        samesite="lax",
        path="/",
    )
    return response

@app.post("/auth/logout")
def logout(response: Response):
    # Just clear the cookie; frontend will reload
    resp = JSONResponse({"ok": True})
    resp.delete_cookie("access_token", path="/")
    return resp


@app.get("/me", response_model=UserOut)
def me(request: Request, db: Session = Depends(get_db)):
    user = require_user(request, db)
    get_or_create_org_for_user(db, user)   # Fix #4 ensure_org exists
    return user

@app.post("/rooms", response_model=CreateRoomResponse)
def create_room(payload: CreateRoomRequest, request: Request, db: Session = Depends(get_db)):
    user = require_user(request, db)
    org = get_or_create_org_for_user(db, user)

    room = RoomORM(
        id=str(uuid.uuid4()),
        name=payload.room_name,
        org_id=org.id,
        created_at=datetime.now(timezone.utc),
    )
    db.add(room)
    db.commit()
    db.refresh(room)

    return CreateRoomResponse(room_id=room.id, room_name=room.name)



@app.get("/rooms/{room_id}", response_model=RoomResponse)
def get_room(room_id: str, request: Request, db: Session = Depends(get_db)):
    user = require_current_user(request, db)
    room = db.get(RoomORM, room_id)
    room = ensure_room_access(db, user, room)
    return room_to_response(db, room)



CANONICAL_ROOMS = {
    "engineering": "Engineering Room",
    "design": "Design Room",
    "team": "Team Room",
    "product": "Product Room",
}


@app.get("/rooms/team/{team_label}")
def get_or_create_team_room(team_label: str, request: Request, db: Session = Depends(get_db)):
    """
    Required by new dashboard → resolves canonical team room.
    """
    user = require_user(request, db)
    org = get_or_create_org_for_user(db, user)

    key = team_label.lower().strip()
    room_name = CANONICAL_ROOMS.get(key, f"{team_label.title()} Room")

    room = (
        db.query(RoomORM)
        .filter(RoomORM.org_id == org.id, RoomORM.name == room_name)
        .first()
    )
    if not room:
        room = RoomORM(
            id=str(uuid.uuid4()),
            name=room_name,
            org_id=org.id,
            created_at=datetime.now(timezone.utc),
        )
        db.add(room)
        db.commit()

    return {"room_id": room.id, "room_name": room.name}


# ============================================================
# SSE — STATUS/ERROR STREAM (Fix #11)
# ============================================================

SUBSCRIBERS = []   # list[(queue, filters {room_id,user_id})]

async def event_generator(filters: Dict):
    queue: asyncio.Queue = asyncio.Queue()
    SUBSCRIBERS.append((queue, filters))
    try:
        while True:
            payload = await queue.get()
            # room filter
            if filters.get("room_id") and payload.get("room_id") != filters.get("room_id"):
                continue
            # user filter
            if filters.get("user_id") and payload.get("user_id") != filters.get("user_id"):
                continue
            yield f"data: {json.dumps(payload)}\n\n"
    finally:
        if (queue, filters) in SUBSCRIBERS:
            SUBSCRIBERS.remove((queue, filters))


def publish_event(payload: Dict):
    for queue, filters in list(SUBSCRIBERS):
        try:
            queue.put_nowait(payload)
        except asyncio.QueueFull:
            pass


@app.get("/events")
async def events(room_id: Optional[str] = None, user_id: Optional[str] = None):
    """
    SSE stream filtered by room
    """
    filters = {"room_id": room_id, "user_id": user_id}
    return StreamingResponse(event_generator(filters), media_type="text/event-stream")


def publish_status(room_id: str, step: str, meta: Optional[Dict] = None):
    publish_event({
        "type": "status",
        "room_id": room_id,
        "step": step,
        "meta": meta or {},
        "ts": datetime.now(timezone.utc).isoformat(),
    })


def publish_error(room_id: str, message: str, meta: Optional[Dict] = None):
    publish_event({
        "type": "error",
        "room_id": room_id,
        "message": message,
        "meta": meta or {},
        "ts": datetime.now(timezone.utc).isoformat(),
    })

@app.get("/users/{user_id}/inbox", response_model=List[InboxTaskOut])
def list_inbox(user_id: str, request: Request, db: Session = Depends(get_db)):
    me = require_user(request, db)

    # Allow legacy "demo-user" slug to map to the logged-in user
    if user_id == "demo-user":
        user_id = me.id

    if me.id != user_id:
        raise HTTPException(403, "Forbidden")

    tasks = (
        db.query(InboxTaskORM)
        .filter(InboxTaskORM.user_id == user_id)
        .order_by(InboxTaskORM.created_at.desc())
        .all()
    )
    return tasks

@app.post("/users/{user_id}/inbox", response_model=InboxTaskOut)
def add_inbox(user_id: str, payload: InboxCreateRequest, request: Request, db: Session = Depends(get_db)):
    me = require_user(request, db)
    if me.id != user_id:
        raise HTTPException(403, "Forbidden")

    task = InboxTaskORM(
        id=str(uuid.uuid4()),
        user_id=user_id,
        content=payload.content,
        room_id=payload.room_id,
        source_message_id=payload.source_message_id,
        priority=payload.priority,
        tags=payload.tags,
        status="open",
        created_at=datetime.now(timezone.utc),
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@app.patch("/users/{user_id}/inbox/{task_id}", response_model=InboxTaskOut)
def update_inbox(user_id: str, task_id: str, payload: InboxUpdateRequest, request: Request, db: Session = Depends(get_db)):
    me = require_user(request, db)
    if me.id != user_id:
        raise HTTPException(403, "Forbidden")

    task = db.get(InboxTaskORM, task_id)
    if not task or task.user_id != user_id:
        raise HTTPException(404, "Task not found")

    task.status = payload.status
    task.priority = payload.priority or task.priority

    db.add(task)
    db.commit()
    db.refresh(task)
    return task

@app.get("/users/{user_id}/notifications", response_model=List[NotificationOut])
def list_notifications(user_id: str, request: Request, db: Session = Depends(get_db)):
    me = require_user(request, db)

    if user_id == "demo-user":
        user_id = me.id

    if me.id != user_id:
        raise HTTPException(403, "Forbidden")

    notifs = (
        db.query(NotificationORM)
        .filter(NotificationORM.user_id == user_id)
        .order_by(NotificationORM.created_at.desc())
        .all()
    )
    return notifs

@app.post("/users/{user_id}/notifications", response_model=NotificationOut)
def create_notification(user_id: str, payload: NotificationCreate, request: Request, db: Session = Depends(get_db)):
    me = require_user(request, db)

    notif = NotificationORM(
        id=str(uuid.uuid4()),
        user_id=user_id,
        type="task",
        title=payload.title,
        message=payload.message or payload.title,
        created_at=datetime.now(timezone.utc),
        is_read=False,
    )
    db.add(notif)
    db.commit()
    db.refresh(notif)
    return notif

def get_current_user(request: Request, db: Session) -> Optional[UserORM]:
    token = request.cookies.get("access_token")
    if not token:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if not user_id:
            return None
    except JWTError:
        return None
    return db.get(UserORM, user_id)


def require_current_user(request: Request, db: Session) -> UserORM:
    """
    Fetch the currently authenticated user from the JWT cookie.
    Raise 401 if not authenticated.
    """
    user = get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


# ============================================================
# MEMORY HELPERS
# ============================================================

def append_memory(db: Session, room: RoomORM, agent_id: str, content: str, importance: float = 0.1):
    mem = MemoryORM(
        id=str(uuid.uuid4()),
        agent_id=agent_id,
        room_id=room.id,
        content=content,
        importance_score=importance,
        created_at=datetime.now(timezone.utc),
    )
    db.add(mem)
    return mem


def list_recent_memories(db: Session, room_id: str, limit: int = 8):
    return (
        db.query(MemoryORM)
        .filter(MemoryORM.room_id == room_id)
        .order_by(MemoryORM.created_at.desc())
        .limit(limit)
        .all()
    )


# ============================================================
# SUMMARY UPDATE RULES (Fix #14)
# ============================================================

def extract_explicit_summary_request(text: str) -> Optional[str]:
    """
    Only update summary if user writes something like:
        "update summary: <text>"
    """
    marker = "update summary:"
    lower = text.lower()
    if marker in lower:
        return text[lower.index(marker) + len(marker):].strip()
    return None

def build_ai_prompt(
    db: Session,
    room: RoomORM,
    user: UserORM,
    content: str,
    mode: str,
):
    """
    Build a system + user prompt that:
    - Only goes into "draft a message to X" mode when the user actually
      asks to send/notify/tell someone.
    - Otherwise just answers the question normally.
    - Always talks to the user as "you" / "I", not using their name.
    """
    memories = list_recent_memories(db, room.id, limit=8)
    mem_text = "\n".join(f"- {m.content}" for m in memories)

    # Figure out teammate names in this org (excluding current user)
    teammate_names: list[str] = []
    if room.org_id:
        teammates = (
            db.query(UserORM)
            .filter(UserORM.org_id == room.org_id)
            .all()
        )
        teammate_names = [
            (u.name or "").strip()
            for u in teammates
            if u.id != user.id and (u.name or "").strip()
        ]

    text_lower = (content or "").lower()
    outreach_verbs = [
        "tell ",
        "message ",
        "notify ",
        "ping ",
        "remind ",
        "email ",
        "dm ",
        "slack ",
        "text ",
        "send a message",
        "send this to",
        "let them know",
    ]
    has_verb = any(v in text_lower for v in outreach_verbs)
    has_teammate_name = any(
        name and name.lower() in text_lower for name in teammate_names
    )
    is_outreach = has_verb and has_teammate_name

    # Base system prompt
    system = f"""
You are the workspace assistant inside the room "{room.name}".

Core rules:
- Never actually send messages outside this chat. You only talk to the user here.
- Never say that you are "drafting" a message or "won't send it automatically".
- Never auto-create inbox tasks or notifications unless the user clearly asks for that.
- Never update summaries unless the user explicitly says: "update summary: ...".
- Answer concisely and stay on task.
- Do not hallucinate tasks, inbox items, or teammates that don't exist.
- The user's name is "{user.name}". When you talk to them, refer to them as "you".
  If you write a message on their behalf, speak in first person ("I", "we") and
  never say their name in third person.

""".rstrip()

    if is_outreach:
        # Only in true teammate-messaging scenarios do we use the helper pattern.
        system += """

Current request type: TEAM OUTREACH.

The user is asking you to help send a message to another teammate.

When the user asks you to "send a message to X", "tell X that ...", or similar:
- Assume they want help with the wording.
- Respond with ONE short, natural message they could send, written in the user's voice.
  For example:
    "Hi Alice, could you take a look at the UI and finish the remaining tasks today?"
- Do NOT say "Here is a draft" or "I won't send this automatically".
- You may ask ONCE:
    "Do you want to use that message as-is?"
- Do not ask for confirmation more than once and do not loop.
"""
    else:
        # For normal questions, forbid the draft-message pattern entirely.
        system += """

Current request type: NORMAL QUESTION.

The user is NOT asking you to send or draft a message to a teammate.
For this request:
- Just answer the question directly.
- Do NOT suggest or draft messages to teammates.
- Do NOT use phrases like "Here’s a message you could send to X".
- Do NOT ask whether they want to send anything.
"""

    system += f"""

You may use these recent memory notes and project context:

Project Summary:
{room.project_summary or "(none)"}

Recent Memory Notes:
{mem_text or "(none)"}

Mode: {mode}
""".rstrip()

    # User message is just their raw content; no third-person name.
    user_msg = content

    return system, user_msg


def run_ai(client: OpenAI, system_prompt: str, user_text: str) -> str:
    """
    Unified OpenAI chat wrapper.
    """
    resp = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_text},
        ],
        temperature=0.4,
    )
    return resp.choices[0].message.content


CONFIRM_PHRASES = [
    "yes",
    "yes please",
    "yes, please",
    "yeah",
    "yep",
    "sure",
    "please send",
    "send it",
    "send it for me",
    "go ahead and send",
    "can you send it for me",
]


def maybe_send_approved_message(
    db: Session,
    room: RoomORM,
    user: UserORM,
    latest_text: str,
) -> Optional[MessageORM]:
    """
    If the latest user message is a confirmation to send a previously
    suggested draft (e.g., 'Yes please, send it'), convert that draft
    into a NotificationORM and add a deterministic assistant reply.

    Returns the assistant MessageORM if we handled it, otherwise None.
    """
    normalized = latest_text.strip().lower()
    if not any(p in normalized for p in CONFIRM_PHRASES):
        return None

    # Look at the most recent assistant message in this room
    last_assistant = (
        db.query(MessageORM)
        .filter(MessageORM.room_id == room.id, MessageORM.role == "assistant")
        .order_by(MessageORM.created_at.desc())
        .first()
    )
    if not last_assistant or not last_assistant.content:
        return None

    content = last_assistant.content

    # Pattern: “Here’s a message you could send to Angie: "Hi Angie, ..." …”
    m = re.search(
        r"message you could send to\s+([A-Za-z][A-Za-z0-9_\- ]*)\s*:\s*\"(.+?)\"",
        content,
        flags=re.DOTALL,
    )
    if not m:
        return None

    target_name = m.group(1).strip()
    message_text = m.group(2).strip()

    # Find recipient user in same org
    recipient = (
        db.query(UserORM)
        .filter(
            UserORM.org_id == room.org_id,
            func.lower(UserORM.name) == target_name.lower(),
        )
        .first()
    )

    # If we can't find them, just tell the user and bail
    if not recipient:
        bot_msg = MessageORM(
            id=str(uuid.uuid4()),
            room_id=room.id,
            sender_id="agent:coordinator",
            sender_name="Coordinator",
            role="assistant",
            content=(
                f"I couldn't find a teammate named {target_name} in your workspace, "
                f"so I couldn’t send it automatically. Here’s the message again for you "
                f"to copy and send manually:\n\n{message_text}"
            ),
            created_at=datetime.now(timezone.utc),
        )
        db.add(bot_msg)
        db.commit()
        return bot_msg

    # Create notification with EXACT approved content
    notif = NotificationORM(
        id=str(uuid.uuid4()),
        user_id=recipient.id,
        type="message",
        title=f"Message from {user.name}",
        message=message_text,
        created_at=datetime.now(timezone.utc),
        is_read=False,
    )
    db.add(notif)

    # Deterministic assistant reply – no LLM call
    bot_msg = MessageORM(
        id=str(uuid.uuid4()),
        room_id=room.id,
        sender_id="agent:coordinator",
        sender_name="Coordinator",
        role="assistant",
        content=f'Okay, I sent this message to {recipient.name}:\n\n"{message_text}"',
        created_at=datetime.now(timezone.utc),
    )
    db.add(bot_msg)

    db.commit()
    publish_status(room.id, "notification_sent", {"recipient": recipient.name})
    return bot_msg




@app.post("/rooms/{room_id}/ask", response_model=RoomResponse)
def ask(room_id: str, payload: AskModeRequest, request: Request, db: Session = Depends(get_db)):
    user = require_current_user(request, db)

    room = db.get(RoomORM, room_id)
    room = ensure_room_access(db, user, room)

    publish_status(room_id, "ask_received", {"mode": payload.mode, "user": payload.user_name})
    logger.info("Ask received room_id=%s user_id=%s mode=%s", room_id, payload.user_id, payload.mode)

    # Save user message
    user_msg = MessageORM(
        id=str(uuid.uuid4()),
        room_id=room.id,
        sender_id=f"user:{user.id}",
        sender_name=user.name,
        role="user",
        content=payload.content,
        created_at=datetime.now(timezone.utc),
    )
    db.add(user_msg)
    db.commit()

    publish_status(room.id, "ask_received", {"mode": payload.mode})

    # 🔥 First: try to handle “Yes please send it” confirmations
    try:
        handled = maybe_send_approved_message(db, room, user, payload.content)
    except Exception as e:
        # Don’t crash the route if the helper misbehaves; just log and fall back to AI.
        print("Error in maybe_send_approved_message:", e)
        handled = None

    if handled:
        # We already created an assistant message + notification, no LLM call needed
        return room_to_response(db, room)

    # ⬇️ AI call ⬇️
    client = get_default_client()
    # Use lightweight system prompt builder (fallback)
    system_prompt = build_system_prompt_for_room(db, room, user, mode=payload.mode)
    user_prompt = payload.content

    try:
        publish_status(room.id, "routing_agent", {"agent": "Coordinator"})
        completion = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        answer = completion.choices[0].message.content or ""
    except Exception as e:
        print("AI call failed:", e)
        bot_msg = MessageORM(
            id=str(uuid.uuid4()),
            room_id=room.id,
            sender_id="agent:coordinator",
            sender_name="Coordinator",
            role="assistant",
            content="Something went wrong. Try again.",
            created_at=datetime.now(timezone.utc),
        )
        db.add(bot_msg)
        db.commit()
        publish_error(room.id, "ai_error", {"error": str(e)})
        return room_to_response(db, room)

    # Save assistant reply
    bot_msg = MessageORM(
        id=str(uuid.uuid4()),
        room_id=room.id,
        sender_id="agent:coordinator",
        sender_name="Coordinator",
        role="assistant",
        content=answer,
        created_at=datetime.now(timezone.utc),
    )
    db.add(bot_msg)
    db.commit()

    publish_status(room.id, "synthesis_complete", {})

    return room_to_response(db, room)

@app.get("/rooms/{room_id}/memory")
def get_memory(room_id: str, request: Request, db: Session = Depends(get_db)):
    user = require_user(request, db)
    room = db.get(RoomORM, room_id)
    if not room:
        raise HTTPException(404, "Room not found")
    ensure_room_access(db, user, room)

    notes = (
        db.query(MemoryORM)
        .filter(MemoryORM.room_id == room_id)
        .order_by(MemoryORM.created_at.desc())
        .limit(20)
        .all()
    )
    return {
        "project_summary": room.project_summary or "",
        "memory_summary": room.memory_summary or "",
        "notes": [m.content for m in notes],
        "count": len(notes),
    }


class MemoryQueryRequest(BaseModel):
    question: str


@app.post("/rooms/{room_id}/memory/query")
def query_memory(room_id: str, payload: MemoryQueryRequest, request: Request, db: Session = Depends(get_db)):
    """
    Small helper: asks the coordinator model ONLY using memory context.
    """
    user = require_user(request, db)

    room = db.get(RoomORM, room_id)
    if not room:
        raise HTTPException(404, "Room not found")
    ensure_room_access(db, user, room)

    notes = (
        db.query(MemoryORM)
        .filter(MemoryORM.room_id == room.id)
        .order_by(MemoryORM.created_at.desc())
        .limit(200)
        .all()
    )
    text = "\n".join(n.content for n in notes)

    system_prompt = f"""
You are the memory subsystem for room "{room.name}".
Only answer based on memory context below.
Never invent details.

Memory Context:
{text or "(empty)"}
    """

    client = CLIENTS["coordinator"]
    answer = run_ai(client, system_prompt, payload.question)

    # optional: log memory usage
    append_memory(db, room, agent_id="coordinator", content=f"Memory queried: {payload.question}", importance=0.05)
    db.commit()

    return {"answer": answer}
