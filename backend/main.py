"""
Parallel AI — two-agent collaborative workspace with AGI research, Composio actions, Plivo voice.
Includes real-time Pipecat voice agent via Gemini Live.
"""

import os
import uuid
import time
import traceback
from datetime import datetime, timedelta, timezone
from typing import Optional

import requests as http_requests
from fastapi import FastAPI, Request, Response, Depends, HTTPException, Form, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel
from jose import jwt, JWTError
import bcrypt
from sqlalchemy.orm import Session
from loguru import logger

from database import SessionLocal, engine, Base
from models import (
    User as UserORM,
    UserCredential as UserCredentialORM,
    Message as MessageORM,
    Activity as ActivityORM,
)
from config import (
    CLIENTS, OPENAI_MODEL,
    AGI_API_KEY, AGI_BASE_URL,
    COMPOSIO_API_KEY, get_composio_client,
    PLIVO_AUTH_ID, PLIVO_AUTH_TOKEN, PLIVO_PHONE_NUMBER, PLIVO_CLIENT,
    PLIVO_APP_ID, TUNNEL_PUBLIC_URL,
    GEMINI_API_KEY,
)

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
ACCESS_TOKEN_EXPIRE_MINUTES = 1440
ONLINE_SECONDS = 120


# ───────────────────────── helpers ─────────────────────────

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False


def create_access_token(data: dict):
    to_encode = data.copy()
    to_encode["exp"] = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(request: Request, db: Session) -> UserORM | None:
    token = request.cookies.get("access_token")
    if not token:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return db.get(UserORM, payload.get("sub"))
    except JWTError:
        return None


def require_user(request: Request, db: Session) -> UserORM:
    user = get_current_user(request, db)
    if not user:
        raise HTTPException(401, "Not authenticated")
    return user


def touch(db: Session, user: UserORM):
    user.last_seen_at = datetime.now(timezone.utc)
    db.add(user)
    db.commit()


def _client_for_user(user: UserORM):
    name = (user.name or "").strip().lower()
    return CLIENTS.get(name) or CLIENTS.get("sean") or next(iter(CLIENTS.values()), None)


def _save_msg(db, user_id, sender_id, sender_name, role, content):
    msg = MessageORM(
        id=str(uuid.uuid4()), user_id=user_id, sender_id=sender_id,
        sender_name=sender_name, role=role, content=content,
        created_at=datetime.now(timezone.utc),
    )
    db.add(msg)
    return msg


def _save_activity(db, user_id, user_name, summary):
    db.add(ActivityORM(
        id=str(uuid.uuid4()), user_id=user_id, user_name=user_name,
        summary=summary, created_at=datetime.now(timezone.utc),
    ))


def _build_system_prompt(db: Session, user: UserORM) -> str:
    activities = db.query(ActivityORM).order_by(ActivityORM.created_at.desc()).limit(15).all()
    activity_text = "\n".join(f"- {a.user_name}: {a.summary}" for a in reversed(activities)) or "(none)"
    messages = db.query(MessageORM).order_by(MessageORM.created_at.asc()).limit(30).all()
    history = "\n".join(f"{m.sender_name}: {m.content[:300]}" for m in messages) or "(none)"
    return f"""You are {user.name}'s personal AI assistant in a team workspace.

== TEAM ACTIVITY ==
{activity_text}

== SHARED CONVERSATION ==
{history}

You speak only to {user.name}. Refer to teammates by name. If asked what someone is working on, use the activity and conversation above.

TOOLS AVAILABLE (mention these when relevant):
- Research: user can click "Research" to have an AGI web agent look things up in real time.
- Actions: user can click "Action" to trigger Composio actions (send email, create calendar event, etc.).
- Voice: teammates can call +1{PLIVO_PHONE_NUMBER or ''} to talk to their agent by phone."""


# ───────────────────────── auth ─────────────────────────

class AuthLogin(BaseModel):
    email: str
    password: str


class AuthRegister(BaseModel):
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


@app.post("/auth/register")
def register(p: AuthRegister, db: Session = Depends(get_db)):
    if db.query(UserORM).filter(UserORM.email == p.email).first():
        raise HTTPException(400, "Email already registered")
    user = UserORM(id=str(uuid.uuid4()), email=p.email, name=p.name,
                   created_at=datetime.now(timezone.utc), last_seen_at=datetime.now(timezone.utc))
    db.add(user)
    db.add(UserCredentialORM(user_id=user.id, password_hash=hash_password(p.password),
                             created_at=datetime.now(timezone.utc)))
    db.commit()
    db.refresh(user)
    resp = JSONResponse(content=UserOut.model_validate(user).model_dump(mode="json"))
    resp.set_cookie("access_token", create_access_token({"sub": user.id}),
                    httponly=True, secure=False, samesite="lax", path="/")
    return resp


@app.post("/auth/login")
def login(p: AuthLogin, db: Session = Depends(get_db)):
    user = db.query(UserORM).filter(UserORM.email == p.email).first()
    if not user:
        raise HTTPException(401, "Invalid credentials")
    cred = db.get(UserCredentialORM, user.id)
    if not cred or not verify_password(p.password, cred.password_hash):
        raise HTTPException(401, "Invalid credentials")
    resp = JSONResponse({"ok": True})
    resp.set_cookie("access_token", create_access_token({"sub": user.id}),
                    httponly=True, secure=False, samesite="lax", path="/")
    return resp


