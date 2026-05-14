import { useState, useEffect } from 'react';
import { api } from '../services/api';
import { File as FileIcon, Folder as FolderIcon, Download, Search, FileText, FolderOpen } from 'lucide-react';
import { useUI } from '../context/UIContext';
import './SearchView.css';

export default function SearchView({ query, onOpenFolder }) {
  const [results, setResults] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);
  const { addToast } = useUI();

  useEffect(() => {
    if (!query || query.trim().length === 0) {
      setResults([]);
      setTotal(0);
      setSearched(false);
      return;
    }

    const fetchResults = async () => {
      setLoading(true);
      try {
        const data = await api.searchDocuments(query.trim());
        setResults(data.results || []);
        setTotal(data.total || 0);
        setSearched(true);
      } catch (err) {
        console.error('Search failed:', err);
        setResults([]);
        setTotal(0);
        setSearched(true);
      } finally {
        setLoading(false);
      }
    };

    fetchResults();
  }, [query]);

  const handleDownload = async (result) => {
    try {
      await api.downloadDocument(result.id, result.name);
      addToast('Download avviato', 'success');
    } catch (err) {
      addToast(`Errore download: ${err.message}`, 'error');
    }
  };

  const handleGoToParent = (result) => {
    if (!onOpenFolder) return;
    // For documents: open the folder containing the file (last item in path).
    // For folders: open the folder itself (path = ancestors only).
    const targetChain = result.type === 'folder'
      ? [...(result.path || []), { id: result.id, name: result.name }]
      : (result.path || []);
    const targetId = targetChain.length > 0 ? targetChain[targetChain.length - 1].id : null;
    onOpenFolder(targetId, targetChain);
  };

  const getFileIcon = (result) => {
    if (result.type === 'folder') {
      return <FolderIcon size={24} color="var(--brand-primary)" fill="#dbeafe" />;
    }
    const mimeType = result.mime_type;
    if (mimeType && (mimeType.startsWith('text/') || mimeType.includes('pdf') || mimeType.includes('document'))) {
      return <FileText size={24} color="#3b82f6" />;
    }
    return <FileIcon size={24} color="#64748b" />;
  };

  const getFriendlyType = (result) => {
    if (result.type === 'folder') return 'Folder';
    const mime = (result.mime_type || '').toLowerCase();
    const name = (result.name || '').toLowerCase();
    const ext = name.includes('.') ? name.split('.').pop() : '';

    if (mime.includes('pdf') || ext === 'pdf') return 'PDF';
    if (mime.includes('wordprocessingml') || mime === 'application/msword' || ext === 'doc' || ext === 'docx') return 'Word';
    if (mime.includes('spreadsheetml') || mime.includes('ms-excel') || ext === 'xls' || ext === 'xlsx' || ext === 'csv') return 'Spreadsheet';
    if (mime.includes('presentationml') || mime.includes('ms-powerpoint') || ext === 'ppt' || ext === 'pptx') return 'Presentation';
    if (mime.startsWith('image/') || ['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg', 'bmp'].includes(ext)) return 'Image';
    if (mime.startsWith('video/')) return 'Video';
    if (mime.startsWith('audio/')) return 'Audio';
    if (mime.startsWith('text/') || ['txt', 'md', 'log'].includes(ext)) return 'Text';
    if (mime.includes('zip') || mime.includes('compressed') || ['zip', 'rar', '7z', 'tar', 'gz'].includes(ext)) return 'Archive';
    if (mime.includes('json') || ext === 'json') return 'JSON';
    if (mime.includes('xml') || ext === 'xml') return 'XML';
    if (mime.includes('html') || ext === 'html' || ext === 'htm') return 'HTML';
    if (ext) return ext.toUpperCase();
    return 'File';
  };

  const renderPath = (result) => {
    const segments = ['My Drive', ...(result.path || []).map(p => p.name)];
    return segments.join(' / ');
  };

  return (
    <div className="search-view">
      <div className="search-header">
        <Search size={24} color="var(--text-secondary)" />
        <h2>Risultati di ricerca</h2>
        {searched && (
          <span className="search-count">
            {total} {total === 1 ? 'risultato' : 'risultati'} per "{query}"
          </span>
        )}
      </div>

      {loading ? (
        <div className="search-loading">
          <div className="search-spinner"></div>
          <p>Ricerca in corso...</p>
        </div>
      ) : searched && results.length === 0 ? (
        <div className="search-empty">
          <Search size={48} color="var(--text-secondary)" />
          <h3>Nessun risultato</h3>
          <p>Nessun documento trovato per "{query}"</p>
        </div>
      ) : (
        <div className="search-results">
          {results.map((result) => (
            <div key={`${result.type}-${result.id}`} className="search-result-card">
              <div className="result-icon">
                {getFileIcon(result)}
              </div>
              <div className="result-content">
                <div className="result-filename">{result.name}</div>
                <div className="result-path" title={renderPath(result)}>
                  {renderPath(result)}
                </div>
                {result.highlight && (
                  <div
                    className="result-highlight"
                    dangerouslySetInnerHTML={{ __html: result.highlight }}
                  />
                )}
                {result.type === 'document' && (
                  <div className="result-meta">
                    <span className="result-mime">{getFriendlyType(result)}</span>
                  </div>
                )}
              </div>
              <div className="result-actions">
                <button
                  className="btn-icon"
                  onClick={() => handleGoToParent(result)}
                  title={result.type === 'folder' ? 'Apri cartella' : 'Vai alla cartella padre'}
                >
                  <FolderOpen size={18} />
                </button>
                {result.type === 'document' && (
                  <button
                    className="btn-icon"
                    onClick={() => handleDownload(result)}
                    title="Download"
                  >
                    <Download size={18} />
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
