import { useState, useEffect } from 'react';
import { api } from '../services/api';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useUI } from '../context/UIContext';
import { ShieldAlert, Users, Database, Activity, RefreshCw, ArrowLeft, ShieldCheck, Power, Activity as ActivityLog } from 'lucide-react';
import './AdminPage.css';

const AdminPage = () => {
    const { user } = useAuth();
    const navigate = useNavigate();
    
    const [metrics, setMetrics] = useState(null);
    const [domainUsers, setDomainUsers] = useState([]);
    const [auditLogs, setAuditLogs] = useState([]);
    const [loading, setLoading] = useState(true);
    const [activeTab, setActiveTab] = useState('users');
    const { setLoading: setGlobalLoading, addToast } = useUI();

    useEffect(() => {
        if (!user || user.role !== 'DOMAIN_ADMIN') {
            navigate('/drive');
            return;
        }
        
        loadData();
    }, [user, navigate]);

    const loadData = async () => {
        setLoading(true);
        try {
            const [mRes, uRes, aRes] = await Promise.all([
                api.getDomainMetrics(),
                api.getDomainUsers(),
                api.getDomainAudit()
            ]);
            setMetrics(mRes);
            setDomainUsers(uRes);
            setAuditLogs(aRes);
        } catch (error) {
            console.error("Failed to load admin data", error);
        } finally {
            setLoading(false);
        }
    };

    const toggleUserStatus = async (targetUser) => {
        if (targetUser.id === user.id) return;
        setGlobalLoading(true, "Aggiornamento stato utente...");
        try {
            await api.updateDomainUserStatus(targetUser.id, !targetUser.is_active);
            setDomainUsers(users => users.map(u => u.id === targetUser.id ? { ...u, is_active: !targetUser.is_active } : u));
            addToast("Stato utente aggiornato", "success");
        } catch (error) {
            addToast(`Errore aggiornamento stato: ${error.message}`, "error");
        } finally {
            setGlobalLoading(false);
        }
    };

    const toggleUserRole = async (targetUser) => {
        if (targetUser.id === user.id) return;
        const newRole = targetUser.role === 'DOMAIN_ADMIN' ? 'USER' : 'DOMAIN_ADMIN';
        setGlobalLoading(true, "Aggiornamento ruolo utente...");
        try {
            await api.updateDomainUserRole(targetUser.id, newRole);
            setDomainUsers(users => users.map(u => u.id === targetUser.id ? { ...u, role: newRole } : u));
            addToast("Ruolo utente aggiornato", "success");
        } catch (error) {
            addToast(`Errore aggiornamento ruolo: ${error.message}`, "error");
        } finally {
            setGlobalLoading(false);
        }
    };

    const formatBytes = (bytes) => {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    };

    if (loading || !metrics) {
        return <div className="admin-loading"><RefreshCw className="spin" size={32} /> Loading Admin Workspace...</div>;
    }

    return (
        <div className="admin-container">
            <header className="admin-header">
                <div className="header-left">
                    <button onClick={() => navigate('/drive')} className="btn-icon tooltip" data-tooltip="Back to Drive">
                        <ArrowLeft />
                    </button>
                    <h1>Workspace Control Center</h1>
                </div>
                <div className="header-right">
                    <span className="domain-badge"><ShieldAlert size={16} /> @{user.email.split('@')[1]}</span>
                </div>
            </header>

            <div className="metrics-grid">
                <div className="metric-card">
                    <div className="metric-icon"><Users size={24} /></div>
                    <div className="metric-info">
                        <h3>Total Accounts</h3>
                        <p>{metrics.total_users}</p>
                    </div>
                </div>
                <div className="metric-card">
                    <div className="metric-icon active"><Activity size={24} /></div>
                    <div className="metric-info">
                        <h3>Active Accounts</h3>
                        <p>{metrics.active_users}</p>
                    </div>
                </div>
                <div className="metric-card">
                    <div className="metric-icon storage"><Database size={24} /></div>
                    <div className="metric-info">
                        <h3>Total Storage</h3>
                        <p>{formatBytes(metrics.total_storage_bytes)}</p>
                    </div>
                </div>
            </div>

            <main className="admin-main">
                <div className="tabs">
                    <button className={activeTab === 'users' ? 'active' : ''} onClick={() => setActiveTab('users')}>User Directory</button>
                    <button className={activeTab === 'audit' ? 'active' : ''} onClick={() => setActiveTab('audit')}>Global Audit Log</button>
                </div>

                {activeTab === 'users' && (
                    <div className="tab-pane slide-up">
                        <div className="table-responsive">
                            <table className="admin-table">
                                <thead>
                                    <tr>
                                        <th>User</th>
                                        <th>Email</th>
                                        <th>Role</th>
                                        <th>Status</th>
                                        <th>Actions</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {domainUsers.map(u => (
                                        <tr key={u.id}>
                                            <td><div className="user-avatar">{u.username.charAt(0).toUpperCase()}</div> {u.username}</td>
                                            <td>{u.email}</td>
                                            <td><span className={'badge-role ' + u.role}>{u.role}</span></td>
                                            <td><span className={'badge-status ' + (u.is_active ? 'active' : 'suspended')}>{u.is_active ? 'Active' : 'Suspended'}</span></td>
                                            <td>
                                                {u.id !== user.id && (
                                                    <div className="action-buttons">
                                                        <button 
                                                            onClick={() => toggleUserRole(u)} 
                                                            className="btn-action toggle-role" 
                                                            title={u.role === 'DOMAIN_ADMIN' ? 'Demote to User' : 'Promote to Admin'}
                                                        >
                                                            <ShieldCheck size={16} />
                                                        </button>
                                                        <button 
                                                            onClick={() => toggleUserStatus(u)} 
                                                            className={'btn-action ' + (u.is_active ? 'danger' : 'success')}
                                                            title={u.is_active ? 'Suspend Account' : 'Activate Account'}
                                                        >
                                                            <Power size={16} />
                                                        </button>
                                                    </div>
                                                )}
                                                {u.id === user.id && <span className="muted-text">You</span>}
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>
                )}

                {activeTab === 'audit' && (
                    <div className="tab-pane slide-up">
                        <div className="audit-feed">
                            {auditLogs.length === 0 ? <p className="no-data">No audit logs found.</p> : null}
                            {auditLogs.map(log => {
                                const targetUser = domainUsers.find(u => u.id === log.user_id) || { username: 'Unknown User' };
                                return (
                                    <div key={log.id} className="audit-item">
                                        <div className="audit-icon"><ActivityLog size={18} /></div>
                                        <div className="audit-content">
                                            <p dangerouslySetInnerHTML={{ __html: `<strong>${targetUser.username}</strong> ${log.action}` }}></p>
                                            <span className="audit-time">{new Date(log.timestamp).toLocaleString()}</span>
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    </div>
                )}
            </main>
        </div>
    );
};

export default AdminPage;
