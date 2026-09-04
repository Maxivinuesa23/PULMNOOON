import { BeakerIcon, ClockIcon } from "@heroicons/react/24/outline";

export default function Loader() {
  return <div className="processing-card">
    <div className="processing-orb"><BeakerIcon /><span /></div>
    <span className="section-kicker">ANÁLISIS EN CURSO</span>
    <h1>Procesando tu estudio</h1>
    <p>Estamos segmentando los cortes DICOM y preparando la reconstrucción volumétrica.</p>
    <div className="processing-track"><div /></div>
    <div className="processing-status"><ClockIcon /> Esto puede tardar unos minutos</div>
  </div>;
}