@app.post("/auth/logout")
def logout():
    resp = JSONResponse({"ok": True})
    resp.delete_cookie("access_token", path="/")
    return resp


@app.get("/me", response_model=UserOut)
def me(request: Request, db: Session = Depends(get_db)):
    user = require_user(request, db)
    touch(db, user)
    return user


# ───────────────────────── online ─────────────────────────

@app.get("/online")
def online(request: Request, db: Session = Depends(get_db)):
    require_user(request, db)
    now = datetime.now(timezone.utc)
    members = []
    # Return all users (Sean, Yug, etc.) so team roster and online status are visible
    users = db.query(UserORM).order_by(UserORM.name).all()
    for u in users:
        last = u.last_seen_at or u.created_at
        if last and last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        delta = (now - last).total_seconds() if last else 9999
        members.append({"id": u.id, "name": u.name or "Unknown", "online": delta <= ONLINE_SECONDS})
    return {"members": members}


# ───────────────────────── chat ─────────────────────────

class ChatRequest(BaseModel):
    content: str
    mode: str = "chat"  # "chat" | "research" | "action"
    action_tool: Optional[str] = None  # e.g. "GMAIL_SEND_EMAIL"


class MessageOut(BaseModel):
    id: str
    sender_id: str
    sender_name: str
    role: str
    content: str
    created_at: datetime
    class Config:
        from_attributes = True


@app.post("/chat", response_model=MessageOut)
def chat(payload: ChatRequest, request: Request, db: Session = Depends(get_db)):
    user = require_user(request, db)
    touch(db, user)
    content = (payload.content or "").strip()
    if not content:
        raise HTTPException(400, "Empty message")

    # Save user message
    _save_msg(db, user.id, f"user:{user.id}", user.name, "user", content)
    db.commit()

    mode = payload.mode or "chat"

    # ── RESEARCH MODE (AGI REST API) ──
    if mode == "research":
        answer = _do_agi_research(content, user)
        tag = "[AGI Research] "
    # ── ACTION MODE (Composio) ──
    elif mode == "action":
        answer = _do_composio_action(user, content, tool_name=payload.action_tool, db=db)
        tag = "[Composio Action] "
    # ── NORMAL CHAT ──
    else:
        answer = _do_chat(db, user, content)
        tag = ""

    bot_msg = _save_msg(db, user.id, f"agent:{user.id}", f"{user.name}'s Agent",
                        "assistant", tag + answer)
    _save_activity(db, user.id, user.name,
                   (f"[{mode}] " if mode != "chat" else "") + content[:70] + ("..." if len(content) > 70 else ""))
    db.commit()
    db.refresh(bot_msg)
    return bot_msg


def _do_chat(db, user, content):
    client = _client_for_user(user)
    if not client:
        return "No AI client configured."
    prompt = _build_system_prompt(db, user)
    try:
        comp = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "system", "content": prompt}, {"role": "user", "content": content}],
        )
        return (comp.choices[0].message.content or "").strip() or "No response."
    except Exception as e:
        return f"OpenAI error: {e}"


# ───────────────────── AGI research (REST API) ─────────────────────

def _do_agi_research(query: str, user: UserORM) -> str:
    """Use AGI Inc. REST API to research a topic with a browser agent."""
    if not AGI_API_KEY:
        return "AGI API key not configured. Add AGI_API_KEY to your .env"
    headers = {"Authorization": f"Bearer {AGI_API_KEY}", "Content-Type": "application/json"}

    try:
        # 1. Create a session (API returns 201 Created on success)
        r = http_requests.post(f"{AGI_BASE_URL}/sessions",
                               headers=headers,
                               json={"agent_name": "agi-0"},
                               timeout=30)
        if r.status_code not in (200, 201):
            return f"AGI session creation failed ({r.status_code}): {r.text[:200]}"
        session_data = r.json()
        session_id = session_data.get("session_id") or session_data.get("id")
        if not session_id:
            return f"AGI returned no session ID: {r.text[:200]}"

        # 2. Send the research task
        r2 = http_requests.post(f"{AGI_BASE_URL}/sessions/{session_id}/message",
                                headers=headers,
                                json={"message": f"Research the following and return a concise summary with key findings: {query}"},
                                timeout=30)
        if r2.status_code not in (200, 201, 202):
            return f"AGI task send failed ({r2.status_code}): {r2.text[:200]}"

        # 3. Poll for completion (up to 90 seconds)
        for _ in range(45):
            time.sleep(2)
            r3 = http_requests.get(f"{AGI_BASE_URL}/sessions/{session_id}/status",
                                   headers=headers, timeout=15)
            if r3.status_code != 200:
                continue
            status = r3.json().get("status", "")
            if status in ("finished", "done", "completed"):
                # Get result messages
                r4 = http_requests.get(f"{AGI_BASE_URL}/sessions/{session_id}/messages",
                                       headers=headers, timeout=15)
                if r4.status_code == 200:
                    msgs = r4.json().get("messages", [])
                    # Find the DONE/result message
                    for m in reversed(msgs):
                        if m.get("type") in ("DONE", "done", "result", "assistant"):
                            content = m.get("content") or m.get("message") or m.get("text") or ""
                            if content:
                                return content[:3000]
                    # Fallback: return last message
                    if msgs:
                        last = msgs[-1]
                        return str(last.get("content") or last.get("message") or last)[:3000]
                return "Research complete but no result text found."
            elif status in ("error", "failed"):
                return f"AGI research failed with status: {status}"

        # Cleanup
        try:
            http_requests.delete(f"{AGI_BASE_URL}/sessions/{session_id}",
                                 headers=headers, timeout=10)
        except Exception:
            pass
        return "AGI research timed out after 90s. The query may have been too complex."

    except Exception as e:
        traceback.print_exc()
        return f"AGI research error: {e}"


