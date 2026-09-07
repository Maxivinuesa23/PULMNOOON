import { useState } from "react";
import {
  ArrowPathIcon,
  BeakerIcon,
  CheckCircleIcon,
  ClockIcon,
  ExclamationTriangleIcon,
  InformationCircleIcon,
  LinkIcon,
  PlayCircleIcon,
  SparklesIcon,
  XMarkIcon,
} from "@heroicons/react/24/outline";
import UploadZone from "../components/UploadZone";
import SliceViewer from "../components/SliceViewer";
import MeshViewer from "../components/MeshViewer";
import Loader from "../components/Loader";
import { checkTaskStatus } from "../services/api";

const TEST_STUDIES_DRIVE_URL = "https://drive.google.com/drive/folders/1PBv0RC5Oi2tIJw9jJRUxej-6y_DTaQlc?usp=sharing";
const DEMO_VIDEO_URL = "https://youtu.be/lOLhE6efY6k?si=D3lP3RepBJhf0r42";

function getVideoSource(url) {
  if (!url || url.includes("REEMPLAZAR")) return null;
  try {
    const parsedUrl = new URL(url);
    if (parsedUrl.hostname === "youtu.be") {
      return { type: "youtube", src: `https://www.youtube.com/embed/${parsedUrl.pathname.slice(1)}` };
    }
    if (parsedUrl.hostname.endsWith("youtube.com")) {
      const videoId = parsedUrl.searchParams.get("v");
      return videoId ? { type: "youtube", src: `https://www.youtube.com/embed/${videoId}` } : null;
    }
    return { type: "file", src: parsedUrl.toString() };
  } catch {
    return null;
  }
}

