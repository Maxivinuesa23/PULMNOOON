import base64
import json
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from io import BytesIO
from PIL import Image

from core.config import (
    GEMINI_API_KEY,
    GEMINI_MODEL,
    GEMINI_TIMEOUT,
    GEMINI_MAX_RETRIES,
    GEMINI_MAX_REVIEWS,
    GEMINI_MAX_WORKERS,
)

# Clasificaciones que Gemini puede devolver y que NO deben contar como
# hallazgo positivo en el resumen final (son descartes, no tumores).
NON_TUMOR_CLASSIFICATIONS = {
    "vessel", "airway", "pleura", "atelectasis",
    "scar", "table_artifact", "normal",
}


def _call_gemini(payload: dict) -> dict:
    """Llama a la API de Gemini con reintentos ante errores transitorios."""
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    )
    last_error = None
    for attempt in range(GEMINI_MAX_RETRIES + 1):
        try:
            request = urllib.request.Request(
                url,
                data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(request, timeout=GEMINI_TIMEOUT) as response:
                return json.loads(response.read())
        except urllib.error.HTTPError as error:
            last_error = error
            # 429 (rate limit) y 5xx son transitorios, el resto no vale reintentar.
            if error.code not in (429, 500, 502, 503, 504) or attempt == GEMINI_MAX_RETRIES:
                raise
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            last_error = error
            if attempt == GEMINI_MAX_RETRIES:
                raise
        time.sleep(min(2 ** attempt, 8))
    raise last_error


def verify_detection(image_path: str, detection: dict) -> dict:
    if not GEMINI_API_KEY:
        return {"status": "disabled", "reason": "GEMINI_API_KEY no configurada"}

    with Image.open(image_path) as image:
        image_width, image_height = image.size
        crop = image.crop((
            max(0, detection["x"] - detection["width"]),
            max(0, detection["y"] - detection["height"]),
            min(image_width, detection["x"] + detection["width"] * 2),
            min(image_height, detection["y"] + detection["height"] * 2),
        )).convert("RGB")
        buffer = BytesIO()
        crop.save(buffer, format="PNG")
        encoded = base64.b64encode(buffer.getvalue()).decode("ascii")

    review_context = {
        "slice": detection.get("slice"),
        "detector_score": detection.get("score"),
        "crop_size": [crop.width, crop.height],
        "review_id": datetime.now(timezone.utc).isoformat(),
    }
    prompt = (
        "Actua como segundo lector de una TC pulmonar. No emitas un diagnostico definitivo. "
        "Esta es una revision independiente de un recorte; no asumas que la deteccion automatica "
        "es correcta y no uses respuestas previas. Examina visualmente el recorte y justifica la "
        "decision con evidencia observable. "
        "Distingue entre: nodulo/masa pulmonar, vaso sanguineo, bronquio, pleura, atelectasia, "
        "cicatriz, artefacto de movimiento/metal/camilla, normal o incierto. "
        "La camilla suele producir una banda o estructura densa en la zona inferior: si la region "
        "esta pegada al borde inferior o tiene forma lineal, prioriza table_artifact. "
        "No clasifiques possible_tumor solo por alta densidad: exige una lesion focal redondeada u "
        "ovalada, dentro del parenquima y separada de vasos o pleura. Si la imagen no permite "
        "distinguirlo, usa uncertain y baja la confianza. No inventes sintomas, antecedentes ni "
        "medidas que no se vean. "
        f"Contexto tecnico de esta revision (no es evidencia clinica): {json.dumps(review_context)}. "
        "Responde SOLO un objeto JSON valido, sin markdown, con estas claves: "
        "classification (possible_tumor|vessel|airway|pleura|atelectasis|scar|table_artifact|normal|uncertain), "
        "confidence (entero 0-100), reason (una explicacion concreta de 1-2 frases), "
        "recommendation (siguiente paso clinico prudente)."
    )
    payload = {
        "contents": [{"parts": [{"text": prompt}, {
            "inline_data": {"mime_type": "image/png", "data": encoded}
        }]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.2,
            "topP": 0.9,
        },
    }
    result = _call_gemini(payload)
    text = result["candidates"][0]["content"]["parts"][0]["text"]
    return json.loads(text)


def verify_detections(image_paths: list[str], detections: list[dict]) -> list[dict]:
    """
    Revisa hasta GEMINI_MAX_REVIEWS detecciones en paralelo. Cada deteccion
    queda con su clave "gemini" seteada (o un error/estado si fallo).
    """
    to_review = detections[:GEMINI_MAX_REVIEWS]
    if not to_review:
        return detections

    def _worker(detection):
        try:
            return verify_detection(image_paths[detection["slice"]], detection)
        except (OSError, ValueError, KeyError, IndexError, urllib.error.URLError, json.JSONDecodeError) as error:
            return {"status": "error", "message": str(error)}

    with ThreadPoolExecutor(max_workers=GEMINI_MAX_WORKERS) as executor:
        future_to_detection = {executor.submit(_worker, d): d for d in to_review}
        for future in as_completed(future_to_detection):
            detection = future_to_detection[future]
            detection["gemini"] = future.result()

    return detections


def apply_second_opinion(detections: list[dict], stats: dict) -> dict:
    """
    Usa la clasificacion de Gemini para recalcular las stats finales,
    descartando del resumen las detecciones que Gemini identifico como
    vaso/via aerea/artefacto/normal (falsos positivos del detector local).

    No borra las detecciones: las marca con "descartado_por_gemini" para
    que sigan siendo trazables en el detalle, pero no cuenten en el
    resumen (confianza, area, volumen, corte critico).

    Llamar DESPUES de run_inference() y verify_detections(), antes de
    devolver la respuesta al cliente.
    """
    valid = []
    for detection in detections:
        gemini = detection.get("gemini") or {}
        classification = gemini.get("classification")
        is_ruled_out = classification in NON_TUMOR_CLASSIFICATIONS
        detection["descartado_por_gemini"] = is_ruled_out
        if not is_ruled_out:
            valid.append(detection)

    if not valid:
        stats = {
            **stats,
            "slicesAfectados": f"0 de {stats.get('slicesAfectados', '0 de 0').split(' de ')[-1]}",
            "corteCritico": 0,
            "areaAfectadaMax": "0.00 mm²",
            "volumenEstimado": "0.00 mm³",
            "diametroAprox": "0 mm",
            "confianzaFinal": 0.0,
        }
        return stats

    affected_slices = len({d["slice"] for d in valid})
    best = max(valid, key=lambda d: d["areaPixels"])
    area_mm2 = best["areaPixels"] * 0.7 * 0.7
    import math
    stats = {
        **stats,
        "slicesAfectados": f"{affected_slices} de {stats.get('slicesAfectados', '0 de 0').split(' de ')[-1]}",
        "corteCritico": best["slice"],
        "areaAfectadaMax": f"{area_mm2:.2f} mm²",
        "volumenEstimado": f"{area_mm2 * max(affected_slices, 1) * 2.5:.2f} mm³",
        "diametroAprox": f"{2 * math.sqrt(area_mm2 / math.pi):.2f} mm" if area_mm2 else "0 mm",
        "confianzaFinal": max(d["score"] for d in valid),
    }
    return stats


def build_conclusion(detections: list[dict]) -> dict:
    results = [(d.get("gemini") or {}) for d in detections]
    classifications = [r.get("classification") for r in results]
    reviewed = [r for r in results if r.get("classification")]
    if not results or all(r.get("status") in {"disabled", "error"} for r in results):
        return {
            "conclusion": "No se pudo realizar la segunda validacion con Gemini.",
            "recomendaciones": ["Solicitar revision por un radiologo/neumonologo."],
            "status": "unavailable",
        }
    if "possible_tumor" in classifications:
        conclusion = (
            f"Gemini considero {classifications.count('possible_tumor')} region(es) "
            "compatibles con un posible nodulo o tumor. Requieren confirmacion medica."
        )
    elif any(value in NON_TUMOR_CLASSIFICATIONS for value in classifications):
        conclusion = (
            "Las regiones marcadas parecen mas compatibles con estructuras normales "
            "o artefactos que con un tumor."
        )
    else:
        conclusion = "El resultado es indeterminado: las regiones requieren evaluacion profesional."
    return {
        "conclusion": conclusion,
        "recomendaciones": [
            f"Se revisaron {len(reviewed)} region(es); confianza informada: "
            f"{', '.join(str(r.get('confidence')) + '%' for r in reviewed if r.get('confidence') is not None) or 'no disponible'}.",
            "Comparar con estudios previos y evaluar crecimiento.",
            "Consultar a un radiologo/neumonologo; no es un diagnostico.",
        ],
        "status": "completed",
    }