# ───────────────────── Composio actions ─────────────────────

ALL_COMPOSIO_TOOLS = [
    "GMAIL_SEND_EMAIL",
    "GMAIL_FETCH_EMAILS",
    "GMAIL_CREATE_EMAIL_DRAFT",
    "GOOGLEDOCS_CREATE_DOCUMENT",
    "GOOGLEDRIVE_FIND_FILE",
    "GOOGLEDRIVE_CREATE_FILE",
    "GOOGLECALENDAR_CREATE_EVENT",
    "GOOGLECALENDAR_FIND_EVENT",
]


def _do_composio_action(user: UserORM, content: str, tool_name: str = None, db: Session = None) -> str:
    """Use Composio to execute an action via OpenAI function calling.
    Includes recent chat history so the AI knows 'that' / 'the transcript' etc."""
    composio = get_composio_client()
    if not composio:
        return "Composio not configured. Add COMPOSIO_API_KEY to .env"

    user_id = f"parallel-{user.name.lower()}"

    try:
        # If a specific tool was requested, try that first; otherwise load all tools
        if tool_name:
            requested_tools = [tool_name]
        else:
            requested_tools = ALL_COMPOSIO_TOOLS

        # Gather all available tools — skip ones that fail (not connected)
        tools = []
        for t in requested_tools:
            try:
                got = composio.tools.get(user_id=user_id, tools=[t])
                if got:
                    tools.extend(got)
            except Exception:
                pass  # toolkit not connected, skip it

        if not tools:
            return ("No Composio tools available. Make sure you've connected your accounts "
                    "(Gmail, Google Docs, Google Drive) using the Connect buttons in the sidebar.")

        # Call OpenAI with ALL available tools so it picks the right one
        client = _client_for_user(user)
        if not client:
            return "No OpenAI client for Composio action."

        # Build context from recent messages so "put that into a doc" works
        recent_context = ""
        if db:
            recent_msgs = (
                db.query(MessageORM)
                .filter(MessageORM.user_id == user.id)
                .order_by(MessageORM.created_at.desc())
                .limit(10)
                .all()
            )
            if recent_msgs:
                recent_context = "\n".join(
                    f"{m.sender_name}: {m.content[:500]}" for m in reversed(recent_msgs)
                )

        system_msg = (
            "You are an AI assistant that executes actions using connected tools. "
            "When the user asks you to do something, ALWAYS call the appropriate tool. "
            "Do NOT just describe what you would do — actually call the tool.\n\n"
            "If the user refers to 'that', 'the transcript', 'the exchange', or 'the conversation', "
            "use the recent chat history below as the content.\n\n"
        )
        if recent_context:
            system_msg += f"== RECENT CHAT HISTORY ==\n{recent_context}\n"

        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            tools=tools,
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": content},
            ],
        )

        # Let Composio handle the tool calls
        result = composio.provider.handle_tool_calls(response=response, user_id=user_id)
        if result:
            return str(result)[:2000]
        # If no tool call was made, return the text response
        text = (response.choices[0].message.content or "").strip()
        return text or "Action processed (no tool call was needed)."

    except Exception as e:
        traceback.print_exc()
        err = str(e)
        if "connected account" in err.lower() or "connection" in err.lower():
            return (f"Composio error: No connected account found. "
                    f"Click 'Connect' in the sidebar to authenticate, then try again.")
        return f"Composio action error: {err[:500]}"


# ───────────────────── Composio connection management ─────────────────────

@app.get("/composio/tools")
def composio_list_tools(request: Request, db: Session = Depends(get_db)):
    """List available Composio toolkits."""
    require_user(request, db)
    return {
        "toolkits": [
            {"name": "GMAIL_SEND_EMAIL", "label": "Send Email (Gmail)", "toolkit": "GMAIL"},
            {"name": "GMAIL_FETCH_EMAILS", "label": "Fetch Emails (Gmail)", "toolkit": "GMAIL"},
            {"name": "GMAIL_CREATE_EMAIL_DRAFT", "label": "Draft Email (Gmail)", "toolkit": "GMAIL"},
            {"name": "GOOGLEDOCS_CREATE_DOCUMENT", "label": "Create Google Doc", "toolkit": "GOOGLEDOCS"},
            {"name": "GOOGLEDRIVE_FIND_FILE", "label": "Find File (Drive)", "toolkit": "GOOGLEDRIVE"},
            {"name": "GOOGLECALENDAR_CREATE_EVENT", "label": "Create Calendar Event", "toolkit": "GOOGLECALENDAR"},
            {"name": "GOOGLECALENDAR_FIND_EVENT", "label": "Find Calendar Event", "toolkit": "GOOGLECALENDAR"},
            {"name": "SLACK_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL", "label": "Send Slack Message", "toolkit": "SLACK"},
            {"name": "GITHUB_CREATE_AN_ISSUE", "label": "Create GitHub Issue", "toolkit": "GITHUB"},
        ]
    }


