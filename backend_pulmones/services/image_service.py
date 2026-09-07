import os
import zipfile
import pydicom
import numpy as np
from PIL import Image
import gc
import logging
import warnings

# Ocultar las advertencias inofensivas de pydicom sobre "explicit VR"
warnings.filterwarnings("ignore", category=UserWarning, module="pydicom")

logger = logging.getLogger("cancer_detector.images")

def process_tomography_zip(file_path: str, output_folder: str):
    logger.info("Extrayendo archivo ZIP: %s", file_path)
    extracted_folder = os.path.join(output_folder, "extracted_data")
    os.makedirs(extracted_folder, exist_ok=True)

    with zipfile.ZipFile(file_path, 'r') as zip_ref:
        zip_ref.extractall(extracted_folder)

    dcm_meta = []
    metadata_extracted = False
    vol_spacing = [0.7, 0.7]
    vol_thickness = 2.5

    total_candidatos = 0
    descartados_sin_tags = 0
    descartados_por_error = 0

    # 1. Escanear metadatos sin cargar los píxeles a la RAM
    for root, _, files in os.walk(extracted_folder):
        if "__MACOSX" in root:
            continue
        for f in files:
            if f.startswith(".") or f.lower().endswith((".xml", ".txt", ".json", ".pdf", ".png", ".jpg")):
                continue

            full_p = os.path.join(root, f)
            total_candidatos += 1

            try:
                # stop_before_pixels=True lee solo los metadatos (super ligero)
                ds = pydicom.dcmread(full_p, stop_before_pixels=True, force=True)

                # Si pydicom pudo extraer al menos 1 etiqueta, es un DICOM válido
                if len(ds.dir()) == 0:
                    descartados_sin_tags += 1
                    logger.debug("Ignorado (sin tags DICOM): %s", full_p)
                    continue

                # Intentar obtener la posición espacial para ordenarlos
                z_val = 0.0
                try:
                    if hasattr(ds, 'ImagePositionPatient') and ds.ImagePositionPatient:
                        z_val = float(ds.ImagePositionPatient[2])
                    elif hasattr(ds, 'InstanceNumber') and ds.InstanceNumber:
                        z_val = float(ds.InstanceNumber)
                    elif hasattr(ds, 'SliceLocation') and ds.SliceLocation:
                        z_val = float(ds.SliceLocation)
                    else:
                        z_val = float(len(dcm_meta))
                except (TypeError, ValueError, IndexError) as e:
                    logger.warning(
                        "No se pudo calcular posición Z de %s, se usa orden de aparición: %s",
                        full_p, e
                    )
                    z_val = float(len(dcm_meta))

                # Extraer metadatos geométricos del primer corte válido
                if not metadata_extracted:
                    try:
                        if hasattr(ds, 'PixelSpacing') and ds.PixelSpacing:
                            vol_spacing = [float(x) for x in ds.PixelSpacing]
                        if hasattr(ds, 'SliceThickness') and ds.SliceThickness:
                            vol_thickness = float(ds.SliceThickness)
                        metadata_extracted = True
                    except (TypeError, ValueError) as e:
                        logger.warning("No se pudo leer geometría de %s: %s", full_p, e)

                dcm_meta.append({"path": full_p, "z": z_val})

            except Exception as e:
                descartados_por_error += 1
                logger.warning(
                    "No se pudo leer %s como DICOM: %s (%s)",
                    full_p, e, type(e).__name__
                )

    logger.info(
        "Escaneo terminado: %d archivos candidatos, %d válidos, %d sin tags DICOM, %d con error de lectura",
        total_candidatos, len(dcm_meta), descartados_sin_tags, descartados_por_error
    )

    if not dcm_meta:
        logger.error(
            "No se detectaron archivos DICOM legibles en %s (candidatos=%d, sin_tags=%d, con_error=%d)",
            extracted_folder, total_candidatos, descartados_sin_tags, descartados_por_error
        )
        raise ValueError("No se encontraron archivos DICOM válidos en el archivo comprimido.")

    # Ordenar los archivos por su eje Z real
    dcm_meta.sort(key=lambda x: x["z"])
    num_slices = len(dcm_meta)
    logger.info("Archivos DICOM ordenados: %d. Procesando matriz volumétrica...", num_slices)

    # 2. Pre-asignar la matriz volumétrica 3D (256x256 en int16 usa menos de 40MB totales)
    volume_3d = np.zeros((256, 256, num_slices), dtype=np.int16)
    slice_filenames = []
    hu_min, hu_max = -1000.0, 400.0

    valid_slices_count = 0

    # 3. Procesar un corte a la vez para mantener la RAM limpia
    for meta in dcm_meta:
        try:
            ds = pydicom.dcmread(meta["path"], force=True)
            if not hasattr(ds, 'pixel_array'):
                logger.warning("Archivo sin pixel_array, se omite: %s", meta["path"])
                continue

            arr = ds.pixel_array.astype(np.float32)
            slope = float(getattr(ds, 'RescaleSlope', 1.0))
            intercept = float(getattr(ds, 'RescaleIntercept', 0.0))
            hu = arr * slope + intercept

            # Crear PNG 2D
            norm = np.clip(hu, hu_min, hu_max)
            norm = ((norm - hu_min) / (hu_max - hu_min) * 255.0).astype(np.uint8)
            img = Image.fromarray(norm)
            img_filename = f"slice_{valid_slices_count:03d}.png"
            img.save(os.path.join(output_folder, img_filename))
            slice_filenames.append(img_filename)

            # Guardar en matriz volumétrica 3D
            img_small = img.resize((256, 256), resample=Image.BILINEAR)
            volume_3d[:, :, valid_slices_count] = np.array(img_small, dtype=np.int16)

            valid_slices_count += 1

            # OOM FIX: Destruir el objeto DICOM pesado en cada iteración
            del ds, arr, hu, norm, img, img_small
            if valid_slices_count % 20 == 0:
                gc.collect()

        except Exception as e:
            logger.warning("Error procesando píxeles de %s: %s", meta['path'], e)

    if valid_slices_count == 0:
        raise ValueError("Los archivos DICOM encontrados no contienen datos de imagen válidos.")

    # Ajustar tamaño final si algún corte falló
    if valid_slices_count < num_slices:
        volume_3d = volume_3d[:, :, :valid_slices_count]

    volume_metadata = {
        "num_slices": valid_slices_count,
        "pixel_spacing": vol_spacing[0] * 2.0,
        "slice_thickness": vol_thickness
    }

    del dcm_meta
    gc.collect()

    return volume_3d, slice_filenames, volume_metadata
