"""
Parallel AI — simplified backend: two teammates (Sean, Yug), shared message log, team activity feed.
"""

import os
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, Request, Response, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from jose import jwt, JWTError
import bcrypt
from sqlalchemy.orm import Session

from database import SessionLocal, engine, Base
from models import User as UserORM, UserCredential as UserCredentialORM, Message as MessageORM, Activity as ActivityORM
from config import CLIENTS, OPENAI_MODEL

app = FastAPI(title="Parallel AI")

ALLOWED_ORIGINS = [
    "http://localhost:5173", "http://localhost:5174", "http://localhost:5175", "http://localhost:5176",
    "http://127.0.0.1:5173", "http://127.0.0.1:5174", "http://127.0.0.1:5175", "http://127.0.0.1:5176",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)


SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret")
ALGORITHM = "HS256"
ONLINE_SECONDS = 120  # last_seen within this = online


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


ACCESS_TOKEN_EXPIRE_MINUTES = 1440


def get_current_user(request: Request, db: Session) -> UserORM | None:
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


def touch_user_seen(db: Session, user: UserORM):
    user.last_seen_at = datetime.now(timezone.utc)
    db.add(user)
    db.commit()


# ----- Auth -----

class AuthLoginRequest(BaseModel):
    email: str
    password: str


class AuthRegisterRequest(BaseModel):
    email: str
    name: str
    password: str


class UserOut(BaseModel):
    id: str
    email: str
    name: str
    created_at: datetime

    class Config:
        from_attributes = True


@app.post("/auth/register", response_model=UserOut)
def register(payload: AuthRegisterRequest, response: Response, db: Session = Depends(get_db)):
    if db.query(UserORM).filter(UserORM.email == payload.email).first():
        raise HTTPException(400, "Email already registered")
    user = UserORM(
        id=str(uuid.uuid4()),
        email=payload.email,
        name=payload.name,
        created_at=datetime.now(timezone.utc),
        last_seen_at=datetime.now(timezone.utc),
    )
    db.add(user)
    db.add(UserCredentialORM(
        user_id=user.id,
        password_hash=hash_password(payload.password),
        created_at=datetime.now(timezone.utc),
    ))
    db.commit()
    db.refresh(user)
    token = create_access_token({"sub": user.id})
    resp = JSONResponse(content=UserOut.model_validate(user).model_dump(mode="json"))
    resp.set_cookie("access_token", token, httponly=True, secure=False, samesite="lax", path="/")
    return resp


@app.post("/auth/login")
def login(payload: AuthLoginRequest, response: Response, db: Session = Depends(get_db)):
    user = db.query(UserORM).filter(UserORM.email == payload.email).first()
    if not user:
        raise HTTPException(401, "Invalid credentials")
    cred = db.get(UserCredentialORM, user.id)
    if not cred or not verify_password(payload.password, cred.password_hash):
        raise HTTPException(401, "Invalid credentials")
    token = create_access_token({"sub": user.id})
    resp = JSONResponse({"ok": True})
    resp.set_cookie("access_token", token, httponly=True, secure=False, samesite="lax", path="/")
    return resp


@app.post("/auth/logout")
def logout(response: Response):
    resp = JSONResponse({"ok": True})
    resp.delete_cookie("access_token", path="/")
    return resp


@app.get("/me", response_model=UserOut)
def me(request: Request, db: Session = Depends(get_db)):
    user = require_user(request, db)
    touch_user_seen(db, user)
    return user


# ----- Online -----

@app.get("/online")
def online(request: Request, db: Session = Depends(get_db)):
    require_user(request, db)
    users = db.query(UserORM).all()
    now = datetime.now(timezone.utc)
    members = []
    for u in users:
        last = u.last_seen_at or u.created_at
        delta = (now - last).total_seconds() if last else 9999
        members.append({
            "id": u.id,
            "name": u.name,
            "online": delta <= ONLINE_SECONDS,
        })
    return {"members": members}


# ----- Chat -----

class ChatRequest(BaseModel):
    content: str


class MessageOut(BaseModel):
    id: str
    sender_id: str
    sender_name: str
    role: str
    content: str
    created_at: datetime

    class Config:
        from_attributes = True


def _client_for_user(user: UserORM):
    name_lower = (user.name or "").strip().lower()
    if name_lower == "sean":
        return CLIENTS.get("sean")
    if name_lower == "yug":
        return CLIENTS.get("yug")
    return CLIENTS.get("sean") or next(iter(CLIENTS.values()), None)


