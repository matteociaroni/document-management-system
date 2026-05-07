import { useState, useEffect } from 'react';
import { api } from '../services/api';
import { Bot, FileDown, FolderTree, Mail, AlertCircle, Inbox, CopyX } from 'lucide-react';
import './AgentHistoryView.css';

const getOperationIcon = (type) => {
  switch (type) {
    case 'email_received':
      return <Mail size={18} className="op-icon email" />;
    case 'attachment_extracted':
      return <FileDown size={18} className="op-icon extract" />;
    case 'auto_filed':
      return <FolderTree size={18} className="op-icon file" />;
    case 'sent_to_inbox':
      return <Inbox size={18} className="op-icon inbox" />;
    case 'duplicate_skipped':
      return <CopyX size={18} className="op-icon skip" />;
    case 'error':
      return <AlertCircle size={18} className="op-icon error" />;
    default:
      return <Bot size={18} className="op-icon default" />;
  }
};

const getOperationLabel = (type) => {
  return type.split('_').map(word => word.charAt(0).toUpperCase() + word.slice(1)).join(' ');
};

export default function AgentHistoryView() {
  const [operations, setOperations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchOperations = async () => {
      try {
        const data = await api.getAgentOperations();
        setOperations(data);
      } catch (err) {
        console.error("Failed to fetch agent operations", err);
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };
    fetchOperations();
  }, []);

  return (
    <div className="agent-history-view">
      <div className="history-header">
        <Bot size={28} className="header-icon" />
        <h2 className="history-title">Agent Activity Log</h2>
      </div>
      
      {error && <div className="error-state">{error}</div>}
      
      {loading ? (
        <div className="loading-state">Loading operations...</div>
      ) : operations.length === 0 ? (
        <div className="empty-state">
          <Bot size={48} opacity={0.2} />
          <p>No recent agent activity.</p>
        </div>
      ) : (
        <div className="agent-history-list">
          {operations.map(op => (
            <div key={op.id} className="agent-history-item">
              <div className="op-icon-container">
                {getOperationIcon(op.operation_type)}
              </div>
              <div className="op-content">
                <div className="op-header">
                  <span className="op-type">{getOperationLabel(op.operation_type)}</span>
                  <span className="op-time">{new Date(op.created_at).toLocaleString()}</span>
                </div>
                <div className="op-description">{op.description}</div>
                {op.details && op.details.folder_name && (
                  <div className="op-details">
                    <FolderTree size={14} />
                    <span>{op.details.folder_name}</span>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
