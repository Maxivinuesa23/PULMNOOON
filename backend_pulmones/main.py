from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from core.config import UPLOAD_DIR, OUTPUT_DIR
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

# Importamos las rutas que creamos en api/routes.py
from api.routes import router

app = FastAPI(title="Pulmonary Nodule AI Backend")

# Permitir orígenes cruzados para Vercel
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://pulmooon.vercel.app",
        "http://localhost:5173",
        "http://localhost:3000",
        "*"  # Permite pruebas y conexiones directas
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")

# Crear carpetas de runtime automáticamente al iniciar el servidor.
# Por defecto viven en el directorio temporal del sistema, no dentro del repo.
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)