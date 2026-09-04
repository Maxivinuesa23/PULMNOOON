import { useState } from "react";
import {
  ArrowPathIcon,
  BeakerIcon,
  CheckCircleIcon,
  ClockIcon,
  ExclamationTriangleIcon,
  InformationCircleIcon,
  ShieldCheckIcon,
  SparklesIcon,
} from "@heroicons/react/24/outline";
import UploadZone from "../components/UploadZone";
import SliceViewer from "../components/SliceViewer";
import MeshViewer from "../components/MeshViewer";
import Loader from "../components/Loader";
import { checkTaskStatus, validateWithGemini } from "../services/api";

const navItems = ["Nuevo análisis", "Estudios recientes", "Guía clínica"];

export default function Dashboard() {
  const [appState, setAppState] = useState("upload");
  const [analysisResults, setAnalysisResults] = useState(null);
  const [processingError, setProcessingError] = useState("");
  const [geminiState, setGeminiState] = useState("");

  const handleUploadSuccess = async (responseData) => {
    setAppState("processing");
    setProcessingError("");
    const taskId = responseData.task_id;
    let intervalId;
    let finished = false;
    const poll = async () => {
      if (finished) return;
      try {
        const statusData = await checkTaskStatus(taskId);
        if (statusData.status === "completed") {
          finished = true;
          clearInterval(intervalId);
          setAnalysisResults({ ...statusData.results, taskId });
          setAppState("results");
        } else if (statusData.status === "not_found" || statusData.status === "error") {
          finished = true;
          clearInterval(intervalId);
          setProcessingError(statusData.message || "El backend no pudo procesar el ZIP.");
          setAppState("upload");
        }
      } catch (error) {
        finished = true;
        clearInterval(intervalId);
        setProcessingError(error.message || "No se pudo consultar el backend.");
        setAppState("upload");
      }
    };
    poll();
    setTimeout(() => {
      if (!finished) intervalId = setInterval(poll, 2000);
    }, 2000);
  };

  const handleReset = () => {
    setAppState("upload");
    setAnalysisResults(null);
    setGeminiState("");
  };

  const handleGeminiValidation = async () => {
    if (!analysisResults?.taskId) return setGeminiState("No hay identificador de análisis");
    setGeminiState("Analizando...");
    try {
      const result = await validateWithGemini(analysisResults.taskId);
      setAnalysisResults((current) => ({ ...current, ...result }));
      setGeminiState("Validación completada");
    } catch (error) {
      setGeminiState(`Error: ${error.message}`);
    }
  };

  const detected = Boolean(analysisResults?.tumorDetected);
  const stats = analysisResults?.stats;

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <div className="brand-mark"><BeakerIcon /></div>
          <div><strong>Pulmo<span>Scan</span></strong><small>Asistencia radiológica</small></div>
        </div>
        <nav aria-label="Navegación principal">
          {navItems.map((item, index) => <button key={item} className={index === 0 ? "nav-link active" : "nav-link"}>{item}</button>)}
        </nav>
        <div className="secure-badge"><ShieldCheckIcon /> Entorno seguro</div>
      </header>

      <main className="page-content">
        <div className="eyebrow"><span className="status-dot" /> PLATAFORMA DE ANÁLISIS DICOM <span className="eyebrow-line" /></div>
        {appState === "upload" && (
          <section className="welcome-layout">
            <div className="welcome-copy">
              <h1>Una segunda mirada,<br /><em>más precisa.</em></h1>
              <p>Analiza estudios de tórax con modelos de IA diseñados para asistir al equipo clínico. Visualiza hallazgos en 2D y reconstrucciones 3D en un solo lugar.</p>
              <div className="trust-row"><div><CheckCircleIcon /> <span><b>Privacidad primero</b><small>Tus estudios permanecen protegidos</small></span></div><div><ClockIcon /> <span><b>Resultados rápidos</b><small>Análisis en pocos minutos</small></span></div></div>
            </div>
            <UploadZone onUploadSuccess={handleUploadSuccess} />
          </section>
        )}
        {appState === "upload" && (
          <section className="purpose-hero" aria-labelledby="purpose-title">
            <div className="purpose-glow" />
            <div className="purpose-card-icon"><InformationCircleIcon /></div>
            <div className="purpose-hero-content">
              <span className="section-kicker">POR QUÉ EXISTE PULMOSCAN</span>
              <h2 id="purpose-title">Una herramienta para enfocar<br /><em>la atención clínica.</em></h2>
              <p>El sistema marca posibles anomalías pulmonares y crea puntos de interés para que, cuando el médico revise el estudio, pueda localizar rápidamente las regiones que requieren una mirada más detallada.</p>
              <div className="purpose-callout"><span className="callout-pulse" /> <strong>La IA orienta.</strong> El criterio final siempre pertenece al profesional de la salud.</div>
            </div>
            <div className="purpose-visual" aria-hidden="true"><div className="scan-ring ring-one" /><div className="scan-ring ring-two" /><div className="scan-core"><span /><span /><span /></div><div className="scan-line" /></div>
          </section>
        )}
        {processingError && <div className="error-banner"><ExclamationTriangleIcon /> <span>{processingError}</span><button onClick={() => setProcessingError("")}>Cerrar</button></div>}
        {appState === "processing" && <Loader />}
        {appState === "results" && analysisResults && (
          <section className="results-page">
            <div className="results-heading">
              <div><button className="back-link" onClick={handleReset}>← Nuevo análisis</button><h1>Resumen del estudio</h1><p>Revisión asistida por IA · Estudio completado</p></div>
              <div className="result-actions"><span className={detected ? "finding-badge danger" : "finding-badge safe"}>{detected ? "Anomalía detectada" : "Sin anomalías visibles"}</span><button className="button secondary" onClick={handleGeminiValidation} disabled={geminiState === "Analizando..."}><SparklesIcon /> {geminiState === "Analizando..." ? "Validando..." : "Validar con Gemini"}</button></div>
            </div>
            {geminiState && <div className="validation-note"><InformationCircleIcon /> {geminiState}</div>}
            <div className="metric-grid">
              <Metric label="Confianza del modelo" value={`${analysisResults.confidence ?? "—"}%`} accent />
              <Metric label="Diámetro estimado" value={stats?.diametroAprox ?? "—"} />
              <Metric label="Área afectada máxima" value={stats?.areaAfectadaMax ?? "—"} />
              <Metric label="Cortes con hallazgos" value={stats?.slicesAfectados ?? "—"} />
            </div>
            <div className="viewer-grid">
              <div className="viewer-card"><div className="card-heading"><div><span className="section-kicker">RECONSTRUCCIÓN</span><h2>Vista volumétrica 3D</h2></div><span className="live-tag"><span /> Interactivo</span></div><MeshViewer 
  model3dUrl={analysisResults.model3dUrl} 
  detections={analysisResults.detections || stats?.detecciones || []} 
/></div>
              <div className="viewer-card"><div className="card-heading"><div><span className="section-kicker">SERIE AXIAL</span><h2>Cortes 2D marcados</h2></div><span className="count-tag">{analysisResults.slices2dUrls?.length || 0} cortes</span></div><SliceViewer slices={analysisResults.slices2dUrls} /></div>
            </div>
            {analysisResults.conclusion && <div className="conclusion-card"><div className="conclusion-icon"><SparklesIcon /></div><div><span className="section-kicker">VALIDACIÓN CLÍNICA DE REFERENCIA</span><h2>Conclusión asistida</h2><p>{analysisResults.conclusion}</p>{analysisResults.recomendaciones?.length > 0 && <ul>{analysisResults.recomendaciones.map((item) => <li key={item}>{item}</li>)}</ul>}<small><ExclamationTriangleIcon /> Esta herramienta es orientativa y no sustituye la evaluación de un profesional.</small></div></div>}
          </section>
        )}
      </main>
      <footer><span>© 2025 PulmoScan</span><span>Los resultados deben ser interpretados por personal médico cualificado.</span><span>v1.0 · <a href="#privacy">Privacidad</a></span></footer>
    </div>
  );
}

function Metric({ label, value, accent }) {
  return <div className={accent ? "metric-card accent" : "metric-card"}><span>{label}</span><strong>{value}</strong>{accent && <small><ArrowPathIcon /> Modelo IA</small>}</div>;
}
