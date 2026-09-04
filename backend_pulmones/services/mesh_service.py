import logging
import os
import numpy as np
import trimesh
from scipy import ndimage
from skimage import measure

logger = logging.getLogger("cancer_detector.mesh")

def _make_surface(mask, spacing):
    smoothed = ndimage.gaussian_filter(mask.astype(np.float32), sigma=1)
    # Generar malla usando marching_cubes
    verts, faces, normals, _ = measure.marching_cubes(
        smoothed, level=0.5, spacing=spacing, step_size=2
    )
    if len(verts) == 0 or len(faces) == 0:
        # Fallback seguro si la máscara está vacía
        verts = np.array([[0,0,0], [1,0,0], [0,1,0], [0,0,1]], dtype=float)
        faces = np.array([[0,1,2]], dtype=int)
        normals = np.array([[0,0,1]]*3, dtype=float)

    return trimesh.Trimesh(
        vertices=verts, faces=faces, vertex_normals=normals, process=False
    )

def generate_3d_mesh(volume_3d: np.ndarray, output_folder: str, detections=None, metadata=None):
    if volume_3d is None or volume_3d.ndim != 3:
        raise ValueError("Volumen 3D inválido.")
    
    metadata = metadata or {}
    spacing_xy = metadata.get("pixel_spacing", [0.7, 0.7])
    z_positions = metadata.get("slice_positions") or []
    z_spacing = float(metadata.get("slice_thickness", 2.5))
    
    if len(z_positions) > 1:
        z_spacing = float(np.median(np.abs(np.diff(z_positions)))) or z_spacing
        
    spacing = (z_spacing, float(spacing_xy[0]), float(spacing_xy[1]))
    volume = volume_3d.astype(np.float32)

    # 1. Extracción precisa del parénquima pulmonar (rango de aire/tejido blando interno)
    if metadata.get("is_dicom"):
        lung_mask = (volume >= -1024) & (volume <= -300)
    else:
        v_min = volume.min()
        values = volume[volume > v_min]
        cutoff = np.percentile(values, 50) if values.size else v_min
        lung_mask = (volume > v_min) & (volume <= cutoff)

    labels, count = ndimage.label(lung_mask)
    if count:
        sizes = ndimage.sum(lung_mask, labels, range(1, count + 1))
        # Seleccionar los componentes principais correspondientes a los pulmones
        valid_labels = np.argsort(sizes)[-2:] + 1
        lung_mask = np.isin(labels, valid_labels)

    if not np.any(lung_mask):
        lung_mask = volume > volume.min()  # Fallback de respaldo

    lung = _make_surface(lung_mask, spacing)
    lung.visual.vertex_colors = [200, 220, 240, 140]  # Translúcido tipo cristal médico
    scene = trimesh.Scene([lung])

    # Dimensiones de la matriz para escalado de coordenadas de detecciones
    depth, height, width = volume_3d.shape

    # 2. Posicionamiento real de anomalías basadas en las coordenadas de la IA
    for detection in (detections or [])[:15]:
        try:
            index = int(detection["slice"])
            z = float(z_positions[index]) if index < len(z_positions) else index * spacing[0]
            
            # Mapear coordenadas relativas o absolutas de la caja delimitadora (bounding box)
            x_min = float(detection["x"])
            y_min = float(detection["y"])
            w = float(detection["width"])
            h = float(detection["height"])
            
            # Centro de la detección escalado al espacio físico tridimensional
            x_center = (x_min + w / 2.0) * spacing[2]
            y_center = (y_min + h / 2.0) * spacing[1]
            
            radius = max(w, h) * spacing[1] * 0.25
            marker = trimesh.creation.icosphere(subdivisions=2, radius=max(radius, 2.0))
            
            # Aplicar traslación exacta en el espacio de Three.js (Z, Y, X)
            marker.apply_translation((z, y_center, x_center))
            marker.visual.vertex_colors = [239, 68, 68, 255]  # Rojo clínico destacado
            scene.add_geometry(marker)
        except Exception as e:
            logger.warning(f"Error procesando una detección para el 3D: {e}")

    output_path = os.path.join(output_folder, "mesh.glb")
    scene.export(output_path, file_type="glb")
    logger.info("Malla 3D exportada en %s", output_path)
    return output_path