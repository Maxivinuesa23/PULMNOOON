import { useState, useEffect, useRef } from "react";

/**
 * Cola simple de concurrencia limitada para la precarga de vecinos.
 * Nunca dispara más de `maxConcurrent` descargas de imagen al mismo tiempo.
 */
function createLimitedPreloader(maxConcurrent = 4) {
  let active = 0;
  const queue = [];
  const seen = new Set(); // evita re-precargar la misma URL varias veces

  const runNext = () => {
    if (active >= maxConcurrent || queue.length === 0) return;
    active++;
    const url = queue.shift();

    const img = new Image();
    const done = () => {
      active--;
      runNext();
    };
    img.onload = done;
    img.onerror = done;
    img.src = url;
  };

  return function preload(url) {
    if (!url || seen.has(url)) return;
    seen.add(url);
    queue.push(url);
    runNext();
  };
}

export default function SliceViewer({ slices = [] }) {
  const [currentIndex, setCurrentIndex] = useState(0);
  const preloaderRef = useRef(createLimitedPreloader(4));

  // Precarga silenciosa: el corte actual + 2 antes + 2 después.
  // No cambia lo que se ve (sigue siendo un solo <img>), solo hace que
  // moverse por el slider se sienta instantáneo porque la imagen ya
  // suele estar en la caché del navegador cuando el usuario llega a ella.
  useEffect(() => {
    if (!slices || slices.length === 0) return;
    const window = 2;
    for (let offset = -window; offset <= window; offset++) {
      const i = currentIndex + offset;
      if (i >= 0 && i < slices.length) {
        preloaderRef.current(slices[i]);
      }
    }
  }, [currentIndex, slices]);

  if (!slices || slices.length === 0) {
    return (
      <div className="w-full h-full min-h-[400px] flex items-center justify-center text-slate-500 bg-slate-900/50 rounded-2xl border border-slate-800">
        <div className="flex flex-col items-center gap-3">
          <svg className="w-12 h-12 opacity-50" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
          </svg>
          <p>No hay cortes 2D disponibles.</p>
        </div>
      </div>
    );
  }

  const handleSliderChange = (e) => {
    setCurrentIndex(Number(e.target.value));
  };

  return (
    <div className="flex flex-col w-full h-full bg-slate-900 rounded-2xl border border-slate-700/50 overflow-hidden shadow-2xl">
      {/* Image Container */}
      <div className="relative flex-1 flex items-center justify-center bg-black min-h-[320px] md:min-h-[400px] p-4">
        <img
          src={slices[currentIndex]}
          alt={`Corte transversal ${currentIndex + 1}`}
          className="max-w-full max-h-full object-contain filter contrast-125"
          onLoad={() => console.info("[2D] Corte cargado", currentIndex, slices[currentIndex])}
          onError={(error) => console.error("[2D] Error cargando corte", {
            index: currentIndex,
            url: slices[currentIndex],
            error,
          })}
        />

        {/* HUD Overlays */}
        <div className="absolute top-4 right-4 text-emerald-400 font-mono text-sm bg-black/60 backdrop-blur-sm px-3 py-1 rounded-md border border-emerald-500/30 flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
          Z: {currentIndex}
        </div>
        <div className="absolute bottom-4 left-4 text-slate-400 font-mono text-xs">
          DICOM VIEW
        </div>
      </div>

      {/* Controls */}
      <div className="p-6 bg-surface border-t border-slate-700/50 flex flex-col gap-4">
        <div className="flex justify-between items-center text-sm font-medium text-slate-300">
          <span>Axial Slices</span>
          <span className="bg-slate-800 px-3 py-1 rounded-full border border-slate-700 text-primary">
            Corte {currentIndex + 1} / {slices.length}
          </span>
        </div>

        <div className="relative w-full flex items-center">
          <input
            type="range"
            min="0"
            max={slices.length - 1}
            value={currentIndex}
            onChange={handleSliderChange}
            className="w-full h-2 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-primary hover:accent-blue-400 transition-all focus:outline-none focus:ring-2 focus:ring-primary/50"
          />
        </div>
      </div>
    </div>
  );
}
