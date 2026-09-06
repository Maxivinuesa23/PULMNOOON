import os
import tempfile
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
RUNTIME_DIR = Path(os.getenv("RUNTIME_DIR", Path(tempfile.gettempdir()) / "pulmoscan"))
UPLOAD_DIR = RUNTIME_DIR / "uploads"
OUTPUT_DIR = RUNTIME_DIR / "outputs"
MODEL_PATH = BASE_DIR / "ai_model" / "modelo_entrenado.pth"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
GEMINI_TIMEOUT = int(os.getenv("GEMINI_TIMEOUT", "30"))
GEMINI_MAX_RETRIES = int(os.getenv("GEMINI_MAX_RETRIES", "2"))
GEMINI_MAX_REVIEWS = int(os.getenv("GEMINI_MAX_REVIEWS", "10"))
GEMINI_MAX_WORKERS = int(os.getenv("GEMINI_MAX_WORKERS", "5"))
PUBLIC_API_URL = os.getenv("PUBLIC_API_URL", "http://localhost:8001")