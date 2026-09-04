import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
UPLOAD_DIR = BASE_DIR / "temp_storage" / "uploads"
OUTPUT_DIR = BASE_DIR / "temp_storage" / "outputs"
MODEL_PATH = BASE_DIR / "ai_model" / "modelo_entrenado.pth"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
PUBLIC_API_URL = os.getenv("PUBLIC_API_URL", "http://localhost:8001")