def _build_system_prompt(db: Session, user: UserORM) -> str:
    # Recent activity (last 15)
    activities = (
        db.query(ActivityORM)
        .order_by(ActivityORM.created_at.desc())
        .limit(15)
        .all()
    )
    activity_lines = []
    for a in reversed(activities):
        activity_lines.append(f"- {a.user_name}: {a.summary}")
    activity_text = "\n".join(activity_lines) if activity_lines else "(no activity yet)"

    # Last 30 messages from everyone (shared brain)
    messages = (
        db.query(MessageORM)
        .order_by(MessageORM.created_at.asc())
        .limit(30)
        .all()
    )
    history_lines = []
    for m in messages:
        speaker = m.sender_name or m.sender_id or "?"
        text = (m.content or "").strip()
        if len(text) > 300:
            text = text[:297] + "..."
        history_lines.append(f"{speaker}: {text}")
    history_text = "\n".join(history_lines) if history_lines else "(no messages yet)"

    return f"""You are {user.name}'s personal AI assistant in a team workspace. You and your teammate(s) each have your own agent. When your human asks about what a teammate is doing, use the team activity and conversation history below to answer.

== TEAM ACTIVITY (what teammates have been doing recently) ==
{activity_text}

== SHARED CONVERSATION (all messages in the workspace, oldest to newest) ==
{history_text}

You speak only to {user.name}. Refer to teammates by name (e.g. "your teammate Yug"). If asked what someone else is working on, summarize from the activity and conversation above.""".strip()


@app.post("/chat", response_model=MessageOut)
def chat(payload: ChatRequest, request: Request, db: Session = Depends(get_db)):
    user = require_user(request, db)
    touch_user_seen(db, user)
    content = (payload.content or "").strip()
    if not content:
        raise HTTPException(400, "Empty message")

    client = _client_for_user(user)
    if not client:
        raise HTTPException(500, "No OpenAI client configured for this user")

    # Save user message (global log, tied to this user)
    user_msg = MessageORM(
        id=str(uuid.uuid4()),
        user_id=user.id,
        sender_id=f"user:{user.id}",
        sender_name=user.name,
        role="user",
        content=content,
        created_at=datetime.now(timezone.utc),
    )
    db.add(user_msg)
    db.commit()

    # Build prompt and call OpenAI
    system_prompt = _build_system_prompt(db, user)
    try:
        completion = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": content},
            ],
        )
        answer = (completion.choices[0].message.content or "").strip() or "No response."
    except Exception as e:
        db.rollback()
        raise HTTPException(502, f"OpenAI error: {e}")

    # Save assistant message
    bot_msg = MessageORM(
        id=str(uuid.uuid4()),
        user_id=user.id,
        sender_id=f"agent:{user.id}",
        sender_name=f"{user.name}'s Agent",
        role="assistant",
        content=answer,
        created_at=datetime.now(timezone.utc),
    )
    db.add(bot_msg)

    # One-line activity summary (no extra API call: use truncated user message)
    summary = content if len(content) <= 80 else content[:77] + "..."
    activity = ActivityORM(
        id=str(uuid.uuid4()),
        user_id=user.id,
        user_name=user.name,
        summary=summary,
        created_at=datetime.now(timezone.utc),
    )
    db.add(activity)
    db.commit()
    db.refresh(bot_msg)

    return bot_msg


@app.get("/messages", response_model=list[MessageOut])
def get_messages(request: Request, db: Session = Depends(get_db)):
    user = require_user(request, db)
    touch_user_seen(db, user)
    messages = (
        db.query(MessageORM)
        .filter(MessageORM.user_id == user.id)
        .order_by(MessageORM.created_at.asc())
        .all()
    )
    return messages


# ----- Activity feed -----

class ActivityOut(BaseModel):
    id: str
    user_id: str
    user_name: str
    summary: str
    created_at: datetime

    class Config:
        from_attributes = True


@app.get("/activity", response_model=list[ActivityOut])
def get_activity(request: Request, db: Session = Depends(get_db)):
    require_user(request, db)
    activities = (
        db.query(ActivityORM)
        .order_by(ActivityORM.created_at.desc())
        .limit(50)
        .all()
    )
    return activities
