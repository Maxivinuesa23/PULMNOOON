import os
import numpy as np
import trimesh
from skimage import measure
import gc
import logging

logger = logging.getLogger("cancer_detector.mesh")

def generate_3d_mesh(volume_3d: np.ndarray, output_folder: str, detections: list = None, metadata: dict = None):
    os.makedirs(output_folder, exist_ok=True)
    out_path = os.path.join(output_folder, "mesh.glb") # GLB es binario y mucho más ligero
    
    # Reducción espacial previa (paso 2)
    vol_sub = volume_3d[::2, ::2, ::2]
    
    scene = trimesh.Scene()
    
    try:
        # Parénquima externo con step_size amplio para reducir vértices
        verts_p, faces_p, _, _ = measure.marching_cubes(vol_sub, level=40, step_size=2)
        mesh_pulmon = trimesh.Trimesh(vertices=verts_p, faces=faces_p)
        mesh_pulmon.metadata['name'] = 'pulmon_externo'
        mesh_pulmon.visual.vertex_colors = [244, 155, 155, 120]
        scene.add_geometry(mesh_pulmon, node_name="pulmon_externo")
        del verts_p, faces_p, mesh_pulmon
    except Exception as e:
        logger.warning("Error al extraer parénquima 3D: %s", e)

    try:
        # Árbol bronquial interno
        verts_b, faces_b, _, _ = measure.marching_cubes(vol_sub, level=110, step_size=2)
        mesh_bronquios = trimesh.Trimesh(vertices=verts_b, faces=faces_b)
        mesh_bronquios.metadata['name'] = 'arbol_bronquial'
        mesh_bronquios.visual.vertex_colors = [217, 107, 107, 255]
        scene.add_geometry(mesh_bronquios, node_name="arbol_bronquial")
        del verts_b, faces_b, mesh_bronquios
    except Exception as e:
        logger.warning("Error al extraer árbol bronquial 3D: %s", e)

    del vol_sub
    gc.collect()

    scene.export(out_path)
    return out_path