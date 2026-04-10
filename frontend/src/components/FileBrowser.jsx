import { useState, useEffect } from 'react';
import { api } from '../services/api';
import { Folder, File as FileIcon, MoreVertical, Download, Trash, Share2, Move, FolderPlus, Upload } from 'lucide-react';
import ShareModal from './ShareModal';
import MoveModal from './MoveModal';
import './FileBrowser.css';

export default function FileBrowser({ view }) {
  const [items, setItems] = useState({ folders: [], documents: [] });
  const [loading, setLoading] = useState(true);
  const [currentFolderId, setCurrentFolderId] = useState(null);
  const [breadcrumb, setBreadcrumb] = useState([{ id: null, name: view === 'shared' ? 'Shared with me' : 'My Drive' }]);

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

  const handleDelete = async (id, type) => {
    if (window.confirm('Delete this item?')) {
      await api.deleteItem(id, type);
      fetchItems();
    }
  };

  const navigateToFolder = (folder) => {
    setCurrentFolderId(folder.id);
    setBreadcrumb([...breadcrumb, { id: folder.id, name: folder.name }]);
  };

  const navigateBreadcrumb = (index) => {
    const newCrumb = breadcrumb[index];
    setCurrentFolderId(newCrumb.id);
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
    <div className="file-browser">
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
          {view === 'my-drive' && (
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

function ItemCard({ item, type, isShared, onNavigate, onDownload, onDelete, onShare, onMove }) {
  const [menuOpen, setMenuOpen] = useState(false);
  const isEditor = !isShared || item.permission === 'EDITOR';

  const handleAction = (e, action) => {
    e.stopPropagation();
    setMenuOpen(false);
    action();
  };

  return (
    <div className="item-card" onClick={type === 'folder' ? onNavigate : null}>
      <div className="item-icon">
        {type === 'folder' ? <Folder size={32} color="var(--brand-primary)" fill="#dbeafe" /> : <FileIcon size={32} color="#64748b" />}
      </div>
      <div className="item-info">
        <span className="item-name">{item.name}</span>
        {isShared && <span className="badge">{item.permission}</span>}
      </div>

      <div className="item-actions">
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
