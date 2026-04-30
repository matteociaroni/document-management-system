import React from 'react';
import { useUI } from '../context/UIContext';
import { Loader2 } from 'lucide-react';

const GlobalLoading = () => {
  const { loading } = useUI();

  if (!loading.isLoading) return null;

  return (
    <div className="loading-overlay">
      <div className="loading-content">
        <Loader2 className="spinner" size={48} />
        {loading.message && <div className="loading-message">{loading.message}</div>}
      </div>
    </div>
  );
};

export default GlobalLoading;
