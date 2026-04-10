import { useState, useEffect } from 'react';
import { api } from '../services/api';
import './HistoryView.css';

export default function HistoryView() {
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchHistory = async () => {
      const data = await api.getHistory();
      setHistory(data);
      setLoading(false);
    };
    fetchHistory();
  }, []);

  return (
    <div className="history-view">
      <h2 className="history-title">Activity History</h2>
      
      {loading ? (
        <div className="loading-state">Loading...</div>
      ) : history.length === 0 ? (
        <div className="empty-state">No recent activity.</div>
      ) : (
        <div className="history-list">
          {history.map(item => (
            <div key={item.id} className="history-item">
              <div className="history-action">{item.action}</div>
              <div className="history-time">{new Date(item.timestamp).toLocaleString()}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
