import { useState } from 'react';
import { api } from '../services/api';
import { X } from 'lucide-react';
import './Modal.css';

export default function ShareModal({ itemId, type, onClose }) {
  const [email, setEmail] = useState('');
  const [accessLevel, setAccessLevel] = useState('VIEWER');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');
    try {
      await api.shareItem(itemId, type, email, accessLevel);
      setSuccess(`Successfully shared with ${email}`);
      setTimeout(onClose, 1500);
    } catch (err) {
      setError(err.message);
    }
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
      </div>
    </div>
  );
}
