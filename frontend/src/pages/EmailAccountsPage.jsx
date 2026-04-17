import { useState, useEffect } from 'react';
import { api } from '../services/api';
import { Mail, Plus, Trash2, CheckCircle, AlertCircle } from 'lucide-react';
import './EmailAccountsPage.css';

const EmailAccountForm = ({ onClose, onSuccess }) => {
  const [formData, setFormData] = useState({
    email_address: '',
    imap_host: '',
    imap_port: 993,
    use_ssl: true,
    auth_type: 'app_password',
    credentials: '',
  });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : (name === 'imap_port' ? parseInt(value) : value)
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      await api.createEmailAccount(formData);
      onSuccess();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-overlay">
      <div className="modal-content">
        <div className="modal-header">
          <h2>Add Email Account</h2>
          <button onClick={onClose} className="btn-close">×</button>
        </div>
        <form onSubmit={handleSubmit} className="modal-form">
          {error && <div className="modal-alert error">{error}</div>}
          
          <div className="form-group">
            <label className="form-label">Email Address</label>
            <input
              type="email"
              name="email_address"
              value={formData.email_address}
              onChange={handleChange}
              className="form-input"
              required
            />
          </div>

          <div className="form-group">
            <label className="form-label">IMAP Host</label>
            <input
              type="text"
              name="imap_host"
              value={formData.imap_host}
              onChange={handleChange}
              placeholder="imap.gmail.com"
              className="form-input"
              required
            />
          </div>

          <div className="form-row">
            <div className="form-group">
              <label className="form-label">IMAP Port</label>
              <input
                type="number"
                name="imap_port"
                value={formData.imap_port}
                onChange={handleChange}
                className="form-input"
                required
              />
            </div>
            <div className="form-group">
              <label className="form-label">
                <input
                  type="checkbox"
                  name="use_ssl"
                  checked={formData.use_ssl}
                  onChange={handleChange}
                  style={{ marginRight: '0.5rem' }}
                />
                Use SSL
              </label>
            </div>
          </div>

          <div className="form-group">
            <label className="form-label">Auth Type</label>
            <select name="auth_type" value={formData.auth_type} onChange={handleChange} className="form-input">
              <option value="app_password">App Password</option>
              <option value="oauth2">OAuth2</option>
            </select>
          </div>

          <div className="form-group">
            <label className="form-label">
              {formData.auth_type === 'app_password' ? 'Password' : 'Access Token'}
            </label>
            <input
              type="password"
              name="credentials"
              value={formData.credentials}
              onChange={handleChange}
              className="form-input"
              required
            />
          </div>
        </form>

        <div className="modal-footer">
          <button onClick={onClose} className="btn btn-secondary">Cancel</button>
          <button onClick={handleSubmit} disabled={loading} className="btn btn-primary">
            {loading ? 'Creating...' : 'Create Account'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default function EmailAccountsPage() {
  const [accounts, setAccounts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [testing, setTesting] = useState(null);
  const [updatingSync, setUpdatingSync] = useState(null);
  const [testResults, setTestResults] = useState({});

  useEffect(() => {
    loadAccounts();
  }, []);

  const loadAccounts = async () => {
    setLoading(true);
    try {
      const data = await api.listEmailAccounts();
      setAccounts(data);
    } catch (err) {
      console.error('Failed to load accounts', err);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (accountId) => {
    if (!confirm('Delete this email account?')) return;
    try {
      await api.deleteEmailAccount(accountId);
      setAccounts(accounts.filter(a => a.id !== accountId));
    } catch (err) {
      alert('Error deleting account: ' + err.message);
    }
  };

  const handleTest = async (account) => {
    setTesting(account.id);
    try {
      const result = await api.testEmailAccount(account.id);
      setTestResults(prev => ({
        ...prev,
        [account.id]: result
      }));
    } catch (err) {
      setTestResults(prev => ({
        ...prev,
        [account.id]: { success: false, message: err.message }
      }));
    } finally {
      setTesting(null);
    }
  };

  const handleToggleSync = async (account) => {
    setUpdatingSync(account.id);
    try {
      const updated = await api.updateEmailAccount(account.id, { is_active: !account.is_active });
      setAccounts(prev => prev.map(a => (a.id === account.id ? updated : a)));
    } catch (err) {
      alert('Error updating sync status: ' + err.message);
    } finally {
      setUpdatingSync(null);
    }
  };

  if (loading) {
    return (
      <div className="email-accounts-page">
        <div className="page-header">
          <h1><Mail size={28} /> Email Accounts</h1>
        </div>
        <div className="loading">Loading...</div>
      </div>
    );
  }

  return (
    <div className="email-accounts-page">
      <div className="page-header">
        <h1><Mail size={28} /> Email Accounts</h1>
        <button onClick={() => setShowForm(true)} className="btn btn-primary">
          <Plus size={18} /> Add Account
        </button>
      </div>

      {showForm && (
        <EmailAccountForm
          onClose={() => setShowForm(false)}
          onSuccess={() => {
            setShowForm(false);
            loadAccounts();
          }}
        />
      )}

      <div className="accounts-grid">
        {accounts.length === 0 ? (
          <div className="empty-state">
            <Mail size={48} />
            <p>No email accounts yet</p>
            <button onClick={() => setShowForm(true)} className="btn btn-primary">
              Add Your First Account
            </button>
          </div>
        ) : (
          accounts.map(account => (
            <div key={account.id} className="account-card">
              <div className="account-header">
                <h3>{account.email_address}</h3>
                <div className="account-header-actions">
                  <label className="sync-switch" title={account.is_active ? 'Disable sync' : 'Enable sync'}>
                    <input
                      type="checkbox"
                      checked={account.is_active}
                      disabled={updatingSync === account.id}
                      onChange={() => handleToggleSync(account)}
                    />
                    <span className="sync-switch-slider" />
                  </label>
                  <button
                    onClick={() => handleDelete(account.id)}
                    className="btn-icon-danger"
                    title="Delete"
                  >
                    <Trash2 size={18} />
                  </button>
                </div>
              </div>

              <div className="account-details">
                <div className="detail-row">
                  <span className="label">Host:</span>
                  <span className="value">{account.imap_host}:{account.imap_port}</span>
                </div>
                <div className="detail-row">
                  <span className="label">SSL:</span>
                  <span className="value">{account.use_ssl ? 'Yes' : 'No'}</span>
                </div>
                <div className="detail-row">
                  <span className="label">Auth:</span>
                  <span className="value">{account.auth_type === 'app_password' ? 'App Password' : 'OAuth2'}</span>
                </div>
                <div className="detail-row">
                  <span className="label">Status:</span>
                  <span className="value">{account.is_active ? '✓ Active' : 'Inactive'}</span>
                </div>
                <div className="detail-row">
                  <span className="label">Created:</span>
                  <span className="value">{new Date(account.created_at).toLocaleDateString()}</span>
                </div>
                <div className="detail-row">
                  <span className="label">Last Synced:</span>
                  <span className="value">
                    {account.last_synced_at ? new Date(account.last_synced_at).toLocaleString() : 'Never'}
                  </span>
                </div>
              </div>

              <button
                onClick={() => handleTest(account)}
                disabled={testing === account.id}
                className="btn btn-secondary btn-full"
              >
                {testing === account.id ? 'Testing...' : 'Test Connection'}
              </button>

              {testResults[account.id] && (
                <div className={`test-result ${testResults[account.id].success ? 'success' : 'error'}`}>
                  {testResults[account.id].success ? (
                    <CheckCircle size={16} />
                  ) : (
                    <AlertCircle size={16} />
                  )}
                  <span>{testResults[account.id].message}</span>
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
