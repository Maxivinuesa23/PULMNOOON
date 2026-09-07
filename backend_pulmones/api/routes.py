from fastapi import APIRouter, UploadFile, File, BackgroundTasks, Depends, HTTPException
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import shutil
import os
import uuid
import logging
import time
from services.image_service import process_tomography_zip
from services.ai_service import run_inference
from services.mesh_service import generate_3d_mesh
from services.gemini_service import build_conclusion, verify_detections, apply_second_opinion
from services.storage_service import upload_zip
from core.config import UPLOAD_DIR, OUTPUT_DIR
from core.database import get_db
from core.models import Examen

router = APIRouter()
tasks_db = {}
logger = logging.getLogger("cancer_detector")


@router.get("/exams")
async def list_exams(db: AsyncSession = Depends(get_db)):
    """Example route showing async session injection."""
    result = await db.execute(select(Examen).order_by(Examen.fecha.desc()))
    return result.scalars().all()

# Host publico configurado para Render (con respaldo automático si no se define la variable)
DEFAULT_RENDER_URL = "https://pulmnooon.onrender.com"
BASE_HOST_URL = os.getenv(
    "BACKEND_URL",
    DEFAULT_RENDER_URL if os.getenv("RENDER") else "http://localhost:8001"
).rstrip("/")

def process_workflow(task_id: str, file_path: str):
    tasks_db[task_id] = {"status": "processing"}
    logger.info("[TAREA %s] Iniciando pipeline: %s", task_id, file_path)
    
    task_output_folder = os.path.join(OUTPUT_DIR, task_id)
    os.makedirs(task_output_folder, exist_ok=True)
    completed = False
    
    try:
        # 1. Extraer ZIP y procesar cortes y volumen
        volume_3d, slice_filenames, volume_metadata = process_tomography_zip(file_path, task_output_folder)
        logger.info("[TAREA %s] Volumen=%s cortes=%d metadata=%s", task_id, getattr(volume_3d, "shape", None), len(slice_filenames), volume_metadata)
        
        slice_paths = [os.path.join(task_output_folder, f) for f in slice_filenames]
        tumor_detected, confidence, stats = run_inference(slice_paths)
        logger.info("[TAREA %s] Inferencia: tumor=%s confidence=%s detecciones=%d", task_id, tumor_detected, confidence, len(stats.get("detecciones", [])))
        
        # Validacion secundaria con Gemini si hay detecciones
        stats["detecciones"] = verify_detections(slice_paths, stats.get("detecciones", []))
        gemini_results = [
            gemini for detection in stats["detecciones"]
            for gemini in [detection.get("gemini") or {}]
            if gemini.get("classification")
        ]
        
        if gemini_results:
            tumor_detected = any(r.get("classification") == "possible_tumor" for r in gemini_results)
            positive_results = [
                result for result in gemini_results
                if result.get("classification") == "possible_tumor"
            ]
            confidence = round(
                sum(float(result.get("confidence", 0)) for result in positive_results)
                / len(positive_results),
                1,
            ) if positive_results else 0.0

        stats = apply_second_opinion(stats["detecciones"], stats)

        generate_3d_mesh(volume_3d, task_output_folder, stats["detecciones"], volume_metadata)
        extracted_data_folder = os.path.join(task_output_folder, "extracted_data")
        shutil.rmtree(extracted_data_folder, ignore_errors=True)
        
        mesh_path = os.path.join(task_output_folder, "mesh.gltf")
        model_filename = "mesh.gltf"
        if not os.path.exists(mesh_path):
            mesh_path = os.path.join(task_output_folder, "mesh.glb")
            model_filename = "mesh.glb"
            
        logger.info("[TAREA %s] Malla=%s existe=%s", task_id, mesh_path, os.path.exists(mesh_path))

        # Los cortes 2D se sirven como archivos estaticos (mount /files en main.py)
        base_static_url = f"{BASE_HOST_URL}/files/{task_id}"
        slices_urls = [f"{base_static_url}/{fname}" for fname in slice_filenames]

        # La malla 3D sigue viajando por /api/download
        base_download_url = f"{BASE_HOST_URL}/api/download/{task_id}"
        model_3d_url = f"{base_download_url}/{model_filename}" if os.path.exists(mesh_path) else None
        
        tasks_db[task_id] = {
            "status": "completed",
            "results": {
                "taskId": task_id,
                "tumorDetected": tumor_detected,
                "confidence": confidence,
                "stats": stats,
                "model3dUrl": model_3d_url,
                "slices2dUrls": slices_urls,
                "detections": stats["detecciones"],
                "geminiEnabled": bool(os.getenv("GEMINI_API_KEY"))
            }
        }
        completed = True
        logger.info("[TAREA %s] Pipeline completado exitosamente", task_id)
        
    except Exception as e:
        logger.exception("[TAREA %s] Error critico en pipeline", task_id)
        tasks_db[task_id] = {"status": "error", "message": str(e)}
    finally:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception:
            pass
        if not completed:
            shutil.rmtree(task_output_folder, ignore_errors=True)

