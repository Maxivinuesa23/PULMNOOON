import os
import zipfile
import pydicom
from pydicom.errors import InvalidDicomError
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
        # Ignorar metadatos de macOS
        if "__MACOSX" in root:
            continue
        for f in files:
            if f.startswith(".") or f.lower().endswith((".xml", ".txt", ".json")):
                continue
            full_p = os.path.join(root, f)
            try:
                # force=True es indispensable para leer DICOMs sin preámbulo estándar
                ds = pydicom.dcmread(full_p, stop_before_pixels=True, force=True)
                if hasattr(ds, 'SOPClassUID') or hasattr(ds, 'pixel_array') or hasattr(ds, 'ImagePositionPatient'):
                    dcm_files.append(full_p)
            except Exception:
                pass

    if not dcm_files:
        logger.error("No se detectaron archivos DICOM en %s", extracted_folder)
        raise ValueError("No se encontraron archivos DICOM válidos en el archivo comprimido.")

    logger.info("Archivos DICOM candidatos: %d. Cargando metadatos y cortes...", len(dcm_files))

    # Cargar y ordenar por ImagePositionPatient Z o InstanceNumber
    slices = []
    for f in dcm_files:
        try:
            ds = pydicom.dcmread(f, force=True)
            if hasattr(ds, 'pixel_array'):
                slices.append(ds)
        except Exception as e:
            logger.debug("Omitiendo archivo no válido %s: %s", f, e)

    if not slices:
        raise ValueError("Los archivos encontrados no contienen matrices de imagen (pixel_array).")

    # Ordenar espacialmente por eje Z (o por número de instancia si no tiene posición espacial)
    if hasattr(slices[0], 'ImagePositionPatient'):
        slices.sort(key=lambda s: float(s.ImagePositionPatient[2]))
    elif hasattr(slices[0], 'InstanceNumber'):
        slices.sort(key=lambda s: int(s.InstanceNumber))

    num_slices = len(slices)
    logger.info("Cortes DICOM válidos y ordenados: %d", num_slices)

    # Creamos la matriz volumétrica 3D a 256x256 en int16 para no exceder los 512MB de Render
    volume_3d = np.zeros((256, 256, num_slices), dtype=np.int16)
    slice_filenames = []
    
    hu_min, hu_max = -1000.0, 400.0

    for i, s in enumerate(slices):
        arr = s.pixel_array.astype(np.float32)
        slope = float(getattr(s, 'RescaleSlope', 1.0))
        intercept = float(getattr(s, 'RescaleIntercept', 0.0))
        hu = arr * slope + intercept
        
        # Normalizar para ventana de visualización pulmonar estándar
        norm = np.clip(hu, hu_min, hu_max)
        norm = ((norm - hu_min) / (hu_max - hu_min) * 255.0).astype(np.uint8)
        
        img = Image.fromarray(norm)
        img_filename = f"slice_{i:03d}.png"
        img.save(os.path.join(output_folder, img_filename))
        slice_filenames.append(img_filename)
        
        # Submuestreo para la malla volumétrica 3D
        img_small = img.resize((256, 256), resample=Image.BILINEAR)
        volume_3d[:, :, i] = np.array(img_small, dtype=np.int16)

    volume_metadata = {
        "num_slices": num_slices,
        "pixel_spacing": float(getattr(slices[0], 'PixelSpacing', [0.7, 0.7])[0]) * 2,
        "slice_thickness": float(getattr(slices[0], 'SliceThickness', 2.5))
    }

    # Limpieza inmediata de memoria RAM
    del slices
    del dcm_files
    gc.collect()

    return volume_3d, slice_filenames, volume_metadata