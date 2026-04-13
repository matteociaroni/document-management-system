import { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { LogOut, HardDrive, Users, Clock, Settings } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import FileBrowser from '../components/FileBrowser';
import HistoryView from '../components/HistoryView';
import './DrivePage.css';

export default function DrivePage() {
  const { user, logout } = useAuth();
  const [currentView, setCurrentView] = useState('my-drive'); // my-drive | shared | history
  const navigate = useNavigate();

  return (
    <div className="drive-layout">
      {/* Sidebar */}
      <aside className="sidebar">
        <div className="sidebar-header">
          <div className="brand">DMS Cloud</div>
        </div>
        
        <nav className="sidebar-nav">
          <button 
            className={`nav-item ${currentView === 'my-drive' ? 'active' : ''}`}
            onClick={() => setCurrentView('my-drive')}
          >
            <HardDrive size={20} />
            My Drive
          </button>
          
          <button 
            className={`nav-item ${currentView === 'shared' ? 'active' : ''}`}
            onClick={() => setCurrentView('shared')}
          >
            <Users size={20} />
            Shared with me
          </button>
          
          <button 
            className={`nav-item ${currentView === 'history' ? 'active' : ''}`}
            onClick={() => setCurrentView('history')}
          >
            <Clock size={20} />
            History
          </button>
        </nav>
        
        <div className="sidebar-footer">
          <div className="user-info">
            <div className="avatar">{user?.username?.[0]?.toUpperCase() || 'U'}</div>
            <div className="user-text">
              <span className="username">{user?.username}</span>
              <span className="user-email">{user?.email}</span>
            </div>
          </div>
          <div className="footer-actions" style={{ display: 'flex', gap: '0.5rem' }}>
            {user?.role === 'DOMAIN_ADMIN' && (
              <button className="btn-icon" onClick={() => navigate('/admin')} title="Admin Dashboard">
                <Settings size={20} color="#818cf8" />
              </button>
            )}
            <button className="btn-icon" onClick={logout} title="Logout">
              <LogOut size={20} />
            </button>
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="main-content">
        {currentView === 'my-drive' && <FileBrowser view="my-drive" />}
        {currentView === 'shared' && <FileBrowser view="shared" />}
        {currentView === 'history' && <HistoryView />}
      </main>
    </div>
  );
}
