import { useState } from "react";
import { Canvas } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";

function StaticLung({ detections, mode }) {
  const lungMaterial = {
    color: "#f28b8b",
    transparent: true,
    opacity: mode === "complete" ? 0.9 : 0.32,
    roughness: 0.75,
  };
  return (
    <group>
      <mesh position={[-1.05, 0, 0]} scale={[0.95, 1.65, 0.82]}>
        <sphereGeometry args={[1, 40, 28]} />
        <meshStandardMaterial {...lungMaterial} />
      </mesh>
      <mesh position={[1.05, 0, 0]} scale={[0.95, 1.65, 0.82]}>
        <sphereGeometry args={[1, 40, 28]} />
        <meshStandardMaterial {...lungMaterial} />
      </mesh>
      <mesh position={[0, 1.8, 0]} scale={[0.16, 0.72, 0.16]}>
        <cylinderGeometry args={[1, 1, 1, 20]} />
        <meshStandardMaterial color="#65c6d6" />
      </mesh>
      <mesh position={[-0.34, 1.2, 0]} rotation={[0, 0, -0.6]} scale={[0.1, 0.65, 0.1]}>
        <cylinderGeometry args={[1, 1, 1, 16]} />
        <meshStandardMaterial color="#65c6d6" />
      </mesh>
      <mesh position={[0.34, 1.2, 0]} rotation={[0, 0, 0.6]} scale={[0.1, 0.65, 0.1]}>
        <cylinderGeometry args={[1, 1, 1, 16]} />
        <meshStandardMaterial color="#65c6d6" />
      </mesh>
      {detections.slice(0, 8).map((detection, index) => (
        <mesh key={`${detection.slice}-${index}`} position={[
          Number(detection.x) / 256 - 1,
          1.25 - Number(detection.slice) / 10 * 2.5,
          0.78,
        ]}>
          <sphereGeometry args={[0.13, 20, 16]} />
          <meshStandardMaterial color="#f28a18" emissive="#7a2600" emissiveIntensity={0.5} />
        </mesh>
      ))}
    </group>
  );
}

export default function MeshViewer({ detections = [] }) {
  const [mode, setMode] = useState("complete");
  return (
    <div className="w-full h-[450px] relative rounded-xl overflow-hidden bg-slate-950 border border-slate-800">
      <div className="absolute top-3 left-3 z-10 flex gap-2 bg-slate-900/80 p-1 rounded-lg">
        <button onClick={() => setMode("complete")} className="px-3 py-1 text-xs text-white">Pulmón completo</button>
        <button onClick={() => setMode("interior")} className="px-3 py-1 text-xs text-slate-300">Interior</button>
      </div>
      <Canvas camera={{ position: [0, 0, 6], fov: 45 }}>
        <color attach="background" args={["#0f172a"]} />
        <ambientLight intensity={1.2} />
        <directionalLight position={[4, 5, 6]} intensity={1.5} />
        <StaticLung detections={detections} mode={mode} />
        <OrbitControls enablePan enableZoom enableRotate />
      </Canvas>
      <div className="absolute bottom-2 left-3 text-xs text-slate-400">
        Naranja: posible anomalía · Arrastra para rotar
      </div>
    </div>
  );
}
