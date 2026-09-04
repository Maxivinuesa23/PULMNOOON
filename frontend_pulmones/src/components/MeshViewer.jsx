import React, { useState, useMemo, useEffect } from "react";
import { Canvas } from "@react-three/fiber";
import { OrbitControls, useGLTF, Center } from "@react-three/drei";
import * as THREE from "three";

function AnatomicalModel({ detections }) {
  // Carga el modelo prefabricado desde la carpeta public/
  const { scene } = useGLTF("/lung_template.glb");

  // 1. Efecto de cristal translúcido (Rayos X)
  useEffect(() => {
    if (scene) {
      scene.traverse((child) => {
        if (child.isMesh) {
          child.material = new THREE.MeshPhysicalMaterial({
            color: 0x93c5fd, // Azul médico suave
            transmission: 0.85, // Efecto vidrio
            transparent: true,
            opacity: 0.4,
            roughness: 0.1,
            depthWrite: false, // Evita que las caras internas bloqueen a las externas
            side: THREE.DoubleSide,
          });
        }
      });
    }
  }, [scene]);

  // 2. Medir automáticamente la "caja" que ocupa el modelo 3D
  const { box, size } = useMemo(() => {
    const boundingBox = new THREE.Box3().setFromObject(scene);
    const boundingSize = boundingBox.getSize(new THREE.Vector3());
    return { box: boundingBox, size: boundingSize };
  }, [scene]);

  return (
    <group>
      <primitive object={scene} />
      
      {/* 3. Mapeo calibrado de anomalías (Filtramos las 5 principales) */}
      {detections.slice(0, 5).map((detection, index) => {
        // Dimensiones reales de tu tomografía DICOM original
        const resolution = 512; 
        const totalSlices = 133; 

        // Factor de compresión: Los pulmones no ocupan todo el ancho del DICOM.
        // Ajusta este valor (ej. 0.55 o 0.75) si los puntos quedan muy afuera o muy adentro.
        const scale = 0.65;

        // Normalizamos la posición acercándola hacia el centro (0.5)
        const normX = 0.5 + ((Number(detection.x) / resolution) - 0.5) * scale;
        const normY = 0.5 + ((Number(detection.y) / resolution) - 0.5) * scale;
        const normZ = Number(detection.slice) / totalSlices;

        // Proyectamos el porcentaje EXACTAMENTE dentro de los límites del modelo 3D
        // Invertimos normY porque las imágenes 2D se miden de arriba a abajo, y el 3D de abajo a arriba
        const finalX = box.min.x + (normX * size.x);
        const finalY = box.max.y - (normY * size.y); 
        const finalZ = box.min.z + (normZ * size.z);

        return (
          <mesh key={`anomaly-${index}`} position={[finalX, finalY, finalZ]}>
            {/* Aumentamos el radio a 0.8 para visibilidad clínica clara */}
            <sphereGeometry args={[0.8, 32, 32]} />
            <meshStandardMaterial 
              color="#ff2a00" 
              emissive="#ff4400" 
              emissiveIntensity={2.5} 
            />
          </mesh>
        );
      })}
    </group>
  );
}

export default function MeshViewer({ detections = [] }) {
  const [mode, setMode] = useState("complete");

  return (
    <div className="w-full h-[450px] relative rounded-xl overflow-hidden bg-slate-950 border border-slate-800">
      
      {/* Botonera superior */}
      <div className="absolute top-3 left-3 z-10 flex gap-2 bg-slate-900/80 p-1 rounded-lg">
        <button 
          onClick={() => setMode("complete")} 
          className={`px-3 py-1 text-xs rounded transition-colors ${
            mode === "complete" ? "bg-blue-600 text-white" : "text-slate-300 hover:text-white"
          }`}
        >
          Anatomía 3D
        </button>
      </div>
      
      {/* Escena 3D */}
      <Canvas camera={{ position: [0, 0, 15], fov: 50 }}>
        <color attach="background" args={["#0f172a"]} />
        <ambientLight intensity={1.5} />
        <directionalLight position={[10, 10, 10]} intensity={1} />
        <directionalLight position={[-10, -10, -10]} intensity={0.5} />
        
        {/* Contenedor que centra el modelo automáticamente */}
        <Center>
          <AnatomicalModel detections={detections} />
        </Center>
        
        <OrbitControls 
          enablePan={true} 
          enableZoom={true} 
          enableRotate={true} 
          autoRotate={true} 
          autoRotateSpeed={1.0} 
        />
      </Canvas>
      
      {/* Leyenda inferior */}
      <div className="absolute bottom-2 left-3 text-xs text-slate-400 z-10 bg-slate-950/50 px-2 py-1 rounded">
        <span className="inline-block w-2 h-2 rounded-full bg-red-500 mr-2 animate-pulse"></span>
        Posible anomalía · Arrastra para rotar
      </div>
    </div>
  );
}