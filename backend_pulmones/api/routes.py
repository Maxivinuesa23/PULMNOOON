from fastapi import APIRouter, UploadFile, File, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse
import shutil
import os
import uuid
import logging
import time
from services.image_service import process_tomography_zip
from services.ai_service import run_inference
from services.mesh_service import generate_3d_mesh
from services.gemini_service import build_conclusion, verify_detections, apply_second_opinion
from core.config import UPLOAD_DIR, OUTPUT_DIR

router = APIRouter()
tasks_db = {}
logger = logging.getLogger("cancer_detector")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
# Obtener host público (por defecto la URL HTTPS de Render)
BASE_HOST_URL = os.getenv("BACKEND_URL", "https://pulmnooon.onrender.com")

def process_workflow(task_id: str, file_path: str):
    tasks_db[task_id] = {"status": "processing"}
    logger.info("[TAREA %s] Iniciando pipeline: %s", task_id, file_path)
    
    task_output_folder = os.path.join(OUTPUT_DIR, task_id)
    os.makedirs(task_output_folder, exist_ok=True)
    completed = False
    
    try:
        # 1. Extraer ZIP y obtener volumen 3D y lista de cortes
        volume_3d, slice_filenames, volume_metadata = process_tomography_zip(file_path, task_output_folder)
        logger.info("[TAREA %s] Volumen=%s cortes=%d metadata=%s", task_id, getattr(volume_3d, "shape", None), len(slice_filenames), volume_metadata)
        slice_paths = [os.path.join(task_output_folder, f) for f in slice_filenames]
        tumor_detected, confidence, stats = run_inference(slice_paths)
        logger.info("[TAREA %s] Inferencia: tumor=%s confidence=%s detecciones=%d", task_id, tumor_detected, confidence, len(stats["detecciones"]))
        stats["detecciones"] = verify_detections(slice_paths, stats["detecciones"])
        gemini_results = [
            gemini for detection in stats["detecciones"]
            for gemini in [detection.get("gemini") or {}]
            if gemini.get("classification")
        ]
        if gemini_results:
            tumor_detected = any(r["classification"] == "possible_tumor" for r in gemini_results)
            positive_results = [
                result for result in gemini_results
                if result["classification"] == "possible_tumor"
            ]
            confidence = round(
                sum(float(result.get("confidence", 0)) for result in positive_results)
                / len(positive_results),
                1,
            ) if positive_results else 0.0

        # La segunda opinion de Gemini tambien debe reflejarse en el resumen
        # (area, volumen, corte critico, slices afectados), no solo en
        # tumor_detected/confidence de arriba. Marca ademas cada deteccion
        # con "descartado_por_gemini" para que el mesh 3D las distinga.
        stats = apply_second_opinion(stats["detecciones"], stats)

        generate_3d_mesh(volume_3d, task_output_folder, stats["detecciones"], volume_metadata)
        extracted_data_folder = os.path.join(task_output_folder, "extracted_data")
        shutil.rmtree(extracted_data_folder, ignore_errors=True)
        mesh_path = os.path.join(task_output_folder, "mesh.gltf")
        model_filename = "mesh.gltf"
        if not os.path.exists(mesh_path):
            mesh_path = os.path.join(task_output_folder, "mesh.glb")
            model_filename = "mesh.glb"
        logger.info("[TAREA %s] Malla=%s existe=%s bytes=%d", task_id, mesh_path, os.path.exists(mesh_path), os.path.getsize(mesh_path) if os.path.exists(mesh_path) else 0)

        base_download_url = f"{BASE_HOST_URL}/api/download/{task_id}"
        slices_urls = [f"{base_download_url}/{fname}" for fname in slice_filenames]
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
        logger.info("[TAREA %s] Pipeline completado", task_id)
        
    except Exception as e:
        logger.exception("[TAREA %s] Error crítico", task_id)
        tasks_db[task_id] = {"status": "error", "message": str(e)}
    finally:
        # El ZIP original sólo es necesario durante el procesamiento.
        try:
            os.remove(file_path)
        except FileNotFoundError:
            pass
        if not completed:
            shutil.rmtree(task_output_folder, ignore_errors=True)

@router.post("/upload")
async def upload_tomography(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    cutoff = time.time() - 3600
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    for upload in UPLOAD_DIR.iterdir():
        if upload.is_file() and upload.stat().st_mtime < cutoff:
            upload.unlink(missing_ok=True)
    for folder in OUTPUT_DIR.iterdir() if hasattr(OUTPUT_DIR, "iterdir") else []:
        if folder.is_dir() and folder.stat().st_mtime < cutoff:
            shutil.rmtree(folder, ignore_errors=True)
    task_id = str(uuid.uuid4())
    file_extension = os.path.splitext(file.filename or "")[1].lower() or ".zip"
    file_path = os.path.join(UPLOAD_DIR, f"{task_id}{file_extension}")
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    logger.info("[UPLOAD %s] filename=%s guardado=%s bytes=%d", task_id, file.filename, file_path, os.path.getsize(file_path))
        
    background_tasks.add_task(process_workflow, task_id, file_path)
    return {
        "status": "success",
        "message": "Archivo recibido correctamente.",
        "task_id": task_id,
        "filename": file.filename
    }

@router.get("/status/{task_id}")
def get_task_status(task_id: str):
    task = tasks_db.get(task_id)
    if not task:
        return {"status": "not_found"}
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
    # Mantener el resumen numerico (stats) consistente con la revalidacion
    # manual, igual que en el pipeline automatico.
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
    logger.info("[DOWNLOAD] %s bytes=%d", file_path, os.path.getsize(file_path))
    media_type = "model/gltf-binary" if safe_filename.lower().endswith(".glb") else None
    return FileResponse(file_path, media_type=media_type, filename=safe_filename)

@router.head("/download/{task_id}/{filename}")
def head_result(task_id: str, filename: str):
    task_folder = os.path.join(OUTPUT_DIR, task_id)
    safe_filename = os.path.basename(filename)
    file_path = os.path.join(task_folder, safe_filename)
    if not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="Archivo no encontrado.")
    media_type = "model/gltf-binary" if safe_filename.lower().endswith(".glb") else None
    return FileResponse(file_path, media_type=media_type, filename=safe_filename)