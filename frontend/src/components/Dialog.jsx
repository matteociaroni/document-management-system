import { useState, useEffect, useRef } from 'react';
import { AlertTriangle, Trash2, Info, FolderPlus, X } from 'lucide-react';
import './Dialog.css';

/**
 * ConfirmDialog — Sostituisce window.confirm()
 *
 * Props:
 *  - isOpen: bool
 *  - title: string
 *  - message: string
 *  - variant: 'danger' | 'warning' | 'info'  (default 'danger')
 *  - confirmLabel: string (default 'Conferma')
 *  - cancelLabel:  string (default 'Annulla')
 *  - onConfirm: () => void
 *  - onCancel:  () => void
 */
export function ConfirmDialog({
  isOpen,
  title,
  message,
  variant = 'danger',
  confirmLabel = 'Conferma',
  cancelLabel = 'Annulla',
  onConfirm,
  onCancel,
}) {
  useEffect(() => {
    if (!isOpen) return;
    const handleKey = (e) => {
      if (e.key === 'Escape') onCancel?.();
      if (e.key === 'Enter') onConfirm?.();
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [isOpen, onConfirm, onCancel]);

  if (!isOpen) return null;

  const iconMap = {
    danger: <Trash2 size={18} />,
    warning: <AlertTriangle size={18} />,
    info: <Info size={18} />,
  };

  return (
    <div className="dialog-backdrop" onClick={(e) => { if (e.target === e.currentTarget) onCancel?.(); }}>
      <div className={`dialog-box ${variant === 'danger' ? 'is-danger' : ''}`} role="alertdialog" aria-modal="true" aria-labelledby="dialog-title">
        <div className="dialog-header">
          <span className={`dialog-icon ${variant}`}>
            {iconMap[variant]}
          </span>
          <span className="dialog-title" id="dialog-title">{title}</span>
        </div>
        <div className="dialog-body">
          {message && <p className="dialog-message">{message}</p>}
        </div>
        <div className="dialog-footer">
          <button className="dialog-btn dialog-btn-cancel" onClick={onCancel}>
            {cancelLabel}
          </button>
          <button
            className={`dialog-btn ${variant === 'danger' ? 'dialog-btn-danger' : 'dialog-btn-confirm'}`}
            onClick={onConfirm}
            autoFocus
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

/**
 * PromptDialog — Sostituisce window.prompt()
 *
 * Props:
 *  - isOpen: bool
 *  - title: string
 *  - message: string (opzionale)
 *  - inputLabel: string
 *  - placeholder: string
 *  - defaultValue: string
 *  - confirmLabel: string (default 'Crea')
 *  - cancelLabel:  string (default 'Annulla')
 *  - onConfirm: (value: string) => void
 *  - onCancel:  () => void
 */
export function PromptDialog({
  isOpen,
  title,
  message,
  inputLabel = 'Nome',
  placeholder = '',
  defaultValue = '',
  confirmLabel = 'Crea',
  cancelLabel = 'Annulla',
  onConfirm,
  onCancel,
}) {
  const [value, setValue] = useState(defaultValue);
  const inputRef = useRef(null);

  useEffect(() => {
    if (isOpen) {
      setValue(defaultValue);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [isOpen, defaultValue]);

  const handleConfirm = () => {
    if (value.trim()) onConfirm?.(value.trim());
  };

  const handleKey = (e) => {
    if (e.key === 'Enter') handleConfirm();
    if (e.key === 'Escape') onCancel?.();
  };

  if (!isOpen) return null;

  return (
    <div className="dialog-backdrop" onClick={(e) => { if (e.target === e.currentTarget) onCancel?.(); }}>
      <div className="dialog-box" role="dialog" aria-modal="true" aria-labelledby="prompt-dialog-title">
        <div className="dialog-header">
          <span className="dialog-icon info">
            <FolderPlus size={18} />
          </span>
          <span className="dialog-title" id="prompt-dialog-title">{title}</span>
        </div>
        <div className="dialog-body">
          {message && <p className="dialog-message">{message}</p>}
          <div className="dialog-input-wrapper">
            {inputLabel && <label className="dialog-input-label">{inputLabel}</label>}
            <input
              ref={inputRef}
              className="dialog-input"
              type="text"
              value={value}
              placeholder={placeholder}
              onChange={(e) => setValue(e.target.value)}
              onKeyDown={handleKey}
            />
          </div>
        </div>
        <div className="dialog-footer">
          <button className="dialog-btn dialog-btn-cancel" onClick={onCancel}>
            {cancelLabel}
          </button>
          <button
            className="dialog-btn dialog-btn-confirm"
            onClick={handleConfirm}
            disabled={!value.trim()}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
