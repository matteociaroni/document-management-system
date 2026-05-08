import { useState, useEffect, useRef } from 'react';
import { useUI } from '../context/UIContext';
import { api } from '../services/api';
import { Folder, File as FileIcon, MoreVertical, Download, Trash, Share2, Move, FolderPlus, Upload, Sparkles } from 'lucide-react';
import ShareModal from './ShareModal';
import MoveModal from './MoveModal';
import { ConfirmDialog, PromptDialog } from './Dialog';
import './FileBrowser.css';

export default function FileBrowser({ view, onNavigate }) {
  const [items, setItems] = useState({ folders: [], documents: [] });
  const [loading, setLoading] = useState(true);
  const [currentFolderId, setCurrentFolderId] = useState(null);
  const [currentFolderPermission, setCurrentFolderPermission] = useState(null);
  const [currentUser, setCurrentUser] = useState(null);
  const [breadcrumb, setBreadcrumb] = useState([{ id: null, name: view === 'shared' ? 'Shared with me' : 'My Drive' }]);
  const [dragActive, setDragActive] = useState(false);
  const [agentModifiedFolders, setAgentModifiedFolders] = useState(new Set());
  const { setLoading: setGlobalLoading, addToast } = useUI();

  const [shareModalData, setShareModalData] = useState(null);
  const [moveModalData, setMoveModalData] = useState(null);

  // Custom dialog state
  const [promptDialog, setPromptDialog] = useState({ open: false });
  const [confirmDialog, setConfirmDialog] = useState({ open: false });

  useEffect(() => {
    setCurrentUser(api.getCurrentUser());
  }, []);

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

  const fetchAgentOperations = async () => {
    try {
      const ops = await api.getAgentOperations();
      const readMap = JSON.parse(localStorage.getItem('dms_read_agent_folders') || '{}');
      const unread = new Set();
      
      ops.forEach(op => {
        if (op.details && op.details.folder_id) {
          const folderId = op.details.folder_id;
          const opTime = new Date(op.created_at).getTime();
          const readTime = readMap[folderId] || 0;
          if (opTime > readTime) {
            unread.add(folderId);
          }
        }
      });
      setAgentModifiedFolders(unread);
    } catch (err) {
      console.error('Failed to fetch agent operations', err);
    }
  };

  useEffect(() => {
    fetchItems();
    fetchAgentOperations();
  }, [view, currentFolderId]);

  const handleCreateFolder = () => {
    setPromptDialog({
      open: true,
      title: 'Nuova cartella',
      inputLabel: 'Nome cartella',
      placeholder: 'es. Documenti 2025',
      onConfirm: async (name) => {
        setPromptDialog({ open: false });
        setGlobalLoading(true, "Creazione cartella in corso...");
        try {
          await api.createFolder(name, currentFolderId);
          addToast("Cartella creata con successo", "success");
          fetchItems();
        } catch (err) {
          addToast(`Errore durante la creazione: ${err.message}`, "error");
        } finally {
          setGlobalLoading(false);
        }
      },
      onCancel: () => setPromptDialog({ open: false }),
    });
  };

  const handleUploadClick = () => {
    const input = document.createElement('input');
    input.type = 'file';
    input.onchange = async (e) => {
      if (e.target.files && e.target.files[0]) {
        setGlobalLoading(true, "Caricamento file in corso...");
        try {
          await api.uploadDocument(e.target.files[0], currentFolderId);
          addToast("File caricato con successo", "success");
          fetchItems();
        } catch (err) {
          addToast(`Errore durante il caricamento: ${err.message}`, "error");
        } finally {
          setGlobalLoading(false);
        }
      }
    };
    input.click();
  };

  const handleUploadWithAIClick = () => {
    const input = document.createElement('input');
    input.type = 'file';
    input.onchange = async (e) => {
      if (e.target.files && e.target.files[0]) {
        const file = e.target.files[0];
        setGlobalLoading(true, "Upload con AI in corso...");
        try {
          await api.uploadDocumentWithAI(file);
          addToast(
            `'${file.name}' caricato. L'AI lo sta classificando: comparirà in Inbox o nella cartella scelta entro qualche istante.`,
            "success"
          );
          fetchItems();
          if (onNavigate) onNavigate('inbox');
        } catch (err) {
          addToast(`Errore upload AI: ${err.message}`, "error");
        } finally {
          setGlobalLoading(false);
        }
      }
    };
    input.click();
  };

  const handleUploadFolderClick = () => {
    const input = document.createElement('input');
    input.type = 'file';
    input.webkitdirectory = true;
    input.directory = true;
    input.onchange = async (e) => {
      if (e.target.files && e.target.files.length > 0) {
        setGlobalLoading(true, `Caricamento cartella (${e.target.files.length} file)...`);
        try {
          console.log(`Uploading ${e.target.files.length} files from folder...`);
          await api.uploadFolder(Array.from(e.target.files), currentFolderId);
          addToast("Cartella caricata con successo", "success");
          fetchItems();
        } catch (err) {
          console.error('Folder upload error:', err);
          addToast(`Errore durante il caricamento cartella: ${err.message}`, "error");
        } finally {
          setGlobalLoading(false);
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
      setGlobalLoading(true, "Spostamento in corso...");
      try {
        await api.moveItem(itemId, itemType, currentFolderId);
        addToast("Elemento spostato con successo", "success");
        fetchItems();
      } catch (err) {
        addToast(`Errore spostamento: ${err.message}`, "error");
      } finally {
        setGlobalLoading(false);
      }
    } else {
      const files = e.dataTransfer.files;
      if (files && files.length > 0) {
        setGlobalLoading(true, `Caricamento di ${files.length} file in corso...`);
        try {
          for (let i = 0; i < files.length; i++) {
            await api.uploadDocument(files[i], currentFolderId);
          }
          addToast("File caricati con successo", "success");
          fetchItems();
        } catch (err) {
          addToast(`Errore durante il caricamento: ${err.message}`, "error");
        } finally {
          setGlobalLoading(false);
        }
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

  const handleDelete = (id, type) => {
    setConfirmDialog({
      open: true,
      title: 'Elimina elemento',
      message: 'Questa azione è irreversibile. Sei sicuro di voler eliminare questo elemento?',
      confirmLabel: 'Elimina',
      variant: 'danger',
      onConfirm: async () => {
        setConfirmDialog({ open: false });
        setGlobalLoading(true, "Eliminazione in corso...");
        try {
          await api.deleteItem(id, type);
          addToast("Elemento eliminato con successo", "success");
          fetchItems();
        } catch (err) {
          addToast(`Errore eliminazione: ${err.message}`, "error");
        } finally {
          setGlobalLoading(false);
        }
      },
      onCancel: () => setConfirmDialog({ open: false }),
    });
  };

  const handleDragMove = async (draggedId, draggedType, destinationFolderId) => {
    setGlobalLoading(true, "Spostamento in corso...");
    try {
      await api.moveItem(draggedId, draggedType, destinationFolderId);
      addToast("Elemento spostato con successo", "success");
      fetchItems();
    } catch (err) {
      addToast(`Errore spostamento: ${err.message}`, "error");
    } finally {
      setGlobalLoading(false);
    }
  };

  const navigateToFolder = (folder) => {
    setCurrentFolderId(folder.id);
    setCurrentFolderPermission(folder.permission || null);
    setBreadcrumb([...breadcrumb, { id: folder.id, name: folder.name, permission: folder.permission || null }]);
    
    // Mark as read
    const readMap = JSON.parse(localStorage.getItem('dms_read_agent_folders') || '{}');
    readMap[folder.id] = Date.now();
    localStorage.setItem('dms_read_agent_folders', JSON.stringify(readMap));
    
    setAgentModifiedFolders(prev => {
      const next = new Set(prev);
      next.delete(folder.id);
      return next;
    });
  };

  const navigateBreadcrumb = (index) => {
    const newCrumb = breadcrumb[index];
    setCurrentFolderId(newCrumb.id);
    setCurrentFolderPermission(index === 0 ? null : newCrumb.permission || null);
    setBreadcrumb(breadcrumb.slice(0, index + 1));
  };

  const handleDownload = async (doc) => {
    setGlobalLoading(true, "Preparazione download in corso...");
    try {
      await api.downloadDocument(doc.id, doc.name);
      addToast("Download avviato", "success");
    } catch (err) {
      addToast(`Errore download: ${err.message}`, "error");
    } finally {
      setGlobalLoading(false);
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
                <Upload size={16} /> Upload File
              </button>
              <button className="btn-primary" onClick={handleUploadFolderClick}>
                <Upload size={16} /> Upload Folder
              </button>
              <button
                className="btn-primary btn-ai"
                onClick={handleUploadWithAIClick}
                title="L'agente AI classifica e archivia il file nella cartella più appropriata"
              >
                <Sparkles size={16} /> Upload File with AI
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
              currentFolderPermission={currentFolderPermission}
              currentUser={currentUser}
              isAgentModified={agentModifiedFolders.has(f.id)}
              onNavigate={() => navigateToFolder(f)}
              onDelete={() => handleDelete(f.id, 'folder')}
              onShare={() => setShareModalData({ id: f.id, type: 'folder' })}
              onMove={() => setMoveModalData({ id: f.id, type: 'folder', isShared: view === 'shared' })}
              onDragMove={(draggedId, draggedType) => handleDragMove(draggedId, draggedType, f.id)}
            />
          ))}
          {items.documents.map(d => (
            <ItemCard
              key={d.id}
              item={d}
              type="document"
              isShared={view === 'shared'}
              currentFolderPermission={currentFolderPermission}
              currentUser={currentUser}
              onDownload={() => handleDownload(d)}
              onDelete={() => handleDelete(d.id, 'document')}
              onShare={() => setShareModalData({ id: d.id, type: 'document' })}
              onMove={() => setMoveModalData({ id: d.id, type: 'document', isShared: view === 'shared' })}
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
          isShared={moveModalData.isShared}
          onClose={() => {
            setMoveModalData(null);
            fetchItems();
          }}
        />
      )}

      <PromptDialog
        isOpen={promptDialog.open}
        title={promptDialog.title}
        inputLabel={promptDialog.inputLabel}
        placeholder={promptDialog.placeholder}
        confirmLabel="Crea"
        cancelLabel="Annulla"
        onConfirm={promptDialog.onConfirm}
        onCancel={promptDialog.onCancel}
      />

      <ConfirmDialog
        isOpen={confirmDialog.open}
        title={confirmDialog.title}
        message={confirmDialog.message}
        variant={confirmDialog.variant}
        confirmLabel={confirmDialog.confirmLabel}
        cancelLabel="Annulla"
        onConfirm={confirmDialog.onConfirm}
        onCancel={confirmDialog.onCancel}
      />
    </div>
  );
}

function ItemCard({ item, type, isShared, currentFolderPermission, currentUser, isAgentModified, onNavigate, onDownload, onDelete, onShare, onMove, onDragMove }) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const menuRef = useRef(null);
  const cardRef = useRef(null);
  const isOwner = currentUser && currentUser.id === item.owner_id;
  const isEditor = !isShared || item.permission === 'EDITOR';
  const canDelete = isOwner || !isShared || item.permission === 'EDITOR' || currentFolderPermission === 'EDITOR';

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
        {type === 'folder' ? (
          <div className="folder-icon-wrapper">
            <Folder size={32} color="var(--brand-primary)" fill="#dbeafe" />
            {isAgentModified && <span className="agent-indicator"></span>}
          </div>
        ) : (
          <FileIcon size={32} color="#64748b" />
        )}
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

            {isOwner && (
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
