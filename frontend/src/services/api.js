const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const getHeaders = () => {
  const userStr = localStorage.getItem('dms_user');
  const headers = {
    'Content-Type': 'application/json',
  };
  if (userStr) {
    const user = JSON.parse(userStr);
    if (user.access_token) {
      headers['Authorization'] = `Bearer ${user.access_token}`;
    }
  }
  return headers;
};

// Error handler utility
const handleResponse = async (res) => {
  if (!res.ok) {
    let msg = 'API error';
    try {
      const data = await res.json();
      msg = data.detail || data.error || msg;
    } catch(e) {}
    throw new Error(msg);
  }
  return res.json();
};

export const api = {
  async login(email, password) {
    const res = await fetch(`${API_URL}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password })
    });
    const data = await handleResponse(res);
    
    // Fetch profile
    const meRes = await fetch(`${API_URL}/auth/me`, {
      headers: { 'Authorization': `Bearer ${data.access_token}` }
    });
    const me = await handleResponse(meRes);
    
    const user = { ...me, access_token: data.access_token };
    localStorage.setItem('dms_user', JSON.stringify(user));
    this.addHistory(`Logged in as ${email}`);
    return user;
  },

  async register(username, email, password) {
    const res = await fetch(`${API_URL}/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, email, password })
    });
    await handleResponse(res);
    // Auto-login after register
    return this.login(email, password);
  },

  logout() {
    fetch(`${API_URL}/auth/logout`, { method: 'POST', headers: getHeaders() }).catch(console.error);
    localStorage.removeItem('dms_user');
  },

  getCurrentUser() {
    return JSON.parse(localStorage.getItem('dms_user'));
  },

  async getDirectoryContents(folderId = null) {
    const query = folderId ? `?parent_id=${folderId}` : '';
    const dQuery = folderId ? `?folder_id=${folderId}` : '';
    
    const [folders, documents] = await Promise.all([
      fetch(`${API_URL}/folders${query}`, { headers: getHeaders() }).then(handleResponse),
      fetch(`${API_URL}/documents${dQuery}`, { headers: getHeaders() }).then(handleResponse)
    ]);
    
    return { folders, documents };
  },

  async getSharedWithMe() {
    const permissions = await fetch(`${API_URL}/permissions`, { headers: getHeaders() }).then(handleResponse);
    
    const folders = [];
    const documents = [];
    
    for (const p of permissions) {
      if (p.folder_id) {
        try {
          const f = await fetch(`${API_URL}/folders/${p.folder_id}`, { headers: getHeaders() }).then(handleResponse);
          folders.push({ ...f, permission: p.access_level });
        } catch (e) { console.error("Could not fetch shared folder", p.folder_id) }
      }
      if (p.document_id) {
        try {
          const d = await fetch(`${API_URL}/documents/${p.document_id}`, { headers: getHeaders() }).then(handleResponse);
          documents.push({ ...d, permission: p.access_level });
        } catch (e) { console.error("Could not fetch shared document", p.document_id) }
      }
    }
    return { folders, documents };
  },

  async createFolder(name, parentId = null) {
    const res = await fetch(`${API_URL}/folders`, {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify({ name, parent_id: parentId })
    });
    const folder = await handleResponse(res);
    this.addHistory(`Created folder "${name}"`);
    return folder;
  },

  async uploadDocument(file, folderId = null) {
    // Step 1: Request presigned URL from backend
    const formData = new FormData();
    formData.append('file', file);
    if (folderId) formData.append('folder_id', folderId);

    const headers = getHeaders();
    delete headers['Content-Type']; // Let browser set Content-Type for FormData

    const uploadRes = await fetch(`${API_URL}/documents/upload`, {
      method: 'POST',
      headers: headers,
      body: formData
    });
    const uploadData = await handleResponse(uploadRes);
    const documentId = uploadData.document_id;
    const presignedUrl = uploadData.upload_url;

    // Step 2: Upload file to S3 using presigned URL
    const fileUploadRes = await fetch(presignedUrl, {
      method: 'PUT',
      body: file,
      headers: {
        'Content-Type': file.type || 'application/octet-stream'
      }
    });
    if (!fileUploadRes.ok) {
      throw new Error(`File upload to S3 failed: ${fileUploadRes.status}`);
    }

    // Step 3: Confirm upload with backend
    const confirmRes = await fetch(`${API_URL}/documents/${documentId}/confirm`, {
      method: 'POST',
      headers: getHeaders()
    });
    await handleResponse(confirmRes);
    
    this.addHistory(`Uploaded document "${file.name}"`);
    return documentId;
  },

  async downloadDocument(documentId, filename) {
    const res = await fetch(`${API_URL}/documents/${documentId}/download`, { headers: getHeaders() });
    if (!res.ok) {
        const errorText = await res.text();
        throw new Error(`Download failed: ${res.status} ${errorText}`);
    }
    
    // Create a temporary link to trigger download securely
    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);
    
    this.addHistory(`Downloaded document "${filename}"`);
  },

  async deleteItem(id, type) {
    const route = type === 'folder' ? 'folders' : 'documents';
    const res = await fetch(`${API_URL}/${route}/${id}`, {
      method: 'DELETE',
      headers: getHeaders()
    });
    if (res.status !== 204) await handleResponse(res);
    this.addHistory(`Deleted ${type}`);
  },

  async moveItem(id, type, newParentId) {
    const route = type === 'folder' ? 'folders' : 'documents';
    const res = await fetch(`${API_URL}/${route}/${id}/move`, {
      method: 'PATCH',
      headers: getHeaders(),
      body: JSON.stringify({ new_folder_id: newParentId })
    });
    await handleResponse(res);
    this.addHistory(`Moved ${type}`);
  },

  async shareItem(id, type, email, accessLevel) {
    const body = {
      email,
      access_level: accessLevel,
      folder_id: type === 'folder' ? id : null,
      document_id: type === 'document' ? id : null
    };
    
    const res = await fetch(`${API_URL}/permissions/share`, {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify(body)
    });
    await handleResponse(res);
    this.addHistory(`Shared ${type} with ${email} as ${accessLevel}`);
  },

  async getItemPermissions(id, type) {
    const query = `?${type === 'folder' ? 'folder_id' : 'document_id'}=${id}`;
    const res = await fetch(`${API_URL}/permissions/resource/dummy${query}`, { 
      headers: getHeaders() 
    });
    return await handleResponse(res);
  },

  async deletePermission(permissionId) {
    const res = await fetch(`${API_URL}/permissions/${permissionId}`, {
      method: 'DELETE',
      headers: getHeaders()
    });
    if (res.status !== 204) await handleResponse(res);
    this.addHistory('Revoked sharing');
  },

  // History
  addHistory(action) {
    fetch(`${API_URL}/history`, {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify({ action })
    }).catch(console.error); // Best effort
  },

  async getHistory() {
    const res = await fetch(`${API_URL}/history`, { headers: getHeaders() });
    return await handleResponse(res);
  }
};