class ConnectRequest(BaseModel):
    toolkit: str = "GMAIL"


@app.post("/composio/connect")
def composio_connect(payload: ConnectRequest, request: Request, db: Session = Depends(get_db)):
    """Initiate OAuth connection for a Composio toolkit. Returns a redirect URL."""
    user = require_user(request, db)
    composio = get_composio_client()
    if not composio:
        raise HTTPException(500, "Composio not configured")

    user_id = f"parallel-{user.name.lower()}"
    toolkit = str(payload.toolkit).upper().strip()

    try:
        # Find existing auth config for this toolkit
        auth_configs = composio.auth_configs.list()
        target_config = None
        for ac in auth_configs.items:
            ac_toolkit = str(ac.toolkit).upper().strip() if ac.toolkit else ""
            if ac_toolkit == toolkit:
                target_config = ac
                break

        if not target_config:
            # Create with Composio managed auth
            target_config = composio.auth_configs.create(
                toolkit=toolkit,
                options={"type": "use_composio_managed_auth"},
            )

        # Initiate the connection
        connection = composio.connected_accounts.initiate(
            user_id=user_id,
            auth_config_id=target_config.id,
        )

        return {
            "connection_id": connection.id,
            "redirect_url": connection.redirect_url,
            "toolkit": toolkit,
            "status": "pending",
        }
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, f"Connection error: {e}")


@app.get("/composio/status")
def composio_status(request: Request, db: Session = Depends(get_db)):
    """Check if current user has active Composio connected accounts."""
    user = require_user(request, db)
    composio = get_composio_client()
    if not composio:
        return {"connected": False, "reason": "Composio not configured"}

    user_id = f"parallel-{user.name.lower()}"

    try:
        accounts = composio.connected_accounts.list(
            user_ids=[user_id],
        )
        active = [a for a in accounts.items if str(a.status).upper() == "ACTIVE"]
        # Extract clean toolkit name from objects like ItemToolkit(slug='GMAIL')
        def _clean_toolkit(t):
            s = str(t).upper().strip()
            # Handle ItemToolkit(SLUG='GMAIL') format
            import re
            m = re.search(r"SLUG=['\"]?([A-Z_]+)['\"]?", s)
            if m:
                return m.group(1)
            return s
        toolkits = list(set(_clean_toolkit(a.toolkit) for a in active if a.toolkit))
        return {
            "connected": len(active) > 0,
            "active_count": len(active),
            "toolkits": toolkits,
        }
    except Exception as e:
        return {"connected": False, "reason": str(e)}


@app.get("/messages", response_model=list[MessageOut])
def get_messages(request: Request, db: Session = Depends(get_db)):
    user = require_user(request, db)
    touch(db, user)
    return (db.query(MessageORM).filter(MessageORM.user_id == user.id)
            .order_by(MessageORM.created_at.asc()).all())


# ───────────────── summary: Google Doc + email ─────────────────


class SummaryRequest(BaseModel):
    email_to: str  # email address to send the summary to


