import { useEffect, useState } from 'react';
import { api } from '../services/api';
import { useUI } from '../context/UIContext';
import { useBranding } from '../context/BrandingContext';
import { Upload, Trash2, Save, ImageOff } from 'lucide-react';
import './BrandingSettings.css';

const DEFAULT_COLOR = '#3b82f6';
const HEX_RE = /^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/;

export default function BrandingSettings() {
  const { branding, logoUrl, refresh } = useBranding();
  const { setLoading, addToast } = useUI();
  const [name, setName] = useState('');
  const [color, setColor] = useState(DEFAULT_COLOR);
  const [logoPreview, setLogoPreview] = useState(null);
  const [pendingLogoFile, setPendingLogoFile] = useState(null);

  useEffect(() => {
    setName(branding.brand_name || '');
    setColor(branding.primary_color || DEFAULT_COLOR);
    setLogoPreview(null);
    setPendingLogoFile(null);
  }, [branding.brand_name, branding.primary_color, branding.has_logo]);

  const handlePickLogo = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!file.type.startsWith('image/')) {
      addToast('Seleziona un file immagine', 'error');
      return;
    }
    if (file.size > 1_000_000) {
      addToast('Il logo deve essere inferiore a 1 MB', 'error');
      return;
    }
    setPendingLogoFile(file);
    const reader = new FileReader();
    reader.onload = () => setLogoPreview(reader.result);
    reader.readAsDataURL(file);
  };

  const handleSave = async () => {
    if (color && !HEX_RE.test(color)) {
      addToast('Colore non valido (formato atteso #rrggbb)', 'error');
      return;
    }
    setLoading(true, 'Salvataggio branding...');
    try {
      await api.updateBranding({ brand_name: name, primary_color: color });
      if (pendingLogoFile) {
        await api.uploadBrandingLogo(pendingLogoFile);
        setPendingLogoFile(null);
        setLogoPreview(null);
      }
      await refresh();
      addToast('Branding aggiornato', 'success');
    } catch (err) {
      addToast(`Errore: ${err.message}`, 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteLogo = async () => {
    setLoading(true, 'Rimozione logo...');
    try {
      await api.deleteBrandingLogo();
      await refresh();
      setPendingLogoFile(null);
      setLogoPreview(null);
      addToast('Logo rimosso', 'success');
    } catch (err) {
      addToast(`Errore: ${err.message}`, 'error');
    } finally {
      setLoading(false);
    }
  };

  const previewSrc = logoPreview || logoUrl;

  return (
    <div className="branding-settings">
      <div className="branding-row">
        <div className="branding-field">
          <label className="form-label">Nome workspace</label>
          <input
            type="text"
            className="form-input"
            placeholder="DMS Cloud"
            value={name}
            onChange={(e) => setName(e.target.value)}
            maxLength={100}
          />
          <p className="branding-hint">Sostituisce "DMS Cloud" nella sidebar.</p>
        </div>

        <div className="branding-field">
          <label className="form-label">Colore primario</label>
          <div className="branding-color-row">
            <input
              type="color"
              value={HEX_RE.test(color) ? color : DEFAULT_COLOR}
              onChange={(e) => setColor(e.target.value)}
              className="branding-color-picker"
              aria-label="Color picker"
            />
            <input
              type="text"
              className="form-input branding-color-text"
              value={color}
              onChange={(e) => setColor(e.target.value)}
              placeholder="#3b82f6"
            />
          </div>
          <p className="branding-hint">Usato per pulsanti, link e accenti dell'interfaccia.</p>
        </div>
      </div>

      <div className="branding-field branding-logo-field">
        <label className="form-label">Logo</label>
        <div className="branding-logo-row">
          <div className="branding-logo-preview">
            {previewSrc ? (
              <img src={previewSrc} alt="Logo preview" />
            ) : (
              <div className="branding-logo-empty"><ImageOff size={20} /> Nessun logo</div>
            )}
          </div>
          <div className="branding-logo-actions">
            <label className="btn-secondary branding-upload-btn">
              <Upload size={16} /> Scegli file
              <input
                type="file"
                accept="image/png,image/jpeg,image/svg+xml,image/webp,image/gif"
                onChange={handlePickLogo}
                style={{ display: 'none' }}
              />
            </label>
            {(branding.has_logo || logoPreview) && (
              <button type="button" className="btn-secondary branding-danger" onClick={handleDeleteLogo}>
                <Trash2 size={16} /> Rimuovi logo
              </button>
            )}
          </div>
        </div>
        <p className="branding-hint">PNG, JPEG, SVG o WebP. Max 1 MB. Verrà salvato al click su "Salva modifiche".</p>
      </div>

      <div className="branding-actions">
        <button type="button" className="btn-primary" onClick={handleSave}>
          <Save size={16} /> Salva modifiche
        </button>
      </div>
    </div>
  );
}
