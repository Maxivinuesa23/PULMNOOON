from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from core.config import UPLOAD_DIR, OUTPUT_DIR
from fastapi.staticfiles import StaticFiles
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

# Importamos las rutas desde api/routes.py
from api.routes import router

app = FastAPI(title="Pulmonary Nodule AI Backend")

# Origenes permitidos sin comodines conflictivos con allow_credentials
origins = [
    "https://pulmnooon.vercel.app",
    "http://localhost:5173",
    "http://localhost:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=r"https://pulmnooon.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")

# ... (código anterior igual) ...

@app.get("/")
def read_root():
    return {"status": "online", "service": "Pulmonary Nodule AI Backend"}

# 1. PRIMERO creas las carpetas de runtime
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# 2. DESPUÉS montas el directorio estático
app.mount("/files", StaticFiles(directory=str(OUTPUT_DIR)), name="files")