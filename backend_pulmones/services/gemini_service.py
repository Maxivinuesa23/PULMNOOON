import base64
import json
import urllib.error
import urllib.request
from PIL import Image

from core.config import GEMINI_API_KEY, GEMINI_MODEL


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
        from io import BytesIO
        buffer = BytesIO()
        crop.save(buffer, format="PNG")
        encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    prompt = (
        "Actua como segundo lector de imagen toracica, no como diagnostico definitivo. "
        "Analiza el recorte de una TC pulmonar alrededor de una region sospechosa. "
        "Distingue entre: nodulo/masa pulmonar, vaso sanguineo, bronquio, pleura, "
        "atelectasia, cicatriz, artefacto de movimiento/metal o camilla, y normal. "
        "La camilla suele producir una banda o estructura densa en la zona inferior de la imagen: "
        "si la region esta pegada al borde inferior o tiene forma lineal, considerala posible artefacto "
        "y no tumor. No declares posible tumor solo por alta densidad: exige una lesion focal, "
        "redondeada u ovalada, dentro del parenquima y separada de vasos o pleura. "
        "Evalua forma, margenes, densidad, ubicacion y contexto, sin inventar datos. "
        "Responde SOLO JSON valido con estas claves: "
        "classification (possible_tumor|vessel|airway|pleura|atelectasis|scar|table_artifact|normal|uncertain), "
        "confidence (0-100), reason (breve), recommendation (siguiente paso clinico)."
    )
    payload = {
        "contents": [{"parts": [{"text": prompt}, {
            "inline_data": {"mime_type": "image/png", "data": encoded}
        }]}],
        "generationConfig": {"responseMimeType": "application/json"},
    }
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    request = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=30) as response:
        result = json.loads(response.read())
    text = result["candidates"][0]["content"]["parts"][0]["text"]
    return json.loads(text)


def verify_detections(image_paths: list[str], detections: list[dict]) -> list[dict]:
    for detection in detections[:10]:
        try:
            detection["gemini"] = verify_detection(image_paths[detection["slice"]], detection)
        except (OSError, ValueError, KeyError, urllib.error.URLError, json.JSONDecodeError) as error:
            detection["gemini"] = {"status": "error", "message": str(error)}
    return detections


def build_conclusion(detections: list[dict]) -> dict:
    results = [(d.get("gemini") or {}) for d in detections]
    classifications = [r.get("classification") for r in results]
    if not results or all(r.get("status") in {"disabled", "error"} for r in results):
        return {
            "conclusion": "No se pudo realizar la segunda validacion con Gemini.",
            "recomendaciones": ["Solicitar revision por un radiologo/neumonologo."],
            "status": "unavailable",
        }
    if "possible_tumor" in classifications:
        conclusion = "Se identificaron regiones que Gemini considera compatibles con un posible nodulo o tumor. Requieren confirmacion medica."
    elif any(value in {"table_artifact", "vessel", "airway", "normal"} for value in classifications):
        conclusion = "Las regiones marcadas parecen mas compatibles con estructuras normales o artefactos que con un tumor."
    else:
        conclusion = "El resultado es indeterminado: las regiones requieren evaluacion profesional."
    return {
        "conclusion": conclusion,
        "recomendaciones": [
            "Comparar con estudios previos y evaluar crecimiento.",
            "Consultar a un radiologo/neumonologo; no es un diagnostico.",
            "Evitar tabaco y humo, y mantener controles preventivos.",
            "Revisar especialmente falsos positivos en la zona inferior: la camilla puede generar artefactos densos.",
        ],
        "status": "completed",
    }
