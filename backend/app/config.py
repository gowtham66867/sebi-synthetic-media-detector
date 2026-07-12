import os
from pathlib import Path
from dotenv import load_dotenv

BACKEND_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(BACKEND_ROOT.parent.parent / ".env")
load_dotenv(BACKEND_ROOT / ".env")

DATA_DIR = BACKEND_ROOT / "data"
UPLOAD_DIR = BACKEND_ROOT / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "base")
LLM_MODEL = os.getenv("LLM_MODEL", "gemini-2.5-flash")
SIGNING_PRIVATE_KEY_PEM = os.getenv("SIGNING_PRIVATE_KEY_PEM", "")
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://localhost:5180")
