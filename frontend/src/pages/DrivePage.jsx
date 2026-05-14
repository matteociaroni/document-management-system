import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';
import { useBranding } from '../context/BrandingContext';
import { LogOut, HardDrive, Users, Clock, ShieldEllipsis, Mail, Bot, Inbox, Search } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { api } from '../services/api';
import FileBrowser from '../components/FileBrowser';
import HistoryView from '../components/HistoryView';
import EmailAccountsPage from './EmailAccountsPage';
import AgentHistoryView from '../components/AgentHistoryView';
import InboxView from '../components/InboxView';
import SearchView from '../components/SearchView';
import './DrivePage.css';

export default function DrivePage() {
  const { user, logout } = useAuth();
  const { displayName, logoUrl } = useBranding();
  const [currentView, setCurrentView] = useState('my-drive');
  const [inboxCount, setInboxCount] = useState(0);
  const [searchQuery, setSearchQuery] = useState('');
  const [debouncedQuery, setDebouncedQuery] = useState('');
  const [initialFolder, setInitialFolder] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    const fetchInboxCount = async () => {
      try {
        const proposals = await api.listProposals();
        setInboxCount(proposals.length);
      } catch (err) {
        console.error('Failed to fetch inbox count:', err);
      }
    };

    fetchInboxCount();
    // Refresh count periodically or when switching views
    const interval = setInterval(fetchInboxCount, 30000);
    return () => clearInterval(interval);
  }, [currentView]);

  // Debounce search input
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedQuery(searchQuery);
      if (searchQuery.trim().length > 0) {
        setCurrentView('search');
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  const handleSearchChange = (e) => {
    setSearchQuery(e.target.value);
  };

  const handleSearchClear = () => {
    setSearchQuery('');
    setDebouncedQuery('');
    if (currentView === 'search') {
      setCurrentView('my-drive');
    }
  };

  const handleNavClick = (view) => {
    setSearchQuery('');
    setDebouncedQuery('');
    setInitialFolder(null);
    setCurrentView(view);
  };

  const handleOpenFolderFromSearch = (folderId, pathChain) => {
    setSearchQuery('');
    setDebouncedQuery('');
    setInitialFolder({ id: folderId, pathChain: pathChain || [] });
    setCurrentView('my-drive');
  };

  return (
    <div className="drive-layout">
      {/* Sidebar */}
      <aside className="sidebar">
        <div className="sidebar-header">
          {logoUrl && <img src={logoUrl} alt="" className="brand-logo" />}
          <div className="brand">{displayName}</div>
        </div>

        {/* Search bar */}
        <div className="sidebar-search">
          <Search size={16} className="search-icon" />
          <input
            type="text"
            className="search-input"
            placeholder="Cerca nei documenti..."
            value={searchQuery}
            onChange={handleSearchChange}
          />
          {searchQuery && (
            <button className="search-clear" onClick={handleSearchClear}>
              ✕
            </button>
          )}
        </div>

        <nav className="sidebar-nav">
          <div className="nav-section-title">Drive</div>
          <button
            className={`nav-item ${currentView === 'my-drive' ? 'active' : ''}`}
            onClick={() => handleNavClick('my-drive')}
          >
            <HardDrive size={20} />
            My Drive
          </button>

          <button
            className={`nav-item ${currentView === 'shared' ? 'active' : ''}`}
            onClick={() => handleNavClick('shared')}
          >
            <Users size={20} />
            Shared with me
          </button>

          <button
            className={`nav-item ${currentView === 'history' ? 'active' : ''}`}
            onClick={() => handleNavClick('history')}
          >
            <Clock size={20} />
            History
          </button>

          <div className="nav-section-title">Agentic Integration</div>
          <button
            className={`nav-item ${currentView === 'email-accounts' ? 'active' : ''}`}
            onClick={() => handleNavClick('email-accounts')}
          >
            <Mail size={20} />
            Email Accounts
          </button>
          <button
            className={`nav-item ${currentView === 'agent-history' ? 'active' : ''}`}
            onClick={() => handleNavClick('agent-history')}
          >
            <Bot size={20} />
            Agent History
          </button>
          <button
            className={`nav-item ${currentView === 'inbox' ? 'active' : ''}`}
            onClick={() => handleNavClick('inbox')}
            style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
              <Inbox size={20} />
              Inbox
            </div>
            {inboxCount > 0 && (
              <span className="inbox-badge" style={{ 
                backgroundColor: 'var(--brand-primary)', 
                color: 'white', 
                borderRadius: '9999px', 
                padding: '0.125rem 0.5rem', 
                fontSize: '0.75rem', 
                fontWeight: 'bold' 
              }}>
                {inboxCount}
              </span>
            )}
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
                <ShieldEllipsis size={20} color="#818cf8" />
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
        {currentView === 'my-drive' && (
          <FileBrowser
            key={initialFolder ? `mydrive-${initialFolder.id || 'root'}-${Date.now()}` : 'mydrive'}
            view="my-drive"
            onNavigate={handleNavClick}
            initialFolder={initialFolder}
          />
        )}
        {currentView === 'shared' && <FileBrowser view="shared" onNavigate={handleNavClick} />}
        {currentView === 'history' && <HistoryView />}
        {currentView === 'agent-history' && <AgentHistoryView />}
        {currentView === 'inbox' && <InboxView />}
        {currentView === 'email-accounts' && <EmailAccountsPage />}
        {currentView === 'search' && (
          <SearchView query={debouncedQuery} onOpenFolder={handleOpenFolderFromSearch} />
        )}
      </main>
    </div>
  );
}
