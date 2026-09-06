import logging

import numpy as np
import torch
from PIL import Image, ImageDraw
from scipy import ndimage

from ai_model.architecture import MiniUNet
from core.config import MODEL_PATH

logger = logging.getLogger("cancer_detector.ai")

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
modelo_ia = MiniUNet().to(device)
model_loaded = False

if MODEL_PATH.exists():
    try:
        state = torch.load(MODEL_PATH, map_location=device)
        if isinstance(state, dict) and "state_dict" in state:
            state = state["state_dict"]
        modelo_ia.load_state_dict(state)
        model_loaded = True
        logger.info("Pesos cargados correctamente desde %s", MODEL_PATH)
    except (RuntimeError, KeyError, OSError, ValueError) as error:
        # Un checkpoint corrupto o incompatible no debe tumbar el servicio:
        # seguimos con el modelo sin entrenar (model_loaded=False) para que
        # el resto del pipeline (heuristicas + Gemini) siga funcionando y
        # el problema quede visible en la respuesta ("modeloCargado": false)
        # en vez de como un 500 al arrancar.
        logger.warning("No se pudieron cargar los pesos desde %s: %s", MODEL_PATH, error)
        model_loaded = False
else:
    logger.warning("No se encontro el archivo de pesos en %s", MODEL_PATH)

modelo_ia.eval()


def _lung_mask(arr_norm: np.ndarray) -> np.ndarray:
    candidate = (arr_norm > 0.03) & (arr_norm < 0.70)
    candidate = ndimage.binary_opening(candidate, iterations=1)
    candidate = ndimage.binary_closing(candidate, iterations=2)
    labels, count = ndimage.label(candidate)
    if count:
        sizes = ndimage.sum(candidate, labels, range(1, count + 1))
        keep = np.argsort(sizes)[-2:] + 1
        candidate = np.isin(labels, keep)
    return candidate


def run_inference(image_paths: list[str]):
    detections = []
    affected_slices = 0
    max_area = 0
    max_score = 0.0
    critical_slice = 0

    for index, image_path in enumerate(image_paths):
        image = Image.open(image_path).convert("RGB")
        width, height = image.size
        gray = np.asarray(image.convert("L"), dtype=np.float32)
        low, high = np.percentile(gray, (1, 99))
        normalized = np.clip((gray - low) / max(high - low, 1e-6), 0, 1)
        lung = _lung_mask(normalized)

        model_input = Image.fromarray((normalized * 255).astype(np.uint8)).resize((64, 64))
        tensor = torch.from_numpy(np.asarray(model_input, dtype=np.float32) / 255).unsqueeze(0).unsqueeze(0).to(device)
        with torch.inference_mode():
            prediction = modelo_ia(tensor).squeeze().cpu().numpy()
        prediction = np.asarray(Image.fromarray((prediction * 255).astype(np.uint8)).resize(
            (width, height), Image.Resampling.BILINEAR
        )) / 255.0

        # Exigimos una probabilidad alta dentro del pulmon. El modelo reducido
        # tiene una salida suave al redimensionar, por lo que un umbral menor
        # convierte bordes e interpolacion en falsos positivos.
        mask = (prediction >= 0.78) & lung
        mask = ndimage.binary_opening(mask, iterations=1)
        labels, count = ndimage.label(mask)
        components = []
        for component in range(1, count + 1):
            ys, xs = np.where(labels == component)
            if len(xs) < 15 or len(xs) > 2500:
                continue
            x1, x2 = int(xs.min()), int(xs.max())
            y1, y2 = int(ys.min()), int(ys.max())
            # La camilla y el borde inferior generan focos muy densos que no
            # deben presentarse como posibles nodulos.
            if y1 > height * 0.88:
                continue
            if (x2 - x1 + 1) > min(width, height) * 0.20 or (y2 - y1 + 1) > min(width, height) * 0.20:
                continue
            smooth = ndimage.gaussian_filter(normalized, sigma=5)
            local_contrast = float(np.mean(normalized[ys, xs] - smooth[ys, xs]))
            if local_contrast < 0.015:
                continue
            score = float(0.75 * prediction[ys, xs].mean() + 0.25 * np.clip(
                local_contrast / 0.25, 0, 1
            ))
            components.append((len(xs), score, x1, y1, x2, y2))

        if not components:
            # Propuesta independiente de la red: lesiones suelen ser focos
            # localmente mas densos que el parenquima vecino.
            smooth = ndimage.gaussian_filter(normalized, sigma=5)
            local_contrast = normalized - smooth
            fallback = (normalized > 0.62) & (local_contrast > 0.10) & lung
            fallback_labels, fallback_count = ndimage.label(fallback)
            for component in range(1, fallback_count + 1):
                ys, xs = np.where(fallback_labels == component)
                if len(xs) < 18 or len(xs) > width * height * 0.08:
                    continue
                box_width, box_height = np.ptp(xs) + 1, np.ptp(ys) + 1
                box_area = box_width * box_height
                compactness = len(xs) / max(box_area, 1)
                if compactness < 0.22 or box_width > width * 0.28 or box_height > height * 0.28:
                    continue
                if np.min(ys) > height * 0.88:
                    continue
                components.append((
                    len(xs), float(normalized[ys, xs].mean()),
                    int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max()),
                ))

        components = sorted(components, key=lambda item: item[1], reverse=True)[:3]
        affected_slices += int(bool(components))
        for area, score, x1, y1, x2, y2 in components:
            detections.append({
                "slice": index, "x": x1, "y": y1, "width": x2 - x1 + 1,
                "height": y2 - y1 + 1, "areaPixels": area,
                "score": round(score * 100, 1), "gemini": None,
            })
            if area > max_area:
                max_area, max_score, critical_slice = area, score, index

        draw = ImageDraw.Draw(image)
        for _, score, x1, y1, x2, y2 in components:
            draw.rectangle((x1, y1, x2, y2), outline=(255, 40, 40), width=max(2, width // 256))
            draw.text((x1, max(0, y1 - 16)), f"posible anomalia {score * 100:.0f}%", fill=(255, 180, 40))
        image.save(image_path)

    area_mm2 = max_area * 0.7 * 0.7
    stats = {
        "slicesAfectados": f"{affected_slices} de {len(image_paths)}",
        "corteCritico": critical_slice,
        "areaAfectadaMax": f"{area_mm2:.2f} mm²",
        "volumenEstimado": f"{area_mm2 * max(affected_slices, 1) * 2.5:.2f} mm³",
        "diametroAprox": f"{2 * np.sqrt(area_mm2 / np.pi):.2f} mm" if area_mm2 else "0 mm",
        "detecciones": detections,
        "modeloCargado": model_loaded,
        "dispositivo": str(device),
    }
    # La confianza representa la mejor evidencia disponible, no el promedio
    # de todos los focos (que puede ocultar una deteccion fuerte).
    confidence = round(max_score * 100, 1) if detections else 0.0
    return bool(detections), confidence, stats