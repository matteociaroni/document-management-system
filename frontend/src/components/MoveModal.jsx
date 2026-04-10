import { useState, useEffect } from 'react';
import { api } from '../services/api';
import { X, Folder } from 'lucide-react';
import './Modal.css';

export default function MoveModal({ itemId, type, onClose }) {
  const [folders, setFolders] = useState([]);
  const [currentFolderId, setCurrentFolderId] = useState(null);
  const [breadcrumb, setBreadcrumb] = useState([{ id: null, name: 'My Drive' }]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchFolders = async () => {
      setLoading(true);
      const data = await api.getDirectoryContents(currentFolderId);
      // Filter out the folder we are trying to move, so we can't move a folder into itself
      setFolders(data.folders.filter(f => f.id !== itemId));
      setLoading(false);
    };
    fetchFolders();
  }, [currentFolderId, itemId]);

  const handleMove = async () => {
    try {
      await api.moveItem(itemId, type, currentFolderId);
      onClose();
    } catch (err) {
      alert("Error moving item: " + err.message);
    }
  };

  return (
    <div className="modal-overlay">
      <div className="modal-content">
        <div className="modal-header">
          <h2>Move {type}</h2>
          <button className="btn-icon" onClick={onClose}><X size={20}/></button>
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
            {folders.map(f => (
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
          <button type="button" className="btn-secondary" onClick={onClose}>Cancel</button>
          <button type="button" className="btn-primary" onClick={handleMove}>Move Here</button>
        </div>
      </div>
    </div>
  );
}
