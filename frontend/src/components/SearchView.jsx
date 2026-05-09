import { useState, useEffect } from 'react';
import { api } from '../services/api';
import { File as FileIcon, Download, Search, FileText } from 'lucide-react';
import { useUI } from '../context/UIContext';
import './SearchView.css';

export default function SearchView({ query }) {
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
      await api.downloadDocument(result.document_id, result.filename);
      addToast('Download avviato', 'success');
    } catch (err) {
      addToast(`Errore download: ${err.message}`, 'error');
    }
  };

  const getFileIcon = (mimeType) => {
    if (!mimeType) return <FileIcon size={24} color="#64748b" />;
    if (mimeType.startsWith('text/') || mimeType.includes('pdf') || mimeType.includes('document')) {
      return <FileText size={24} color="#3b82f6" />;
    }
    return <FileIcon size={24} color="#64748b" />;
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
            <div key={result.document_id} className="search-result-card">
              <div className="result-icon">
                {getFileIcon(result.mime_type)}
              </div>
              <div className="result-content">
                <div className="result-filename">{result.filename}</div>
                {result.highlight && (
                  <div
                    className="result-highlight"
                    dangerouslySetInnerHTML={{ __html: result.highlight }}
                  />
                )}
                <div className="result-meta">
                  {result.mime_type && (
                    <span className="result-mime">{result.mime_type}</span>
                  )}
                  <span className="result-score">
                    Rilevanza: {(result.score * 10).toFixed(1)}
                  </span>
                </div>
              </div>
              <div className="result-actions">
                <button
                  className="btn-icon"
                  onClick={() => handleDownload(result)}
                  title="Download"
                >
                  <Download size={18} />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
