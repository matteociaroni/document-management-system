import { useState, useEffect } from 'react';
import { api } from '../services/api';
import { useUI } from '../context/UIContext';
import { Inbox, Mail, Folder, FolderTree, Check, X, MoveRight, FileText } from 'lucide-react';
import './InboxView.css';

function FolderPickerModal({ onClose, onPick }) {
  const [folders, setFolders] = useState([]);
  const [currentFolderId, setCurrentFolderId] = useState(null);
  const [breadcrumb, setBreadcrumb] = useState([{ id: null, name: 'My Drive' }]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    setLoading(true);
    api.getDirectoryContents(currentFolderId).then((data) => {
      if (!active) return;
      setFolders(data.folders);
      setLoading(false);
    });
    return () => { active = false; };
  }, [currentFolderId]);

  return (
    <div className="modal-overlay">
      <div className="modal-content">
        <div className="modal-header">
          <h2>Scegli cartella di destinazione</h2>
          <button className="btn-icon" onClick={onClose}><X size={20} /></button>
        </div>

        <div className="modal-body">
          <div className="move-breadcrumb">
            {breadcrumb.map((crumb, idx) => (
              <span key={crumb.id || 'root'}>
                <button
                  className="text-btn"
                  onClick={() => {
                    setCurrentFolderId(crumb.id);
                    setBreadcrumb(breadcrumb.slice(0, idx + 1));
                  }}
                >
                  {crumb.name}
                </button>
                {idx < breadcrumb.length - 1 && ' / '}
              </span>
            ))}
          </div>

          <div className="folder-list">
            {loading ? <p>Loading...</p> : folders.length === 0 ? <p className="text-secondary">Empty folder</p> : null}
            {folders.map((f) => (
              <button
                key={f.id}
                className="folder-list-item"
                onClick={() => {
                  setCurrentFolderId(f.id);
                  setBreadcrumb([...breadcrumb, { id: f.id, name: f.name }]);
                }}
              >
                <Folder size={16} />
                {f.name}
              </button>
            ))}
          </div>
        </div>

        <div className="modal-footer">
          <button type="button" className="btn-secondary" onClick={onClose}>Annulla</button>
          <button
            type="button"
            className="btn-primary"
            onClick={() => onPick(currentFolderId)}
          >
            {currentFolderId ? 'Sposta qui' : 'Sposta in My Drive'}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function InboxView() {
  const [proposals, setProposals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [pickerForId, setPickerForId] = useState(null);
  const { setLoading: setGlobalLoading, addToast } = useUI();

  const fetchProposals = async () => {
    try {
      setLoading(true);
      const data = await api.listProposals();
      setProposals(data);
      setError(null);
    } catch (err) {
      console.error('Failed to fetch proposals', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchProposals(); }, []);

  const removeFromList = (id) => {
    setProposals((prev) => prev.filter((p) => p.id !== id));
  };

  const handleAccept = async (p) => {
    setGlobalLoading(true, 'Conferma in corso...');
    try {
      await api.acceptProposal(p.id);
      addToast(`'${p.filename}' archiviato in ${p.suggested_folder_name}`, 'success');
      removeFromList(p.id);
    } catch (err) {
      addToast(`Errore: ${err.message}`, 'error');
    } finally {
      setGlobalLoading(false);
    }
  };

  const handleMove = async (p, folderId) => {
    setGlobalLoading(true, 'Spostamento in corso...');
    try {
      await api.moveProposal(p.id, folderId);
      addToast(`'${p.filename}' spostato`, 'success');
      removeFromList(p.id);
    } catch (err) {
      addToast(`Errore: ${err.message}`, 'error');
    } finally {
      setGlobalLoading(false);
      setPickerForId(null);
    }
  };

  const formatConfidence = (c) => (c == null ? null : `${Math.round(c * 100)}%`);

  const pickerProposal = proposals.find((p) => p.id === pickerForId);

  return (
    <div className="inbox-view">
      <div className="inbox-header">
        <Inbox size={28} className="header-icon" />
        <div>
          <h2 className="inbox-title">Inbox</h2>
          <p className="inbox-subtitle">
            Allegati per cui l'agente non ha trovato una corrispondenza adeguata. Conferma la cartella suggerita o spostali manualmente.
          </p>
        </div>
      </div>

      {error && <div className="error-state">{error}</div>}

      {loading ? (
        <div className="loading-state">Caricamento allegati...</div>
      ) : proposals.length === 0 ? (
        <div className="empty-state">
          <Inbox size={48} opacity={0.2} />
          <p>Nessun allegato in attesa di revisione.</p>
        </div>
      ) : (
        <div className="inbox-list">
          {proposals.map((p) => (
            <div key={p.id} className="inbox-item">
              <div className="inbox-item-icon">
                <FileText size={22} />
              </div>
              <div className="inbox-item-body">
                <div className="inbox-item-header">
                  <span className="inbox-filename">{p.filename}</span>
                  {p.confidence != null && (
                    <span className="inbox-confidence">confidenza {formatConfidence(p.confidence)}</span>
                  )}
                </div>

                {(p.sender || p.subject) && (
                  <div className="inbox-meta">
                    <Mail size={14} />
                    <span>
                      {p.sender ? <strong>{p.sender}</strong> : null}
                      {p.sender && p.subject ? ' — ' : ''}
                      {p.subject || ''}
                    </span>
                  </div>
                )}

                {p.suggested_folder_name && (
                  <div className="inbox-suggestion">
                    <FolderTree size={14} />
                    <span>Suggerito: <strong>{p.suggested_folder_name}</strong></span>
                  </div>
                )}

                {p.agent_reasoning && (
                  <div className="inbox-reasoning">{p.agent_reasoning}</div>
                )}

                <div className="inbox-actions">
                  {p.suggested_folder_id && (
                    <button
                      type="button"
                      className="btn-primary inbox-btn"
                      onClick={() => handleAccept(p)}
                    >
                      <Check size={16} /> Salva nella cartella suggerita
                    </button>
                  )}
                  <button
                    type="button"
                    className="btn-secondary inbox-btn"
                    onClick={() => setPickerForId(p.id)}
                  >
                    <MoveRight size={16} /> Sposta in altra cartella
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {pickerProposal && (
        <FolderPickerModal
          onClose={() => setPickerForId(null)}
          onPick={(folderId) => handleMove(pickerProposal, folderId)}
        />
      )}
    </div>
  );
}
