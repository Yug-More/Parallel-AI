# backend/config.py
import os
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI
import plivo

load_dotenv(dotenv_path=Path(__file__).with_name(".env"))

# --- OpenAI (per-teammate) ---
SEAN_KEY = os.getenv("OPENAI_API_KEY_B")
YUG_KEY = os.getenv("OPENAI_API_KEY_A")


def make_client(key: str | None) -> OpenAI:
    if not key:
        raise RuntimeError("Missing OpenAI API key")
    return OpenAI(api_key=key)


CLIENTS = {
    "sean": make_client(SEAN_KEY),
    "yug": make_client(YUG_KEY),
}

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

# --- AGI (web research via REST API) ---
AGI_API_KEY = os.getenv("AGI_API_KEY")
AGI_BASE_URL = "https://api.agi.tech/v1"

# --- Composio (actions in apps) ---
COMPOSIO_API_KEY = os.getenv("COMPOSIO_API_KEY")

# --- Plivo (voice) ---
PLIVO_AUTH_ID = os.getenv("PLIVO_AUTH_ID")
PLIVO_AUTH_TOKEN = os.getenv("PLIVO_AUTH_TOKEN")
PLIVO_PHONE_NUMBER = os.getenv("PLIVO_PHONE_NUMBER")
TUNNEL_PUBLIC_URL = os.getenv("TUNNEL_PUBLIC_URL", "").strip() or None

# --- Composio: Sean-only linked accounts (use these entity/account IDs for Sean) ---
COMPOSIO_SEAN_GOOGLEDOCS_ACCOUNT_ID = os.getenv("COMPOSIO_SEAN_GOOGLEDOCS_ACCOUNT_ID", "").strip() or None
COMPOSIO_SEAN_GOOGLEDRIVE_ACCOUNT_ID = os.getenv("COMPOSIO_SEAN_GOOGLEDRIVE_ACCOUNT_ID", "").strip() or None

PLIVO_APP_ID = os.getenv("PLIVO_APP_ID", "24932251210085791")

# --- Gemini (Pipecat voice agent) ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

PLIVO_CLIENT = None
if PLIVO_AUTH_ID and PLIVO_AUTH_TOKEN:
    PLIVO_CLIENT = plivo.RestClient(PLIVO_AUTH_ID, PLIVO_AUTH_TOKEN)

# --- Composio singleton ---
_composio_client = None


def get_composio_client():
    global _composio_client
    if _composio_client is not None:
        return _composio_client
    if not COMPOSIO_API_KEY:
        return None
    try:
        from composio import Composio
        from composio_openai import OpenAIProvider
        _composio_client = Composio(provider=OpenAIProvider())
        return _composio_client
    except Exception as e:
        print(f"Composio init error: {e}")
        return None
