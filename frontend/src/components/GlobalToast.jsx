import React from 'react';
import { useUI } from '../context/UIContext';
import { X, CheckCircle, AlertCircle, Info, Upload, XCircle, FolderUp } from 'lucide-react';

const GlobalToast = () => {
  const { toasts, removeToast, uploadTask, cancelUpload, dismissUploadTask } = useUI();

  return (
    <div className="toast-container">
      {/* Upload progress toast */}
      {uploadTask && (
        <div className={`toast toast-upload ${!uploadTask.active ? 'toast-upload-done' : ''}`}>
          <div className="toast-icon toast-upload-icon">
            <FolderUp size={20} className={uploadTask.active ? 'upload-spin' : ''} />
          </div>
          <div className="toast-upload-body">
            <div className="toast-upload-header">
              <span className="toast-upload-title">
                {uploadTask.active
                  ? 'Caricamento in corso...'
                  : uploadTask.errors?.length > 0
                    ? 'Caricamento parziale'
                    : 'Caricamento completato'}
              </span>
              {!uploadTask.indeterminate && (
                <span className="toast-upload-count">
                  {uploadTask.completed}/{uploadTask.total}
                </span>
              )}
            </div>
            {!uploadTask.indeterminate && (
              <div className="toast-upload-progress-bar">
                <div
                  className="toast-upload-progress-fill"
                  style={{ width: `${uploadTask.total > 0 ? (uploadTask.completed / uploadTask.total) * 100 : 0}%` }}
                />
              </div>
            )}
            {uploadTask.active && uploadTask.currentFile && (
              <div className="toast-upload-filename" title={uploadTask.currentFile}>
                {uploadTask.currentFile}
              </div>
            )}
            {!uploadTask.active && uploadTask.errors?.length > 0 && (
              <div className="toast-upload-filename toast-upload-errors">
                {uploadTask.errors.length} file non caricati
              </div>
            )}
          </div>
          {uploadTask.active ? (
            <button className="toast-upload-cancel" onClick={cancelUpload} title="Interrompi caricamento">
              <XCircle size={18} />
            </button>
          ) : (
            <button className="toast-close" onClick={dismissUploadTask}>
              <X size={16} />
            </button>
          )}
        </div>
      )}

      {/* Regular toasts */}
      {toasts.map((toast) => (
        <div key={toast.id} className={`toast toast-${toast.type}`}>
          <div className="toast-icon">
            {toast.type === 'success' && <CheckCircle size={20} />}
            {toast.type === 'error' && <AlertCircle size={20} />}
            {toast.type === 'info' && <Info size={20} />}
          </div>
          <div className="toast-message">{toast.message}</div>
          <button className="toast-close" onClick={() => removeToast(toast.id)}>
            <X size={16} />
          </button>
        </div>
      ))}
    </div>
  );
};

export default GlobalToast;