@app.post("/summary/generate")
def generate_summary(payload: SummaryRequest, request: Request, db: Session = Depends(get_db)):
    """
    1. Summarize the entire chat history via OpenAI
    2. Create a Google Doc with the summary via Composio
    3. Email the doc link to the recipient via Composio/Gmail
    """
    user = require_user(request, db)
    touch(db, user)
    composio = get_composio_client()
    if not composio:
        raise HTTPException(500, "Composio not configured")

    user_id = f"parallel-{user.name.lower()}"
    client = _client_for_user(user)
    if not client:
        raise HTTPException(500, "No OpenAI client configured")

    # ── Step 1: Gather all messages and build a summary ──
    all_msgs = db.query(MessageORM).order_by(MessageORM.created_at.asc()).all()
    if not all_msgs:
        raise HTTPException(400, "No messages to summarize")

    conversation_text = "\n".join(
        f"[{m.created_at.strftime('%Y-%m-%d %H:%M')}] {m.sender_name} ({m.role}): {m.content}"
        for m in all_msgs
    )

    # Use OpenAI to create a structured summary
    try:
        summary_resp = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": (
                    "You are a professional report writer. Summarize the following team workspace conversation "
                    "into a well-structured report. Include:\n"
                    "- Executive Summary (2-3 sentences)\n"
                    "- Key Topics Discussed\n"
                    "- Action Items / Decisions Made\n"
                    "- Participant Summary (who said what)\n"
                    "- Timeline of Events\n\n"
                    "Format it nicely with headers and bullet points."
                )},
                {"role": "user", "content": f"Here is the conversation:\n\n{conversation_text[:8000]}"},
            ],
        )
        summary_text = (summary_resp.choices[0].message.content or "").strip()
    except Exception as e:
        raise HTTPException(502, f"Failed to generate summary: {e}")

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    doc_title = f"Parallel AI - Team Summary - {now_str}"

    results = {"summary": summary_text, "steps": []}

    # ── Step 2: Create Google Doc ──
    doc_url = None
    try:
        tools = composio.tools.get(user_id=user_id, tools=["GOOGLEDOCS_CREATE_DOCUMENT"])
        if tools:
            doc_resp = client.chat.completions.create(
                model=OPENAI_MODEL,
                tools=tools,
                messages=[{"role": "user", "content": (
                    f"Create a new Google Doc with the title '{doc_title}' and the following content:\n\n{summary_text}"
                )}],
            )
            doc_result = composio.provider.handle_tool_calls(response=doc_resp, user_id=user_id)
            results["steps"].append({"step": "google_doc", "status": "success", "result": str(doc_result)[:500]})

            # Try to extract the doc URL from the result
            result_str = str(doc_result)
            if "docs.google.com" in result_str:
                import re
                url_match = re.search(r'https://docs\.google\.com/[^\s\'"]+', result_str)
                if url_match:
                    doc_url = url_match.group(0)
            elif "documentId" in result_str or "document_id" in result_str:
                import re
                id_match = re.search(r'[\'"]?(?:documentId|document_id)[\'"]?\s*[:=]\s*[\'"]([a-zA-Z0-9_-]+)[\'"]', result_str)
                if id_match:
                    doc_url = f"https://docs.google.com/document/d/{id_match.group(1)}/edit"
        else:
            results["steps"].append({"step": "google_doc", "status": "skipped", "reason": "Google Docs not connected"})
    except Exception as e:
        traceback.print_exc()
        results["steps"].append({"step": "google_doc", "status": "error", "error": str(e)[:300]})

    # ── Step 3: Email the summary + doc link ──
    try:
        email_body = f"Hi,\n\nHere is the team workspace summary from Parallel AI:\n\n"
        email_body += f"{'='*50}\n{summary_text}\n{'='*50}\n\n"
        if doc_url:
            email_body += f"Google Doc: {doc_url}\n\n"
        email_body += f"Generated by Parallel AI on {now_str}"

        tools = composio.tools.get(user_id=user_id, tools=["GMAIL_SEND_EMAIL"])
        if tools:
            email_resp = client.chat.completions.create(
                model=OPENAI_MODEL,
                tools=tools,
                messages=[{"role": "user", "content": (
                    f"Send an email to {payload.email_to} with the subject '{doc_title}' "
                    f"and the following body:\n\n{email_body}"
                )}],
            )
            email_result = composio.provider.handle_tool_calls(response=email_resp, user_id=user_id)
            results["steps"].append({"step": "email", "status": "success", "result": str(email_result)[:300]})
        else:
            results["steps"].append({"step": "email", "status": "skipped", "reason": "Gmail not connected"})
    except Exception as e:
        traceback.print_exc()
        results["steps"].append({"step": "email", "status": "error", "error": str(e)[:300]})

    # Log activity
    _save_activity(db, user.id, user.name, f"[Summary] Generated & emailed to {payload.email_to}")
    _save_msg(db, user.id, f"agent:{user.id}", f"{user.name}'s Agent", "assistant",
              f"[Summary Report] Created summary with {len(all_msgs)} messages. "
              f"{'Google Doc created. ' if doc_url else ''}"
              f"Emailed to {payload.email_to}.")
    db.commit()

    if doc_url:
        results["doc_url"] = doc_url
    return results


# ───────────────────────── activity ─────────────────────────

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
    return db.query(ActivityORM).order_by(ActivityORM.created_at.desc()).limit(50).all()


# ───────────────────────── tools info ─────────────────────────

@app.get("/tools")
def get_tools(request: Request, db: Session = Depends(get_db)):
    """Return which sponsor tools are configured."""
    require_user(request, db)
    voice_mode = "live" if (GEMINI_API_KEY and TUNNEL_PUBLIC_URL) else "record"
    return {
        "agi": {"enabled": bool(AGI_API_KEY), "description": "Web research via AGI browser agent (REST API)"},
        "composio": {"enabled": bool(COMPOSIO_API_KEY), "description": "Execute actions in apps (email, calendar, etc.)"},
        "plivo": {
            "enabled": bool(PLIVO_CLIENT),
            "phone_number": PLIVO_PHONE_NUMBER or None,
            "description": "Call your agent by phone",
            "voice_mode": voice_mode,
        },
        "tunnel_url": TUNNEL_PUBLIC_URL,
        "gemini_voice": {"enabled": bool(GEMINI_API_KEY), "description": "Real-time voice AI via Gemini Live + Pipecat"},
    }


@app.get("/tunnel")
def tunnel_status(request: Request, db: Session = Depends(get_db)):
    """Return the current public tunnel URL for voice/SMS webhooks. Use this link to verify the tunnel is up."""
    require_user(request, db)
    return {"url": TUNNEL_PUBLIC_URL, "ok": bool(TUNNEL_PUBLIC_URL)}


