from datetime import datetime
from typing import List, Optional

from sqlalchemy import Column, DateTime, Float, ForeignKey, String, Text, JSON, Integer, Boolean
from sqlalchemy.orm import relationship

from database import Base


class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    role = Column(String, nullable=True)
    preferences = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)

    agents = relationship("AgentProfile", back_populates="owner")
    inbox_tasks = relationship("InboxTask", back_populates="user")
    credentials = relationship("UserCredential", back_populates="user", uselist=False)
    sentiments = relationship("UserSentiment", back_populates="user")


class UserCredential(Base):
    __tablename__ = "user_credentials"
    user_id = Column(String, ForeignKey("users.id"), primary_key=True)
    password_hash = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="credentials")


class UserSentiment(Base):
    __tablename__ = "user_sentiments"
    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    score = Column(Float, default=0.0)
    note = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="sentiments")


class Organization(Base):
    __tablename__ = "organizations"
    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    owner_user_id = Column(String, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    rooms = relationship("Room", back_populates="org")


class AgentProfile(Base):
    __tablename__ = "agents"
    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    persona_json = Column(JSON, default=dict)
    persona_embedding = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    owner = relationship("User", back_populates="agents")
    memories = relationship("MemoryRecord", back_populates="agent")


class Room(Base):
    __tablename__ = "rooms"
    id = Column(String, primary_key=True, index=True)
    org_id = Column(String, ForeignKey("organizations.id"), nullable=False)
    name = Column(String, nullable=False)
    project_summary = Column(Text, default="")
    memory_summary = Column(Text, default="")
    summary_version = Column(Integer, default=1)
    summary_updated_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)

    org = relationship("Organization", back_populates="rooms")
    messages = relationship("Message", back_populates="room")
    memories = relationship("MemoryRecord", back_populates="room")


class Message(Base):
    __tablename__ = "messages"
    id = Column(String, primary_key=True, index=True)
    room_id = Column(String, ForeignKey("rooms.id"), nullable=False, index=True)
    sender_id = Column(String, nullable=False)
    sender_name = Column(String, nullable=False)
    role = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    room = relationship("Room", back_populates="messages")


class InboxTask(Base):
    __tablename__ = "inbox_tasks"
    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    content = Column(Text, nullable=False)
    room_id = Column(String, ForeignKey("rooms.id"), nullable=True)
    source_message_id = Column(String, nullable=True)
    status = Column(String, default="open")
    priority = Column(String, nullable=True)
    tags = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="inbox_tasks")


class MemoryRecord(Base):
    __tablename__ = "memories"
    id = Column(String, primary_key=True, index=True)
    agent_id = Column(String, ForeignKey("agents.id"), nullable=False, index=True)
    room_id = Column(String, ForeignKey("rooms.id"), nullable=True, index=True)
    content = Column(Text, nullable=False)
    importance_score = Column(Float, default=0.0)
    embedding = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    agent = relationship("AgentProfile", back_populates="memories")
    room = relationship("Room", back_populates="memories")


class Task(Base):
    __tablename__ = "tasks"
    id = Column(String, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, default="")
    assignee_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    status = Column(String, default="new", index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

    assignee = relationship("User")


class Notification(Base):
    __tablename__ = "notifications"
    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    type = Column(String, default="task")
    title = Column(String, nullable=False)
    message = Column(Text, default="")
    task_id = Column(String, ForeignKey("tasks.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_read = Column(Boolean, default=False)

    user = relationship("User")
    task = relationship("Task")


class EventLog(Base):
    __tablename__ = "event_logs"
    id = Column(String, primary_key=True, index=True)
    room_id = Column(String, ForeignKey("rooms.id"), nullable=False, index=True)
    user_id = Column(String, nullable=True)
    event_type = Column(String, nullable=False)
    detail = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