export default function Dashboard() {
  const [appState, setAppState] = useState("upload");
  const [activeView, setActiveView] = useState("upload");
  const [analysisResults, setAnalysisResults] = useState(null);
  const [processingError, setProcessingError] = useState("");
  const [geminiState, setGeminiState] = useState("");
  const [showImportantNotice, setShowImportantNotice] = useState(true);
  const [showServiceNotice, setShowServiceNotice] = useState(true);
  const videoSource = getVideoSource(DEMO_VIDEO_URL);

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

  const handleGoHome = () => {
    handleReset();
    setActiveView("upload");
  };

  const detected = Boolean(analysisResults?.tumorDetected);
  const stats = analysisResults?.stats;

  return (
    <div className="app-shell">
      <header className="topbar">
        <button type="button" className="brand brand-button" onClick={handleGoHome} aria-label="Volver al menú principal">
          <div className="brand-mark"><BeakerIcon /></div>
          <div><strong>Pulmo<span>Scan</span></strong><small>Asistencia radiológica</small></div>
        </button>
        <nav className="view-switcher" aria-label="Secciones principales">
          <button type="button" className={activeView === "upload" ? "view-tab active" : "view-tab"} onClick={() => setActiveView("upload")}>Cargar estudio</button>
          <button type="button" className={activeView === "info" ? "view-tab active" : "view-tab"} onClick={() => setActiveView("info")}>Ver información</button>
          <button type="button" className={activeView === "about" ? "view-tab active" : "view-tab"} onClick={() => setActiveView("about")}>Quiénes somos</button>
        </nav>
      </header>

      <main className="page-content">
        <div className="eyebrow"><span className="status-dot" /> PLATAFORMA DE ANÁLISIS DICOM <span className="eyebrow-line" /></div>
        {activeView === "upload" && appState === "upload" && (
          <section className="welcome-layout">
            <div className="welcome-copy">
              <h1>Una segunda mirada,<br /><em>más precisa.</em></h1>
              <p>Analiza estudios de tórax con modelos de IA diseñados para asistir al equipo clínico. Visualiza hallazgos en 2D y reconstrucciones 3D en un solo lugar.</p>
              <div className="trust-row"><div><CheckCircleIcon /> <span><b>Privacidad primero</b><small>Tus estudios permanecen protegidos</small></span></div><div><ClockIcon /> <span><b>Resultados rápidos</b><small>Análisis en pocos minutos</small></span></div></div>
            </div>
            <UploadZone onUploadSuccess={handleUploadSuccess} />
          </section>
        )}
        {activeView === "info" && (
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
        {activeView === "info" && (
          <section className="resources-section" aria-labelledby="resources-title">
            <div className="resources-heading">
              <div>
                <span className="section-kicker">CENTRO DE AYUDA</span>
                <h2 id="resources-title">Probá la aplicación con estudios reales</h2>
                <p>Descargá una serie de prueba o mirá el video para conocer el flujo completo.</p>
              </div>
              <span className="resources-label">2 recursos</span>
            </div>
            <div className="resource-grid">
              <a className="resource-card" href={TEST_STUDIES_DRIVE_URL} target="_blank" rel="noreferrer">
                <span className="resource-icon"><LinkIcon /></span>
                <span className="resource-card-content">
                  <strong>Series de tomografías para probar</strong>
                  <span>Descargá estudios desde nuestro Drive y subilos en formato .ZIP.</span>
                  <small>https://drive.google.com/drive/folders/1PBv0RC5Oi2tIJw9jJRUxej-6y_DTaQlc?usp=sharing <span>↗</span></small>
                </span>
              </a>
              <a className="resource-card" href={DEMO_VIDEO_URL} target="_blank" rel="noreferrer">
                <span className="resource-icon video"><PlayCircleIcon /></span>
                <span className="resource-card-content">
                  <strong>Cómo funciona PulmoScan</strong>
                  <span>Video corto con el paso a paso para cargar y revisar un estudio.</span>
                  <small>https://youtu.be/lOLhE6efY6k?si=D3lP3RepBJhf0r42<span>↗</span></small>
                </span>
              </a>
            </div>
            <div className="tcia-note">
              <InformationCircleIcon />
              <span>Los estudios de prueba provienen de <a href="https://www.cancerimagingarchive.net/" target="_blank" rel="noreferrer">The Cancer Imaging Archive (TCIA)</a>. También podés obtener otras series directamente desde su archivo.</span>
            </div>
            {videoSource && (
              <div className="video-preview">
                {videoSource.type === "youtube" ? (
                  <iframe src={videoSource.src} title="Demostración de PulmoScan" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowFullScreen />
                ) : (
                  <video src={videoSource.src} controls preload="metadata">Tu navegador no puede reproducir este video.</video>
                )}
              </div>
            )}
          </section>
        )}
        {activeView === "info" && (
          <section className="important-notice" aria-labelledby="important-title">
            <div className="notice-icon"><ExclamationTriangleIcon /></div>
            <div><strong id="important-title">Importante antes de usar</strong><p>PulmoScan es una herramienta de asistencia. Los resultados deben ser revisados e interpretados por personal médico cualificado.</p></div>
          </section>
        )}
        {activeView === "about" && <AboutProject />}
        {showServiceNotice && (
          <aside className="service-limit-popup" role="status" aria-label="Límite de carga">
            <div className="service-limit-icon"><InformationCircleIcon /></div>
            <div className="service-limit-content">
              <strong>Límite de carga del servicio gratuito</strong>
              <p>
                Por las limitaciones del hosting gratuito de Supabase, el tamaño máximo recomendado por subida es de <b>50 MB</b>.
                Para probar la plataforma sin inconvenientes, recomendamos utilizar <b>PRUEBA3.zip</b>.
              </p>
            </div>
            <button type="button" className="service-limit-close" onClick={() => setShowServiceNotice(false)} aria-label="Cerrar aviso">
              <XMarkIcon />
            </button>
          </aside>
        )}
        {processingError && <div className="error-banner"><ExclamationTriangleIcon /> <span>{processingError}</span><button onClick={() => setProcessingError("")}>Cerrar</button></div>}
        {activeView === "upload" && appState === "processing" && <Loader />}
        {activeView === "upload" && appState === "results" && analysisResults && (
          <section className="results-page">
            <div className="results-heading">
              <div><button className="back-link" onClick={handleReset}>← Nuevo análisis</button><h1>Resumen del estudio</h1><p>Revisión asistida por IA · Estudio completado</p></div>
              <div className="result-actions"><span className={detected ? "finding-badge danger" : "finding-badge safe"}>{detected ? "Anomalía detectada" : "Sin anomalías visibles"}</span><span className="future-feature-tooltip" data-tooltip="Implementación a futuro" tabIndex="0"><button className="button gemini-button" type="button" disabled aria-disabled="true"><SparklesIcon /> Obtener segunda opinión</button></span></div>
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
      {showImportantNotice && activeView === "upload" && appState === "upload" && (
        <div className="notice-backdrop" role="presentation">
          <section className="notice-modal" role="dialog" aria-modal="true" aria-labelledby="modal-title">
            <button type="button" className="modal-close" aria-label="Cerrar aviso importante" onClick={() => setShowImportantNotice(false)}><XMarkIcon /></button>
            <div className="modal-icon"><ExclamationTriangleIcon /></div>
            <span className="section-kicker">ANTES DE COMENZAR</span>
            <h2 id="modal-title">Importante</h2>
            <p>Leé esta información antes de cargar un estudio.</p>
            <div className="modal-rule" />
            <strong>Una herramienta de asistencia clínica</strong>
            <small>PulmoScan orienta la revisión de imágenes, pero no reemplaza el criterio ni el diagnóstico de un profesional de la salud.</small>
            <div className="modal-actions">
              <button type="button" className="button modal-secondary" onClick={() => { setShowImportantNotice(false); setActiveView("info"); }}>Leer información</button>
              <button type="button" className="button primary modal-primary" onClick={() => setShowImportantNotice(false)}>Entendido, continuar</button>
            </div>
          </section>
        </div>
      )}
      <footer><span>© 2026 PulmoScan</span><span>Los resultados deben ser interpretados por personal médico cualificado.</span><span>v1.0 · <a href="#privacy">Privacidad</a></span></footer>
    </div>
  );
}

function AboutProject() {
  return (
    <section className="about-page" aria-labelledby="about-title">
      <header className="about-hero">
        <span className="section-kicker">SOBRE EL PROYECTO</span>
        <h1 id="about-title">Detección y Segmentación 3D de <em>Nódulos Pulmonares</em></h1>
        <p>Somos <strong>Máximo Vinuesa</strong> y <strong>Tomás Picco</strong>, estudiantes avanzados de Ingeniería en Sistemas de Información en la Universidad Nacional de Villa Mercedes (UNViMe).</p>
        <p>Desarrollamos esta plataforma para asistir la detección temprana del cáncer de pulmón mediante el análisis automatizado de imágenes de tomografía computarizada (CT).</p>
      </header>

      <div className="about-grid">
        <article className="about-card about-wide">
          <span className="section-kicker">PROPÓSITO E INNOVACIÓN</span>
          <h2>Una segunda mirada para la atención clínica</h2>
          <p>La detección temprana de lesiones nodulares en el tórax es determinante para la supervivencia del paciente. Sin embargo, analizar cientos de cortes axiales demanda tiempo y puede dificultar la identificación de nódulos milimétricos o su diferenciación frente a estructuras vasculares.</p>
          <p>Combinamos visión por computadora, aprendizaje profundo (<em>Deep Learning</em>) y reconstrucción tridimensional para ofrecer una segunda mirada clara y visual sobre cada estudio.</p>
        </article>
        <article className="about-card">
          <span className="section-kicker">01 · INGESTA</span>
          <h2>De DICOM a cortes optimizados</h2>
          <p>El profesional carga un archivo <code>.zip</code> con los cortes originales. El sistema los convierte, normaliza sus valores en Unidades Hounsfield (HU) y los prepara con una ventana optimizada para observar el pulmón.</p>
        </article>
        <article className="about-card">
          <span className="section-kicker">02 · INTELIGENCIA ARTIFICIAL</span>
          <h2>Modelo clínico U-Net</h2>
          <p>Una red neuronal U-Net, entrenada con datos del consorcio internacional <strong>LIDC-IDRI</strong>, analiza cada corte. Aísla el pulmón y marca las regiones nodulares sospechosas.</p>
        </article>
        <article className="about-card">
          <span className="section-kicker">03 · RECONSTRUCCIÓN</span>
          <h2>Volumen anatómico interactivo</h2>
          <p>Los cortes se reúnen en un volumen 3D. Luego, el algoritmo <em>Marching Cubes</em> genera un modelo anatómico interactivo en formato GLTF para explorarlo desde el navegador.</p>
        </article>
        <article className="about-card about-wide">
          <span className="section-kicker">CARACTERÍSTICAS DEL SISTEMA</span>
          <h2>Resultados para explorar y comprender</h2>
          <div className="about-feature-list">
            <div><strong>Visor 2D de cortes axiales</strong><span>Recorrido dinámico sobre el eje Z con delimitación automática de zonas sospechosas.</span></div>
            <div><strong>Métricas clínicas cuantitativas</strong><span>Cortes afectados, corte crítico, área máxima (mm²), volumen proyectado (mm³), diámetro aproximado (mm) e índice de confianza.</span></div>
            <div><strong>Visor 3D interactivo dual</strong><span>Visualización WebGL de la morfología pulmonar y localización espacial del nódulo. El modo pulmón completo se encuentra en fase beta.</span></div>
          </div>
        </article>
        <article className="about-card about-wide architecture-card">
          <span className="section-kicker">ARQUITECTURA TECNOLÓGICA</span>
          <h2>Una plataforma integral, de punta a punta</h2>
          <div className="stack-grid">
            <div><strong>Backend</strong><span>Python · FastAPI · Background Tasks · NumPy · SciPy · PyDICOM · Trimesh · PyTorch · GPU/CPU</span></div>
            <div><strong>Frontend</strong><span>React · Vite · Tailwind CSS · Three.js · React Three Fiber / Drei · WebGL</span></div>
          </div>
        </article>
      </div>
    </section>
  );
}

function Metric({ label, value, accent }) {
  return <div className={accent ? "metric-card accent" : "metric-card"}><span>{label}</span><strong>{value}</strong>{accent && <small><ArrowPathIcon /> Modelo IA</small>}</div>;
}
