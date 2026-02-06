# backend/config.py
import os
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(dotenv_path=Path(__file__).with_name(".env"))

# Sean = Key B, Yug = Key A
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
