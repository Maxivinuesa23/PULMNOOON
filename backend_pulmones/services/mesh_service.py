import logging
import os

import numpy as np
import trimesh
from scipy import ndimage
from skimage import measure

logger = logging.getLogger("cancer_detector.mesh")


def _make_surface(mask, spacing):
    smoothed = ndimage.gaussian_filter(mask.astype(np.float32), sigma=1)
    vertices, faces, normals, _ = measure.marching_cubes(
        smoothed, level=0.5, spacing=spacing, step_size=2
    )
    return trimesh.Trimesh(
        vertices=vertices, faces=faces, vertex_normals=normals, process=False
    )


def generate_3d_mesh(volume_3d: np.ndarray, output_folder: str,
                     detections=None, metadata=None):
    if volume_3d is None or volume_3d.ndim != 3:
        raise ValueError("Volumen 3D invalido.")
    metadata = metadata or {}
    spacing_xy = metadata.get("pixel_spacing", [0.7, 0.7])
    z_positions = metadata.get("slice_positions") or []
    z_spacing = float(metadata.get("slice_thickness", 2.5))
    if len(z_positions) > 1:
        z_spacing = float(np.median(np.abs(np.diff(z_positions)))) or z_spacing
    spacing = (z_spacing, float(spacing_xy[0]), float(spacing_xy[1]))
    volume = volume_3d.astype(np.float32)

    if metadata.get("is_dicom"):
        lung_mask = (volume >= -1000) & (volume <= -250)
    else:
        values = volume[volume > volume.min()]
        cutoff = np.percentile(values, 60) if values.size else volume.min()
        lung_mask = (volume > volume.min()) & (volume <= cutoff)
    labels, count = ndimage.label(lung_mask)
    if count:
        sizes = ndimage.sum(lung_mask, labels, range(1, count + 1))
        lung_mask = np.isin(labels, np.argsort(sizes)[-2:] + 1)
    if not np.any(lung_mask):
        raise ValueError("No se detecto parenquima pulmonar.")

    lung = _make_surface(lung_mask, spacing)
    lung.visual.vertex_colors = [244, 155, 155, 210]
    scene = trimesh.Scene([lung])
    for detection in (detections or [])[:8]:
        index = int(detection["slice"])
        z = float(z_positions[index]) if index < len(z_positions) else index * spacing[0]
        x = (float(detection["x"]) + float(detection["width"]) / 2) * spacing[2]
        y = (float(detection["y"]) + float(detection["height"]) / 2) * spacing[1]
        radius = max(float(detection["width"]), float(detection["height"])) * spacing[1] * 0.18
        marker = trimesh.creation.icosphere(subdivisions=2, radius=max(radius, 1.5))
        marker.apply_translation((z, y, x))
        marker.visual.vertex_colors = [242, 116, 18, 255]
        scene.add_geometry(marker)

    output_path = os.path.join(output_folder, "mesh.glb")
    scene.export(output_path, file_type="glb")
    logger.info("Malla 3D exportada en %s (%d bytes)", output_path, os.path.getsize(output_path))
    return output_path
