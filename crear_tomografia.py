import os
import zipfile
from PIL import Image, ImageDraw

def generar_tomografia_sintetica():
    carpeta_temp = "cortes_temp"
    os.makedirs(carpeta_temp, exist_ok=True)
    archivos_generados = []

    print("Dibujando cortes tomográficos...")
    # Generamos 10 cortes de la tomografía (Eje Z)
    for z in range(10):
        # Fondo negro (512x512 píxeles, escala de grises 'L')
        img = Image.new('L', (512, 512), color=0)
        draw = ImageDraw.Draw(img)

        # 1. Tórax / Tejido exterior (Gris claro)
        draw.ellipse((80, 150, 432, 350), fill=80)

        # 2. Pulmón Izquierdo (Gris muy oscuro, lleno de aire)
        draw.ellipse((120, 170, 230, 330), fill=20)

        # 3. Pulmón Derecho (Gris muy oscuro)
        draw.ellipse((280, 170, 390, 330), fill=20)

        # 4. Nódulo / Posible tumor (Solo visible en los cortes intermedios)
        if 3 <= z <= 6:
            # El tumor cambia de tamaño según el corte para simular 3D
            radio = 6 if z in (3, 6) else 12 
            centro_x, centro_y = 330, 260
            draw.ellipse(
                (centro_x - radio, centro_y - radio, centro_x + radio, centro_y + radio), 
                fill=220 # Blanco/Gris muy claro, resalta en la TC
            )

        # Guardamos la imagen PNG
        nombre_archivo = f"{carpeta_temp}/corte_{z:02d}.png"
        img.save(nombre_archivo)
        archivos_generados.append(nombre_archivo)

    # Empaquetamos todo en un ZIP
    nombre_zip = "tomografia_sintetica.zip"
    print(f"Empaquetando {len(archivos_generados)} imágenes en {nombre_zip}...")
    
    with zipfile.ZipFile(nombre_zip, 'w') as zipf:
        for archivo in archivos_generados:
            zipf.write(archivo, os.path.basename(archivo))

    # Limpiamos las imágenes sueltas
    for archivo in archivos_generados:
        os.remove(archivo)
    os.rmdir(carpeta_temp)

    print("¡Listo! Ya tienes tu archivo listo para subir al sistema.")

if __name__ == "__main__":
    generar_tomografia_sintetica()