@app.post("/plivo/update-webhooks")
def plivo_update_webhooks(request: Request, db: Session = Depends(get_db)):
    """Update Plivo app with current TUNNEL_PUBLIC_URL (answer, hangup, message). Call after starting cloudflared."""
    require_user(request, db)
    if not TUNNEL_PUBLIC_URL:
        raise HTTPException(400, "Set TUNNEL_PUBLIC_URL in .env and restart the backend")
    if not PLIVO_CLIENT:
        raise HTTPException(500, "Plivo not configured")
    base = TUNNEL_PUBLIC_URL.rstrip("/")
    try:
        PLIVO_CLIENT.applications.update(
            PLIVO_APP_ID,
            answer_url=f"{base}/voice/incoming",
            answer_method="POST",
            hangup_url=f"{base}/voice/hangup",
            hangup_method="POST",
            message_url=f"{base}/sms/incoming",
            message_method="POST",
        )
        return {"ok": True, "tunnel_url": base}
    except Exception as e:
        raise HTTPException(500, str(e))


# ───────────────────────── Plivo voice webhooks ─────────────────────────

@app.post("/voice/incoming")
@app.get("/voice/incoming")
def voice_incoming(request: Request):
    """Plivo calls this URL when someone dials our number (answer URL)."""
    base = (TUNNEL_PUBLIC_URL or "").rstrip("/")
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <GetDigits action="{base}/voice/identify" method="POST" timeout="10" numDigits="1" retries="2">
        <Speak voice="Polly.Matthew">
            Welcome to Parallel A I. Press 1 if you are Sean. Press 2 if you are Yug.
        </Speak>
    </GetDigits>
    <Speak voice="Polly.Matthew">No input received. Goodbye.</Speak>
</Response>"""
    return PlainTextResponse(content=xml, media_type="text/xml")


@app.post("/voice/hangup")
@app.get("/voice/hangup")
async def voice_hangup(request: Request):
    """Plivo calls this when a call ends (hangup callback)."""
    try:
        form = await request.form()
        call_uuid = form.get("CallUUID", "")
        caller = form.get("To", "")
        logger.info(f"Hangup callback: CallUUID={call_uuid}")
    except Exception:
        pass
    return JSONResponse({"ok": True})


@app.post("/voice/identify")
async def voice_identify(request: Request):
    """After user presses 1 or 2, connect to live AI agent via Pipecat/Gemini (or fallback to Record)."""
    form = await request.form()
    digits = form.get("Digits", "")
    call_uuid = form.get("CallUUID", "") or form.get("call_uuid", "")
    name = "Sean" if digits == "1" else "Yug" if digits == "2" else "Unknown"

    logger.info(f"voice/identify: caller={name}, CallUUID={call_uuid}, Digits={digits}")

    base = (TUNNEL_PUBLIC_URL or "").rstrip("/")

    # If tunnel is available, use bidirectional Stream for live Pipecat voice agent
    if TUNNEL_PUBLIC_URL:
        ws_host = TUNNEL_PUBLIC_URL.replace("https://", "").replace("http://", "").rstrip("/")
        # Pass call_uuid in the WebSocket URL so we can start recording
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Speak voice="Polly.Matthew">Hi {name}. Connecting you to your AI agent now.</Speak>
    <Stream bidirectional="true" keepCallAlive="true"
            contentType="audio/x-mulaw;rate=8000"
            streamTimeout="86400">wss://{ws_host}/voice/ws?caller={name}&amp;call_uuid={call_uuid}</Stream>
</Response>"""
    else:
        # Fallback: record-and-transcribe
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Speak voice="Polly.Matthew">Hi {name}. After the beep, say your message and I will process it.</Speak>
    <Record action="{base}/voice/process?caller={name}" method="POST" maxLength="30"
            transcriptionType="auto" transcriptionUrl="{base}/voice/transcription?caller={name}"
            transcriptionMethod="POST" />
    <Speak voice="Polly.Matthew">I did not hear anything. Goodbye.</Speak>
</Response>"""
    return PlainTextResponse(content=xml, media_type="text/xml")


@app.post("/voice/transcription")
async def voice_transcription(request: Request):
    """Plivo sends the transcription here. Process through chat and log it."""
    form = await request.form()
    caller = request.query_params.get("caller", "Unknown")
    transcription = form.get("transcription", "")
    if not transcription:
        return {"ok": False, "reason": "no transcription"}

    db = SessionLocal()
    try:
        user = db.query(UserORM).filter(UserORM.name == caller).first()
        if not user:
            return {"ok": False, "reason": f"user {caller} not found"}
        _save_msg(db, user.id, f"voice:{user.id}", f"{user.name} (voice)", "user", transcription)
        _save_activity(db, user.id, user.name, f"[Voice] {transcription[:60]}")
        answer = _do_chat(db, user, transcription)
        _save_msg(db, user.id, f"agent:{user.id}", f"{user.name}'s Agent", "assistant", f"[Voice reply] {answer}")
        db.commit()
    finally:
        db.close()
    return {"ok": True}


@app.post("/voice/process")
async def voice_process(request: Request):
    """After recording, speak a confirmation."""
    caller = request.query_params.get("caller", "Unknown")
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Speak voice="Polly.Matthew">
        Thanks {caller}. Your message is being processed by your Parallel agent. Check the dashboard for the response. Goodbye.
    </Speak>
</Response>"""
    return PlainTextResponse(content=xml, media_type="text/xml")


