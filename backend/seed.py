"""
Seed script: creates two demo accounts (Sean & Yug) for the simplified Parallel AI.
Run once (with backend stopped), then start the backend.

Usage:  python seed.py
"""

import uuid
import bcrypt
from datetime import datetime, timezone

from database import SessionLocal, engine, Base
from models import User, UserCredential

# Recreate all tables (drops existing so we get a clean schema)
Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)

db = SessionLocal()


def _hash(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


now = datetime.now(timezone.utc)
sean_id = str(uuid.uuid4())
yug_id = str(uuid.uuid4())

sean = User(
    id=sean_id,
    email="sean@parallel.dev",
    name="Sean",
    role="Engineering",
    created_at=now,
    last_seen_at=now,
)
yug = User(
    id=yug_id,
    email="yug@parallel.dev",
    name="Yug",
    role="Engineering",
    created_at=now,
    last_seen_at=now,
)
db.add(sean)
db.add(yug)

db.add(UserCredential(user_id=sean_id, password_hash=_hash("pass"), created_at=now))
db.add(UserCredential(user_id=yug_id, password_hash=_hash("pass"), created_at=now))

db.commit()
db.close()

print("Seed complete!")
print()
print("  Sean  ->  email: sean@parallel.dev   password: pass")
print("  Yug   ->  email: yug@parallel.dev    password: pass")
print()
print("Start the backend and log in from two browser windows.")
