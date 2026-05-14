import { useEffect, useState } from 'react';
import { X, Download, FileIcon } from 'lucide-react';
import { api } from '../services/api';
import { useUI } from '../context/UIContext';
import './Modal.css';

const PREVIEW_MAX_BYTES = 25 * 1024 * 1024;

export default function PreviewModal({ document, onClose }) {
  const [state, setState] = useState({ status: 'loading' });
  const [textContent, setTextContent] = useState(null);
  const { addToast, setLoading: setGlobalLoading } = useUI();

  useEffect(() => {
    let revoked = false;
    let urlToRevoke = null;

    const sizeKnown = typeof document.size_bytes === 'number';
    if (sizeKnown && document.size_bytes > PREVIEW_MAX_BYTES) {
      setState({ status: 'too-large' });
      return;
    }

    (async () => {
      try {
        const { blobUrl, mimeType, size } = await api.previewDocument(document.id);
        urlToRevoke = blobUrl;
        if (size > PREVIEW_MAX_BYTES) {
          window.URL.revokeObjectURL(blobUrl);
          urlToRevoke = null;
          if (!revoked) setState({ status: 'too-large' });
          return;
        }
        if (!revoked) setState({ status: 'ready', blobUrl, mimeType });
      } catch (err) {
        if (!revoked) setState({ status: 'error', message: err.message });
      }
    })();

    return () => {
      revoked = true;
      if (urlToRevoke) window.URL.revokeObjectURL(urlToRevoke);
    };
  }, [document.id]);

  useEffect(() => {
    if (state.status !== 'ready') return;
    const mime = state.mimeType || '';
    if (!mime.startsWith('text/') && mime !== 'application/json') return;

    let cancelled = false;
    fetch(state.blobUrl)
      .then(r => r.text())
      .then(txt => { if (!cancelled) setTextContent(txt); })
      .catch(() => { if (!cancelled) setTextContent('(Impossibile leggere il contenuto)'); });
    return () => { cancelled = true; };
  }, [state]);

  const handleDownload = async () => {
    setGlobalLoading(true, 'Preparazione download in corso...');
    try {
      await api.downloadDocument(document.id, document.name);
      addToast('Download avviato', 'success');
    } catch (err) {
      addToast(`Errore download: ${err.message}`, 'error');
    } finally {
      setGlobalLoading(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        className="modal-content"
        style={{ maxWidth: '90vw', width: '1100px', maxHeight: '90vh' }}
        onClick={e => e.stopPropagation()}
      >
        <div className="modal-header">
          <h2 style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {document.name}
          </h2>
          <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
            <button className="btn-secondary" onClick={handleDownload}>
              <Download size={16} /> Download
            </button>
            <button className="btn-icon" onClick={onClose} aria-label="Chiudi">
              <X size={20} />
            </button>
          </div>
        </div>
        <div
          className="modal-body"
          style={{ flex: 1, overflow: 'auto', alignItems: 'stretch', padding: 0, background: '#0b0f17' }}
        >
          <PreviewBody state={state} textContent={textContent} />
        </div>
      </div>
    </div>
  );
}

function PreviewBody({ state, textContent }) {
  if (state.status === 'loading') {
    return <CenteredMessage>Caricamento anteprima…</CenteredMessage>;
  }
  if (state.status === 'error') {
    return <CenteredMessage>Impossibile caricare l'anteprima: {state.message}</CenteredMessage>;
  }
  if (state.status === 'too-large') {
    return (
      <CenteredMessage>
        Il file supera i {Math.round(PREVIEW_MAX_BYTES / 1024 / 1024)} MB consentiti per l'anteprima.
        <br />Usa il pulsante Download per scaricarlo.
      </CenteredMessage>
    );
  }

  const { mimeType, blobUrl } = state;

  if (mimeType.startsWith('image/')) {
    return (
      <div style={imageWrap}>
        <img src={blobUrl} alt="" style={{ maxWidth: '100%', maxHeight: '100%', objectFit: 'contain' }} />
      </div>
    );
  }
  if (mimeType === 'application/pdf') {
    return <iframe src={blobUrl} title="preview" style={{ width: '100%', height: '80vh', border: 0 }} />;
  }
  if (mimeType.startsWith('video/')) {
    return (
      <div style={imageWrap}>
        <video src={blobUrl} controls style={{ maxWidth: '100%', maxHeight: '100%' }} />
      </div>
    );
  }
  if (mimeType.startsWith('audio/')) {
    return (
      <div style={{ ...imageWrap, padding: '2rem' }}>
        <audio src={blobUrl} controls style={{ width: '100%' }} />
      </div>
    );
  }
  if (mimeType.startsWith('text/') || mimeType === 'application/json') {
    return (
      <pre style={{
        margin: 0,
        padding: '1.5rem',
        color: '#e2e8f0',
        fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
        fontSize: '0.875rem',
        whiteSpace: 'pre-wrap',
        wordBreak: 'break-word',
      }}>
        {textContent ?? 'Caricamento testo…'}
      </pre>
    );
  }

  return (
    <CenteredMessage>
      <FileIcon size={48} style={{ marginBottom: '1rem', opacity: 0.6 }} />
      Anteprima non disponibile per questo formato ({mimeType || 'sconosciuto'}).
      <br />Usa il pulsante Download per aprire il file.
    </CenteredMessage>
  );
}

function CenteredMessage({ children }) {
  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      width: '100%',
      minHeight: '50vh',
      color: '#cbd5e1',
      textAlign: 'center',
      padding: '2rem',
    }}>
      {children}
    </div>
  );
}

const imageWrap = {
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  width: '100%',
  minHeight: '60vh',
  padding: '1rem',
};