# ───────────────────────── Plivo SMS ─────────────────────────

@app.post("/sms/incoming")
async def sms_incoming(request: Request):
    """Handle incoming SMS."""
    form = await request.form()
    sender = form.get("From", "")
    text = (form.get("Text", "") or "").strip()
    if not text:
        return {"ok": False}

    db = SessionLocal()
    try:
        user = None
        for name in ["Sean", "Yug"]:
            if text.lower().startswith(name.lower()):
                user = db.query(UserORM).filter(UserORM.name == name).first()
                text = text[len(name):].strip().lstrip(":").strip()
                break
        if not user:
            user = db.query(UserORM).first()
        if user and text:
            _save_msg(db, user.id, f"sms:{sender}", f"{user.name} (SMS)", "user", text)
            _save_activity(db, user.id, user.name, f"[SMS] {text[:60]}")
            answer = _do_chat(db, user, text)
            _save_msg(db, user.id, f"agent:{user.id}", f"{user.name}'s Agent", "assistant", f"[SMS reply] {answer}")
            db.commit()
            if PLIVO_CLIENT and PLIVO_PHONE_NUMBER:
                try:
                    PLIVO_CLIENT.messages.create(src=PLIVO_PHONE_NUMBER, dst=sender, text=answer[:1600])
                except Exception as e:
                    print(f"SMS reply error: {e}")
    finally:
        db.close()
    return {"ok": True}


# ───────────────────────── Pipecat voice WebSocket ─────────────────────────


def _start_plivo_recording(call_uuid: str) -> bool:
    """Start recording a live Plivo call via REST API. Returns True on success."""
    if not PLIVO_CLIENT or not call_uuid:
        return False
    try:
        base = (TUNNEL_PUBLIC_URL or "").rstrip("/")
        PLIVO_CLIENT.calls.record(
            call_uuid,
            callback_url=f"{base}/voice/recording-callback",
            callback_method="POST",
            file_format="mp3",
        )
        logger.info(f"Started Plivo recording for call {call_uuid}")
        return True
    except Exception as e:
        logger.warning(f"Could not start call recording: {e}")
        return False


def _fetch_and_transcribe_recording(call_uuid: str, caller_name: str):
    """After call ends, fetch the Plivo recording and transcribe with OpenAI Whisper."""
    import time as _time

    if not PLIVO_CLIENT or not call_uuid:
        logger.info("No Plivo client or call UUID — skipping transcription")
        return

    # Wait for Plivo to process the recording — check at 2s, then every 1.5s (faster)
    recording_url = None
    for attempt in range(10):
        _time.sleep(2 if attempt == 0 else 1.5)
        try:
            auth = (PLIVO_AUTH_ID, PLIVO_AUTH_TOKEN)
            r = http_requests.get(
                f"https://api.plivo.com/v1/Account/{PLIVO_AUTH_ID}/Recording/",
                auth=auth,
                params={"call_uuid": call_uuid, "limit": 5},
                timeout=15,
            )
            if r.status_code == 200:
                recordings = r.json().get("objects", [])
                if recordings:
                    recording_url = recordings[0].get("recording_url")
                    if recording_url:
                        logger.info(f"Found recording: {recording_url}")
                        break
        except Exception as e:
            logger.warning(f"Recording fetch attempt {attempt+1}: {e}")

    if not recording_url:
        logger.warning(f"No recording found for call {call_uuid} after polling")
        # Still save a message about the call
        _save_msg_sync(
            caller_name,
            "[Voice Call] Call completed but recording was not available for transcription. "
            "Use the save_to_workspace tool during calls to capture important points.",
            "assistant",
        )
        return

    # Download the recording
    try:
        logger.info(f"Downloading recording from {recording_url}")
        audio_resp = http_requests.get(recording_url, timeout=60)
        if audio_resp.status_code != 200:
            logger.error(f"Recording download failed: {audio_resp.status_code}")
            return
        audio_data = audio_resp.content
    except Exception as e:
        logger.error(f"Recording download error: {e}")
        return

    # Transcribe with OpenAI Whisper
    try:
        client = CLIENTS.get(caller_name.lower()) or CLIENTS.get("sean") or next(iter(CLIENTS.values()), None)
        if not client:
            logger.error("No OpenAI client for Whisper transcription")
            return

        import io
        audio_file = io.BytesIO(audio_data)
        audio_file.name = "call_recording.mp3"

        transcript_resp = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            language="en",
        )
        raw_transcript = transcript_resp.text.strip()
        logger.info(f"Whisper raw transcript ({len(raw_transcript)} chars): {raw_transcript[:200]}")

        if not raw_transcript:
            logger.info("Empty transcript from Whisper")
            return

        # Fast local dedupe: remove consecutive duplicate lines and "word word" (no extra API call)
        import re
        lines = [ln.strip() for ln in raw_transcript.splitlines() if ln.strip()]
        seen = None
        deduped_lines = []
        for ln in lines:
            if ln != seen:
                deduped_lines.append(ln)
                seen = ln
        deduped = "\n".join(deduped_lines)
        deduped = re.sub(r"(\b\S+)\s+\1\b", r"\1", deduped)  # "word word" -> "word"
        deduped = re.sub(r"\n\s*\n+", "\n\n", deduped).strip()

        # Quick OpenAI cleanup only if still looks messy (saves ~3–5s when dedupe is enough)
        transcript_text = deduped
        if "  " in deduped or deduped.count("Agent:") > 5:
            try:
                cleanup = client.chat.completions.create(
                    model=OPENAI_MODEL,
                    messages=[
                        {"role": "system", "content": (
                            f"Clean this phone transcript. Caller: {caller_name}. Assistant: Agent. "
                            "One line per turn. Remove repeats and filler. Output only the cleaned transcript."
                        )},
                        {"role": "user", "content": deduped[:4000]},
                    ],
                    max_tokens=1500,
                )
                out = (cleanup.choices[0].message.content or "").strip()
                if out:
                    transcript_text = out
            except Exception as e:
                logger.warning(f"Transcript cleanup skipped: {e}")

        logger.info(f"Final transcript ({len(transcript_text)} chars)")

        # Save transcript to chat
        _save_msg_sync(
            caller_name,
            f"[Voice Call Transcript]\n\n{transcript_text}",
            "assistant",
        )

        # Save activity
        preview = transcript_text[:100] + ("..." if len(transcript_text) > 100 else "")
        _save_activity_sync(caller_name, f"[Voice Call] {preview}")

        # Try to save to Google Doc (best effort)
        try:
            from voice_agent import _save_transcript_to_google_doc
            _save_transcript_to_google_doc(caller_name, transcript_text)
        except Exception as e:
            logger.warning(f"Google Doc save skipped: {e}")

    except Exception as e:
        logger.error(f"Whisper transcription error: {e}")
        _save_msg_sync(
            caller_name,
            f"[Voice Call] Call completed. Transcription failed: {str(e)[:200]}",
            "assistant",
        )