@router.post("/upload")
async def upload_tomography(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    filename = file.filename or ""
    if not filename.lower().endswith(".zip") or os.path.basename(filename) != filename:
        raise HTTPException(
            status_code=400,
            detail="Solo se aceptan archivos .zip.",
        )

    cutoff = time.time() - 3600
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    try:
        for upload in UPLOAD_DIR.iterdir():
            if upload.is_file() and upload.stat().st_mtime < cutoff:
                upload.unlink(missing_ok=True)
    except Exception as err:
        logger.warning("[UPLOAD] Error limpiando directorio upload: %s", err)

    task_id = str(uuid.uuid4())
    file_path = os.path.join(UPLOAD_DIR, f"{task_id}.zip")
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    logger.info("[UPLOAD %s] filename=%s guardado=%s bytes=%d", task_id, filename, file_path, os.path.getsize(file_path))
    storage_key = f"tomografias/{task_id}.zip"
    try:
        await run_in_threadpool(upload_zip, file_path, storage_key)
        logger.info("[UPLOAD %s] ZIP subido a Supabase Storage: %s", task_id, storage_key)
    except Exception as err:
        logger.exception("[UPLOAD %s] No se pudo subir el ZIP a Supabase Storage", task_id)
        raise HTTPException(
            status_code=502,
            detail="No se pudo guardar el archivo en Supabase Storage.",
        ) from err

    background_tasks.add_task(process_workflow, task_id, file_path)
    
    return {
        "status": "success",
        "message": "Archivo recibido correctamente.",
        "task_id": task_id,
        "filename": file.filename,
        "storage_key": storage_key,
    }

@router.get("/status/{task_id}")
def get_task_status(task_id: str):
    task = tasks_db.get(task_id)
    if not task:
        return {"status": "not_found", "message": "Tarea no encontrada o en preparacion"}
    return task

@router.post("/validate-gemini/{task_id}")
def validate_with_gemini(task_id: str):
    task = tasks_db.get(task_id)
    if not task or task.get("status") != "completed":
        raise HTTPException(status_code=404, detail="Analisis no disponible.")
        
    result = task["results"]
    folder = os.path.join(OUTPUT_DIR, task_id)
    slice_paths = [os.path.join(folder, os.path.basename(url.split("/")[-1].split("?")[0])) for url in result["slices2dUrls"]]
    detections = verify_detections(slice_paths, result.get("detections", []))
    result["detections"] = detections
    
    classifications = [
        (d.get("gemini") or {}).get("classification") for d in detections
    ]
    if any(value == "possible_tumor" for value in classifications):
        result["tumorDetected"] = True
    elif classifications and all(value in {"table_artifact", "vessel", "airway", "normal"} for value in classifications):
        result["tumorDetected"] = False
        
    result["geminiValidated"] = True
    if "stats" in result:
        result["stats"] = apply_second_opinion(detections, result["stats"])
        
    result.update(build_conclusion(detections))
    return result

@router.get("/download/{task_id}/{filename}")
def download_result(task_id: str, filename: str):
    task_folder = os.path.join(OUTPUT_DIR, task_id)
    safe_filename = os.path.basename(filename)
    file_path = os.path.join(task_folder, safe_filename)
    
    if not os.path.exists(file_path):
        logger.error("[DOWNLOAD] No existe %s", file_path)
        raise HTTPException(status_code=404, detail="Archivo no encontrado.")
        
    media_type = "model/gltf-binary" if safe_filename.lower().endswith(".glb") else ("model/gltf+json" if safe_filename.lower().endswith(".gltf") else None)
    
    return FileResponse(
        file_path, 
        media_type=media_type, 
        filename=safe_filename,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Cache-Control": "public, max-age=86400"
        }
    )

@router.head("/download/{task_id}/{filename}")
def head_result(task_id: str, filename: str):
    task_folder = os.path.join(OUTPUT_DIR, task_id)
    safe_filename = os.path.basename(filename)
    file_path = os.path.join(task_folder, safe_filename)
    
    if not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="Archivo no encontrado.")
        
    media_type = "model/gltf-binary" if safe_filename.lower().endswith(".glb") else ("model/gltf+json" if safe_filename.lower().endswith(".gltf") else None)
    
    return FileResponse(
        file_path, 
        media_type=media_type, 
        filename=safe_filename,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Cache-Control": "public, max-age=86400"
        }
    )