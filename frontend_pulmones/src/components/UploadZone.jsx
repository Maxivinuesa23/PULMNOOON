import { useRef, useState } from "react";
import { ArrowUpTrayIcon, CheckCircleIcon, DocumentIcon, ExclamationCircleIcon, PlayIcon } from "@heroicons/react/24/outline";
import { uploadZipFile } from "../services/api";

export default function UploadZone({ onUploadSuccess }) {
  const [isDragging, setIsDragging] = useState(false);
  const [file, setFile] = useState(null);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState("");
  const fileInputRef = useRef(null);
  const chooseFile = (selectedFile) => {
    setError("");
    if (!selectedFile?.name || !selectedFile.name.toLowerCase().endsWith(".zip")) {
      setError("Selecciona un archivo .zip que contenga la tomografía DICOM.");
      setFile(null);
      return;
    }
    setFile(selectedFile);
  };
  const handleUpload = async () => {
    if (!file) return;
    setIsUploading(true); setError("");
    try { onUploadSuccess?.(await uploadZipFile(file)); } catch (err) { console.error(err); setError("No se pudo conectar con el servidor. Verifica que FastAPI esté corriendo."); } finally { setIsUploading(false); }
  };
  return <div className="upload-card">
    <div className="upload-card-heading"><div className="upload-icon"><ArrowUpTrayIcon /></div><div><h2>Carga un estudio</h2><p>Sube la serie DICOM comprimida para comenzar</p></div></div>
    <div className={`drop-zone ${isDragging ? "dragging" : ""} ${file ? "has-file" : ""}`} onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }} onDragLeave={() => setIsDragging(false)} onDrop={(e) => { e.preventDefault(); setIsDragging(false); chooseFile(e.dataTransfer.files[0]); }} onClick={() => fileInputRef.current?.click()}>
      <input ref={fileInputRef} type="file" accept=".zip" hidden onChange={(e) => chooseFile(e.target.files[0])} />
      {file ? <><CheckCircleIcon className="drop-symbol success" /><strong>{file.name}</strong><span>{(file.size / 1024 / 1024).toFixed(1)} MB · Listo para analizar</span><button className="file-change" onClick={(e) => { e.stopPropagation(); setFile(null); }}>Cambiar archivo</button></> : <><ArrowUpTrayIcon className="drop-symbol" /><strong>Arrastra y suelta tu archivo aquí</strong><span>o haz clic para explorar · Solo .ZIP</span></>}
    </div>
    {error && <div className="inline-error"><ExclamationCircleIcon /> {error}</div>}
    <button className="button primary upload-button" disabled={!file || isUploading} onClick={handleUpload}>{isUploading ? <><span className="spinner" /> Procesando estudio...</> : <><PlayIcon /> Iniciar análisis</>}</button>
    <div className="upload-meta"><span><DocumentIcon /> DICOM .ZIP</span><span>Máximo recomendado: 2 GB</span></div>
  </div>;
}
