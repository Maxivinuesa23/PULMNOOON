import os
import zipfile
import pydicom
import numpy as np
from PIL import Image
import gc
import logging

logger = logging.getLogger("cancer_detector.images")

def is_dicom_file(file_path: str) -> bool:
    """Verifica si un archivo es DICOM de manera confiable y ligera."""
    if os.path.isdir(file_path):
        return False
    # Omitir archivos del sistema o metadatos de compresión
    base = os.path.basename(file_path)
    if base.startswith(".") or base.startswith("__") or base.lower().endswith((".xml", ".txt", ".json", ".pdf", ".png", ".jpg")):
        return False
    
    try:
        # force=True permite leer archivos DICOM que no traen el encabezado estándar de 128 bytes
        ds = pydicom.dcmread(file_path, stop_before_pixels=True, force=True)
        return hasattr(ds, 'SOPClassUID') or hasattr(ds, 'Modality') or hasattr(ds, 'pixel_array') or hasattr(ds, 'SliceLocation') or hasattr(ds, 'ImagePositionPatient')
    except Exception:
        return False

def process_tomography_zip(file_path: str, output_folder: str):
    logger.info("Extrayendo archivo ZIP: %s", file_path)
    extracted_folder = os.path.join(output_folder, "extracted_data")
    os.makedirs(extracted_folder, exist_ok=True)
    
    with zipfile.ZipFile(file_path, 'r') as zip_ref:
        zip_ref.extractall(extracted_folder)
        
    dcm_files = []
    for root, _, files in os.walk(extracted_folder):
        if "__MACOSX" in root:
            continue
        for f in files:
            full_p = os.path.join(root, f)
            if is_dicom_file(full_p):
                dcm_files.append(full_p)

    if not dcm_files:
        logger.error("No se detectaron archivos DICOM en el directorio extraído: %s", extracted_folder)
        raise ValueError("No se encontraron archivos DICOM válidos en el archivo comprimido.")

    logger.info("Archivos DICOM identificados: %d. Leyendo cortes...", len(dcm_files))

    # Cargar datasets y ordenar
    slices = []
    for f in dcm_files:
        try:
            ds = pydicom.dcmread(f, force=True)
            if hasattr(ds, 'pixel_array'):
                slices.append(ds)
        except Exception as e:
            logger.debug("Omitiendo archivo sin matriz de píxeles %s: %s", f, e)

    if not slices:
        raise ValueError("Los archivos DICOM encontrados no contienen datos de imagen válidos.")

    # Ordenar por posición Z (ImagePositionPatient[2]) o por InstanceNumber
    if hasattr(slices[0], 'ImagePositionPatient') and slices[0].ImagePositionPatient:
        slices.sort(key=lambda s: float(s.ImagePositionPatient[2]))
    elif hasattr(slices[0], 'InstanceNumber'):
        slices.sort(key=lambda s: int(s.InstanceNumber))

    num_slices = len(slices)
    logger.info("Total de cortes DICOM procesables ordenados: %d", num_slices)

    # Matriz volumétrica reducida a 256x256 en int16 para no exceder los 512MB de RAM
    volume_3d = np.zeros((256, 256, num_slices), dtype=np.int16)
    slice_filenames = []
    
    hu_min, hu_max = -1000.0, 400.0

    for i, s in enumerate(slices):
        arr = s.pixel_array.astype(np.float32)
        slope = float(getattr(s, 'RescaleSlope', 1.0))
        intercept = float(getattr(s, 'RescaleIntercept', 0.0))
        hu = arr * slope + intercept
        
        # Normalizar para ventana pulmonar estándar
        norm = np.clip(hu, hu_min, hu_max)
        norm = ((norm - hu_min) / (hu_max - hu_min) * 255.0).astype(np.uint8)
        
        img = Image.fromarray(norm)
        img_filename = f"slice_{i:03d}.png"
        img.save(os.path.join(output_folder, img_filename))
        slice_filenames.append(img_filename)
        
        # Almacenar en el volumen 3D con resolución controlada
        img_small = img.resize((256, 256), resample=Image.BILINEAR)
        volume_3d[:, :, i] = np.array(img_small, dtype=np.int16)

    # Extraer metadatos geométricos del primer corte
    pixel_spacing = [0.7, 0.7]
    if hasattr(slices[0], 'PixelSpacing') and slices[0].PixelSpacing:
        pixel_spacing = [float(x) for x in slices[0].PixelSpacing]

    slice_thickness = float(getattr(slices[0], 'SliceThickness', 2.5))

    volume_metadata = {
        "num_slices": num_slices,
        "pixel_spacing": pixel_spacing[0] * 2.0,
        "slice_thickness": slice_thickness
    }

    # Limpiar referencias para liberar memoria de inmediato
    del slices
    del dcm_files
    gc.collect()

    return volume_3d, slice_filenames, volume_metadata