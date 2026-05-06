import { useState, useEffect } from 'react';
import { api } from '../services/api';
import { X, Trash2 } from 'lucide-react';
import { useUI } from '../context/UIContext';
import { ConfirmDialog } from './Dialog';
import './Modal.css';

export default function ShareModal({ itemId, type, onClose }) {
  const [email, setEmail] = useState('');
  const [accessLevel, setAccessLevel] = useState('VIEWER');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [permissions, setPermissions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [confirmRevoke, setConfirmRevoke] = useState({ open: false });
  const { setLoading: setGlobalLoading, addToast } = useUI();

  useEffect(() => {
    fetchPermissions();
  }, [itemId, type]);

  const fetchPermissions = async () => {
    try {
      const perms = await api.getItemPermissions(itemId, type);
      setPermissions(perms || []);
    } catch (err) {
      console.error('Failed to load permissions:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');
    setGlobalLoading(true, "Condivisione in corso...");
    try {
      await api.shareItem(itemId, type, email, accessLevel);
      setSuccess(`Successfully shared with ${email}`);
      addToast(`Condiviso con successo con ${email}`, "success");
      setEmail('');
      setAccessLevel('VIEWER');
      await fetchPermissions();
      setTimeout(() => setSuccess(''), 2000);
    } catch (err) {
      setError(err.message);
      addToast(`Errore condivisione: ${err.message}`, "error");
    } finally {
      setGlobalLoading(false);
    }
  };

  const handleRevoke = (permissionId) => {
    setConfirmRevoke({
      open: true,
      onConfirm: async () => {
        setConfirmRevoke({ open: false });
        setGlobalLoading(true, "Rimozione permessi...");
        try {
          await api.deletePermission(permissionId);
          addToast("Permessi rimossi", "success");
          await fetchPermissions();
        } catch (err) {
          setError(err.message);
          addToast(`Errore rimozione: ${err.message}`, "error");
        } finally {
          setGlobalLoading(false);
        }
      },
      onCancel: () => setConfirmRevoke({ open: false }),
    });
  };

  return (
    <div className="modal-overlay">
      <div className="modal-content">
        <div className="modal-header">
          <h2>Share {type}</h2>
          <button className="btn-icon" onClick={onClose}><X size={20}/></button>
        </div>
        
        {error && <div className="modal-alert error">{error}</div>}
        {success && <div className="modal-alert success">{success}</div>}

        <form onSubmit={handleSubmit} className="modal-form">
          <div className="form-group">
            <label className="form-label">User Email</label>
            <input 
              type="email" 
              className="form-input" 
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="colleague@domain.com"
              required
            />
          </div>
          <div className="form-group">
            <label className="form-label">Permissions</label>
            <select 
              className="form-input"
              value={accessLevel}
              onChange={(e) => setAccessLevel(e.target.value)}
            >
              <option value="VIEWER">Viewer</option>
              <option value="EDITOR">Editor</option>
            </select>
          </div>
          <div className="modal-footer">
            <button type="button" className="btn-secondary" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn-primary">Share</button>
          </div>
        </form>

        {!loading && permissions.length > 0 && (
          <div className="permissions-list">
            <h3>Current Shares</h3>
            <div className="permissions-items">
              {permissions.map(perm => (
                <div key={perm.id} className="permission-item">
                  <div className="permission-info">
                    <span className="permission-user">{perm.user?.email || 'Unknown'}</span>
                    <span className="permission-level">{perm.access_level}</span>
                  </div>
                  <button 
                    type="button"
                    className="btn-icon btn-danger"
                    onClick={() => handleRevoke(perm.id)}
                    title="Revoke"
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      <ConfirmDialog
        isOpen={confirmRevoke.open}
        title="Rimuovi condivisione"
        message="Questa persona perderà l'accesso all'elemento. Vuoi procedere?"
        variant="danger"
        confirmLabel="Rimuovi accesso"
        cancelLabel="Annulla"
        onConfirm={confirmRevoke.onConfirm}
        onCancel={confirmRevoke.onCancel}
      />
    </div>
  );
}
