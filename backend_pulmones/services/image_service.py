import os
import logging
import zipfile
import pydicom
from pydicom.errors import InvalidDicomError
import numpy as np
from PIL import Image

logger = logging.getLogger("cancer_detector.images")

def process_tomography_zip(zip_path: str, output_folder: str):
    """
    Descomprime el ZIP, detecta si son archivos DICOM (.dcm) o PNGs,
    genera las imágenes normalizadas para el visor 2D y retorna
    el volumen 3D en formato numpy array para la malla.
    """
    extract_dir = os.path.join(output_folder, "extracted_data")
    os.makedirs(extract_dir, exist_ok=True)
    
    # 1. Descomprimir el archivo ZIP recibido
    logger.info("Abriendo ZIP %s", zip_path)
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        root = os.path.realpath(extract_dir)
        for member in zip_ref.infolist():
            target = os.path.realpath(os.path.join(extract_dir, member.filename))
            if not target.startswith(root + os.sep):
                raise ValueError("El ZIP contiene una ruta no valida.")
        zip_ref.extractall(extract_dir)
    candidate_files = []
    
    # 2. Clasificar los archivos extraídos
    for root, _, files in os.walk(extract_dir):
        for file in files:
            full_path = os.path.join(root, file)
            if not file.startswith(".") and os.path.isfile(full_path):
                candidate_files.append(full_path)
    logger.info("Archivos candidatos encontrados: %d", len(candidate_files))

    dicom_slices = []
    image_files = []
    for path in candidate_files:
        try:
            ds = pydicom.dcmread(path, force=False)
            if hasattr(ds, "PixelData") and getattr(ds, "Rows", None) and getattr(ds, "Columns", None):
                dicom_slices.append(ds)
                continue
        except (InvalidDicomError, OSError, AttributeError, ValueError):
            pass
        try:
            with Image.open(path):
                image_files.append(path)
        except (OSError, ValueError):
            pass
    logger.info("DICOM detectados=%d imagenes=%d", len(dicom_slices), len(image_files))

    slice_filenames = []
    volume_list = []
    metadata = {
        "pixel_spacing": [0.7, 0.7],
        "slice_thickness": 2.5,
        "is_dicom": False,
        "slice_positions": [],
    }

    # 3. Rama A: Si el ZIP contiene DICOMs reales
    if dicom_slices:
        slices = []
        for ds in dicom_slices:
            try:
                if ds.pixel_array.ndim == 2:
                    slices.append(ds)
            except (AttributeError, ValueError, OSError) as error:
                print(f"[Image Service] Error decodificando DICOM: {error}")
                
        # Ordenar cortes por posición en el eje Z si está disponible
        try:
            slices.sort(key=lambda s: float(s.ImagePositionPatient[2]) if hasattr(s, 'ImagePositionPatient') else 0.0)
        except Exception:
            pass

        if slices:
            metadata["is_dicom"] = True
            spacing = getattr(slices[0], "PixelSpacing", [0.7, 0.7])
            metadata["pixel_spacing"] = [float(spacing[0]), float(spacing[1])]
            metadata["slice_thickness"] = float(getattr(slices[0], "SliceThickness", 2.5))
            positions = []
            for ds in slices:
                position = getattr(ds, "ImagePositionPatient", None)
                if position is not None and len(position) >= 3:
                    positions.append(float(position[2]))
            if len(positions) == len(slices):
                first = positions[0]
                metadata["slice_positions"] = [position - first for position in positions]
        for i, ds in enumerate(slices):
            hu_arr = ds.pixel_array.astype(np.float32)
            hu_arr = hu_arr * float(getattr(ds, "RescaleSlope", 1.0)) + float(getattr(ds, "RescaleIntercept", 0.0))
            arr = hu_arr.copy()
            # Normalizar píxeles a rango 0-255 para visualización web
            if arr.max() > arr.min():
                arr = ((arr - arr.min()) / (arr.max() - arr.min())) * 255.0
            arr = arr.astype(np.uint8)
            
            # Guardar PNG exportado
            img = Image.fromarray(arr).convert('RGB')
            filename = f"slice_{i:03d}.png"
            img.save(os.path.join(output_folder, filename))
            slice_filenames.append(filename)
            
            volume_list.append(hu_arr)

        volume_3d = np.stack(volume_list, axis=0) if volume_list else None
        if volume_3d is None:
            raise ValueError("El ZIP contiene DICOM, pero no se pudieron decodificar sus pixeles.")
        return volume_3d, slice_filenames, metadata

    # 4. Rama B: Si el ZIP contiene los PNGs sintéticos de prueba
    elif image_files:
        image_files.sort()
        for i, f_path in enumerate(image_files):
            filename = f"slice_{i:03d}.png"
            dest_path = os.path.join(output_folder, filename)
            
            # Copiar y convertir a escala de grises para volumen 3D sintético
            img = Image.open(f_path).convert('L')
            img.save(dest_path)
            slice_filenames.append(filename)
            volume_list.append(np.array(img, dtype=np.float32))
            
        volume_3d = np.stack(volume_list, axis=0) if volume_list else None
        return volume_3d, slice_filenames, metadata

    raise ValueError("El ZIP no contiene cortes DICOM ni imagenes compatibles.")