def _save_msg_sync(caller_name: str, content: str, role: str):
    """Save a message to DB (synchronous helper)."""
    db = SessionLocal()
    try:
        user = db.query(UserORM).filter(UserORM.name == caller_name).first()
        if not user:
            return
        _save_msg(db, user.id, f"voice:{user.id}", f"{caller_name} (voice call)", role, content)
        db.commit()
    finally:
        db.close()


def _save_activity_sync(caller_name: str, summary: str):
    """Save an activity row to DB (synchronous helper)."""
    db = SessionLocal()
    try:
        user = db.query(UserORM).filter(UserORM.name == caller_name).first()
        if not user:
            return
        _save_activity(db, user.id, caller_name, summary)
        db.commit()
    finally:
        db.close()


@app.websocket("/voice/ws")
async def voice_websocket(websocket: WebSocket):
    """
    WebSocket endpoint for Plivo bidirectional audio streaming.
    Plivo's <Stream> element connects here after /voice/identify.
    Runs the Pipecat pipeline with Gemini Live for real-time voice AI.
    After hangup: fetches Plivo recording → transcribes with Whisper → saves to chat + Google Doc.
    """
    caller = websocket.query_params.get("caller", "Unknown")
    # call_uuid passed from /voice/identify via query param (Plivo doesn't put it in stream metadata)
    call_uuid_from_url = websocket.query_params.get("call_uuid", "")
    await websocket.accept()

    call_id = call_uuid_from_url
    try:
        # First message from Plivo contains stream metadata
        start_data = await websocket.receive_json()
        # Try to get call_id from stream metadata too, but prefer the URL param
        if not call_id:
            call_id = start_data.get("callId", start_data.get("call_id", ""))
        stream_id = start_data.get("streamId", start_data.get("stream_id", ""))
        logger.info(
            f"Voice WebSocket connected: caller={caller}, "
            f"call_id={call_id}, stream_id={stream_id}"
        )

        # Start recording the call via Plivo REST API
        if call_id:
            _start_plivo_recording(call_id)
        else:
            logger.warning("No call_id available — cannot start recording")

        # Import and run the Pipecat voice agent
        from voice_agent import run_agent

        await run_agent(
            websocket=websocket,
            call_id=call_id,
            stream_id=stream_id,
            caller_name=caller,
            auth_id=PLIVO_AUTH_ID or "",
            auth_token=PLIVO_AUTH_TOKEN or "",
        )
    except Exception as e:
        logger.error(f"Voice WebSocket error for {caller}: {e}")
        traceback.print_exc()
    finally:
        logger.info(f"Voice WebSocket closed for {caller}")

        # ── After hangup: fetch recording and transcribe ──
        if call_id:
            import threading
            threading.Thread(
                target=_fetch_and_transcribe_recording,
                args=(call_id, caller),
                daemon=True,
            ).start()
        else:
            logger.warning(f"No call_id for {caller} — skipping transcript")


@app.post("/voice/recording-callback")
async def voice_recording_callback(request: Request):
    """Plivo posts here when a call recording is ready."""
    form = await request.form()
    logger.info(f"Recording callback: {dict(form)}")
    return {"ok": True}
