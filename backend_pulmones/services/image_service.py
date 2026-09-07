import os
import zipfile
import pydicom
import numpy as np
from PIL import Image
import gc
import logging

logger = logging.getLogger("cancer_detector.images")

def process_tomography_zip(file_path: str, output_folder: str):
    logger.info("Extrayendo archivo ZIP: %s", file_path)
    extracted_folder = os.path.join(output_folder, "extracted_data")
    os.makedirs(extracted_folder, exist_ok=True)
    
    with zipfile.ZipFile(file_path, 'r') as zip_ref:
        zip_ref.extractall(extracted_folder)
        
    dcm_files = []
    for root, _, files in os.walk(extracted_folder):
        for f in files:
            full_p = os.path.join(root, f)
            try:
                # Lectura rápida solo de cabeceras para validar DICOM sin cargar pixels a RAM
                pydicom.dcmread(full_p, stop_before_pixels=True)
                dcm_files.append(full_p)
            except Exception:
                pass

    if not dcm_files:
        raise ValueError("No se encontraron archivos DICOM válidos en el archivo comprimido.")

    # Ordenar por ubicación Z
    slices = []
    for f in dcm_files:
        try:
            ds = pydicom.dcmread(f)
            if hasattr(ds, 'ImagePositionPatient'):
                slices.append(ds)
        except Exception:
            pass

    slices.sort(key=lambda s: float(s.ImagePositionPatient[2]))
    num_slices = len(slices)
    logger.info("Cortes DICOM ordenados: %d", num_slices)

    # 1. Crear volumen submuestreado o en int16 para no saturar los 512MB
    # Usar resolución 256x256 para el volumen 3D en lugar de 512x512 ahorra un 75% de RAM
    volume_3d = np.zeros((256, 256, num_slices), dtype=np.int16)
    slice_filenames = []
    
    hu_min, hu_max = -1000.0, 400.0

    for i, s in enumerate(slices):
        arr = s.pixel_array.astype(np.float32)
        slope = float(getattr(s, 'RescaleSlope', 1.0))
        intercept = float(getattr(s, 'RescaleIntercept', 0.0))
        hu = arr * slope + intercept
        
        # Guardar corte PNG 2D (a 256x256 o 512x512)
        norm = np.clip(hu, hu_min, hu_max)
        norm = ((norm - hu_min) / (hu_max - hu_min) * 255.0).astype(np.uint8)
        
        img = Image.fromarray(norm)
        img_filename = f"slice_{i:03d}.png"
        img.save(os.path.join(output_folder, img_filename))
        slice_filenames.append(img_filename)
        
        # Reducir corte para la matriz volumétrica 3D
        img_small = img.resize((256, 256), resample=Image.BILINEAR)
        volume_3d[:, :, i] = np.array(img_small, dtype=np.int16)

    # Metadata básica
    volume_metadata = {
        "num_slices": num_slices,
        "pixel_spacing": float(getattr(slices[0], 'PixelSpacing', [0.7, 0.7])[0]) * 2,
        "slice_thickness": float(getattr(slices[0], 'SliceThickness', 2.5))
    }

    # Limpieza inmediata de memoria
    del slices
    del dcm_files
    gc.collect()

    return volume_3d, slice_filenames, volume_metadata