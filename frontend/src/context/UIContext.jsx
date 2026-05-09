import React, { createContext, useState, useContext, useCallback, useRef } from 'react';

const UIContext = createContext(null);

export const UIProvider = ({ children }) => {
  const [toasts, setToasts] = useState([]);
  const [loading, setLoadingState] = useState({ isLoading: false, message: '' });

  // Upload task state: { total, completed, errors, currentFile, active }
  const [uploadTask, setUploadTask] = useState(null);
  const abortRef = useRef(null);

  const addToast = useCallback((message, type = 'info') => {
    const id = Math.random().toString(36).substring(2, 9);
    setToasts((prevToasts) => [...prevToasts, { id, message, type }]);

    // Auto dismiss after 3 seconds
    setTimeout(() => {
      removeToast(id);
    }, 3000);

    return id;
  }, []);

  const removeToast = useCallback((id) => {
    setToasts((prevToasts) => prevToasts.filter((toast) => toast.id !== id));
  }, []);

  const setLoading = useCallback((isLoading, message = 'Elaborazione in corso...') => {
    setLoadingState({ isLoading, message });
  }, []);

  // ── Background upload helpers ──────────────────────────────────────

  const startUploadTask = useCallback((totalFiles) => {
    const controller = new AbortController();
    abortRef.current = controller;
    setUploadTask({
      total: totalFiles,
      completed: 0,
      errors: 0,
      currentFile: '',
      active: true,
    });
    return controller;
  }, []);

  const updateUploadProgress = useCallback((completed, currentFile, errors = 0) => {
    setUploadTask((prev) => {
      if (!prev) return prev;
      return { ...prev, completed, currentFile, errors };
    });
  }, []);

  const finishUploadTask = useCallback(() => {
    abortRef.current = null;
    setUploadTask((prev) => {
      if (!prev) return null;
      return { ...prev, active: false };
    });
    // Auto-dismiss after 4 seconds
    setTimeout(() => {
      setUploadTask(null);
    }, 4000);
  }, []);

  const cancelUpload = useCallback(() => {
    if (abortRef.current) {
      abortRef.current.abort();
    }
  }, []);

  const dismissUploadTask = useCallback(() => {
    setUploadTask(null);
  }, []);

  return (
    <UIContext.Provider value={{
      toasts, addToast, removeToast,
      loading, setLoading,
      uploadTask, startUploadTask, updateUploadProgress, finishUploadTask, cancelUpload, dismissUploadTask,
    }}>
      {children}
    </UIContext.Provider>
  );
};

export const useUI = () => {
  const context = useContext(UIContext);
  if (!context) {
    throw new Error('useUI must be used within a UIProvider');
  }
  return context;
};
