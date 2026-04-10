import { useState, useEffect, useRef } from 'react';
import { api } from '../services/api';
import { Folder, File as FileIcon, MoreVertical, Download, Trash, Share2, Move, FolderPlus, Upload } from 'lucide-react';
import ShareModal from './ShareModal';
import MoveModal from './MoveModal';
import './FileBrowser.css';

export default function FileBrowser({ view }) {
  const [items, setItems] = useState({ folders: [], documents: [] });
  const [loading, setLoading] = useState(true);
  const [currentFolderId, setCurrentFolderId] = useState(null);
  const [currentFolderPermission, setCurrentFolderPermission] = useState(null);
  const [breadcrumb, setBreadcrumb] = useState([{ id: null, name: view === 'shared' ? 'Shared with me' : 'My Drive' }]);
  const [dragActive, setDragActive] = useState(false);

  const [shareModalData, setShareModalData] = useState(null);
  const [moveModalData, setMoveModalData] = useState(null);

  const fetchItems = async () => {
    setLoading(true);
    try {
      if (view === 'shared' && currentFolderId === null) {
        const data = await api.getSharedWithMe();
        setItems(data);
      } else {
        const data = await api.getDirectoryContents(currentFolderId);
        setItems(data);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchItems();
  }, [view, currentFolderId]);

  const handleCreateFolder = async () => {
    const name = prompt("Folder name:");
    if (!name) return;
    await api.createFolder(name, currentFolderId);
    fetchItems();
  };

  const handleUploadClick = () => {
    const input = document.createElement('input');
    input.type = 'file';
    input.onchange = async (e) => {
      if (e.target.files && e.target.files[0]) {
        try {
          await api.uploadDocument(e.target.files[0], currentFolderId);
          fetchItems();
        } catch (err) {
          alert("Upload failed: " + err.message);
        }
      }
    };
    input.click();
  };

  const handleDrop = async (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    const draggedItem = e.dataTransfer.getData('application/x-dms-item');
    
    if (draggedItem) {
      const { itemId, itemType } = JSON.parse(draggedItem);
      try {
        await api.moveItem(itemId, itemType, currentFolderId);
        fetchItems();
      } catch (err) {
        alert(`Move failed: ${err.message}`);
      }
    } else {
      const files = e.dataTransfer.files;
      if (files && files.length > 0) {
        for (let i = 0; i < files.length; i++) {
          try {
            await api.uploadDocument(files[i], currentFolderId);
          } catch (err) {
            alert(`Upload failed for ${files[i].name}: ${err.message}`);
          }
        }
        fetchItems();
      }
    }
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
  };

  const handleDelete = async (id, type) => {
    if (window.confirm('Delete this item?')) {
      await api.deleteItem(id, type);
      fetchItems();
    }
  };

  const handleDragMove = async (draggedId, draggedType, destinationFolderId) => {
    try {
      await api.moveItem(draggedId, draggedType, destinationFolderId);
      fetchItems();
    } catch (err) {
      alert(`Move failed: ${err.message}`);
    }
  };

  const navigateToFolder = (folder) => {
    setCurrentFolderId(folder.id);
    setCurrentFolderPermission(folder.permission || null);
    setBreadcrumb([...breadcrumb, { id: folder.id, name: folder.name, permission: folder.permission || null }]);
  };

  const navigateBreadcrumb = (index) => {
    const newCrumb = breadcrumb[index];
    setCurrentFolderId(newCrumb.id);
    setCurrentFolderPermission(index === 0 ? null : newCrumb.permission || null);
    setBreadcrumb(breadcrumb.slice(0, index + 1));
  };

  const handleDownload = async (doc) => {
    try {
      await api.downloadDocument(doc.id, doc.name);
    } catch (err) {
      alert("Download failed: " + err.message);
    }
  };

  return (
    <div 
      className={`file-browser ${dragActive ? 'drag-active' : ''}`}
      onDrop={handleDrop}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
    >
      {dragActive && (
        <div className="drag-overlay">
          <div className="drag-content">
            <Upload size={48} />
            <p>Drop files here to upload</p>
          </div>
        </div>
      )}
      <div className="browser-header">
        <div className="breadcrumbs">
          {breadcrumb.map((crumb, idx) => (
            <span key={crumb.id || 'root'} className="crumb">
              <button className="crumb-btn" onClick={() => navigateBreadcrumb(idx)}>
                {crumb.name}
              </button>
              {idx < breadcrumb.length - 1 && <span className="separator">/</span>}
            </span>
          ))}
        </div>
        <div className="browser-actions">
          {(view === 'my-drive' || currentFolderPermission === 'EDITOR') && (
            <>
              <button className="btn-secondary" onClick={handleCreateFolder}>
                <FolderPlus size={16} /> New Folder
              </button>
              <button className="btn-primary" onClick={handleUploadClick}>
                <Upload size={16} /> Upload
              </button>
            </>
          )}
        </div>
      </div>

      {loading ? (
        <div className="loading-state">Loading...</div>
      ) : (
        <div className="items-grid">
          {items.folders.map(f => (
            <ItemCard
              key={f.id}
              item={f}
              type="folder"
              isShared={view === 'shared'}
              onNavigate={() => navigateToFolder(f)}
              onDelete={() => handleDelete(f.id, 'folder')}
              onShare={() => setShareModalData({ id: f.id, type: 'folder' })}
              onMove={() => setMoveModalData({ id: f.id, type: 'folder' })}
              onDragMove={(draggedId, draggedType) => handleDragMove(draggedId, draggedType, f.id)}
            />
          ))}
          {items.documents.map(d => (
            <ItemCard
              key={d.id}
              item={d}
              type="document"
              isShared={view === 'shared'}
              onDownload={() => handleDownload(d)}
              onDelete={() => handleDelete(d.id, 'document')}
              onShare={() => setShareModalData({ id: d.id, type: 'document' })}
              onMove={() => setMoveModalData({ id: d.id, type: 'document' })}
              onDragMove={(draggedId, draggedType) => draggedType === 'folder' && handleDragMove(draggedId, draggedType, d.id)}
            />
          ))}
          {items.folders.length === 0 && items.documents.length === 0 && (
            <div className="empty-state">No files or folders found.</div>
          )}
        </div>
      )}

      {shareModalData && (
        <ShareModal
          itemId={shareModalData.id}
          type={shareModalData.type}
          onClose={() => setShareModalData(null)}
        />
      )}

      {moveModalData && (
        <MoveModal
          itemId={moveModalData.id}
          type={moveModalData.type}
          onClose={() => {
            setMoveModalData(null);
            fetchItems();
          }}
        />
      )}
    </div>
  );
}

function ItemCard({ item, type, isShared, onNavigate, onDownload, onDelete, onShare, onMove, onDragMove }) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const menuRef = useRef(null);
  const cardRef = useRef(null);
  const isEditor = !isShared || item.permission === 'EDITOR';

  const handleAction = (e, action) => {
    e.stopPropagation();
    setMenuOpen(false);
    action();
  };

  const handleDragStart = (e) => {
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('application/x-dms-item', JSON.stringify({
      itemId: item.id,
      itemType: type
    }));
  };

  const handleDragOver = (e) => {
    if (type === 'folder') {
      e.preventDefault();
      e.stopPropagation();
      e.dataTransfer.dropEffect = 'move';
      setDragOver(true);
    }
  };

  const handleDragLeave = (e) => {
    if (e.target === cardRef.current) {
      setDragOver(false);
    }
  };

  const handleDrop = async (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragOver(false);

    if (type === 'folder') {
      const draggedItem = e.dataTransfer.getData('application/x-dms-item');
      if (draggedItem) {
        const { itemId, itemType } = JSON.parse(draggedItem);
        if (itemId !== item.id && onDragMove) {
          onDragMove(itemId, itemType);
        }
      }
    }
  };

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        setMenuOpen(false);
      }
    };

    if (menuOpen) {
      document.addEventListener('click', handleClickOutside);
      return () => document.removeEventListener('click', handleClickOutside);
    }
  }, [menuOpen]);

  return (
    <div
      ref={cardRef}
      className={`item-card ${dragOver ? 'drag-over' : ''}`}
      draggable={true}
      onDragStart={handleDragStart}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      onClick={type === 'folder' ? onNavigate : null}
    >
      <div className="item-icon">
        {type === 'folder' ? <Folder size={32} color="var(--brand-primary)" fill="#dbeafe" /> : <FileIcon size={32} color="#64748b" />}
      </div>
      <div className="item-info">
        <span className="item-name">{item.name}</span>
        {isShared && <span className="badge">{item.permission}</span>}
      </div>

      <div className="item-actions" ref={menuRef}>
        <button className="btn-icon" onClick={(e) => { e.stopPropagation(); setMenuOpen(!menuOpen); }}>
          <MoreVertical size={16} />
        </button>

        {menuOpen && (
          <div className="dropdown-menu">
            {type === 'document' && (
              <button onClick={(e) => handleAction(e, onDownload)}><Download size={14} /> Download</button>
            )}
            <button onClick={(e) => handleAction(e, onMove)}><Move size={14} /> {isShared ? "Copy to My Drive" : "Move"}</button>

            {isEditor && (
              <>
                <button onClick={(e) => handleAction(e, onShare)}><Share2 size={14} /> Share</button>
                <div className="divider"></div>
                <button className="text-danger" onClick={(e) => handleAction(e, onDelete)}><Trash size={14} /> Delete</button>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
