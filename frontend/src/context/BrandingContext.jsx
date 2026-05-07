import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react';
import { api } from '../services/api';
import { useAuth } from './AuthContext';

const BrandingContext = createContext();

const DEFAULT_NAME = 'DMS Cloud';
const DEFAULT_COLOR = '#3b82f6';

function darken(hex, factor = 0.85) {
  const m = /^#([0-9a-f]{3}|[0-9a-f]{6})$/i.exec(hex);
  if (!m) return hex;
  let h = m[1];
  if (h.length === 3) h = h.split('').map((c) => c + c).join('');
  const r = parseInt(h.slice(0, 2), 16);
  const g = parseInt(h.slice(2, 4), 16);
  const b = parseInt(h.slice(4, 6), 16);
  const fmt = (v) => Math.max(0, Math.min(255, Math.round(v * factor))).toString(16).padStart(2, '0');
  return '#' + fmt(r) + fmt(g) + fmt(b);
}

function applyColor(color) {
  const c = color || DEFAULT_COLOR;
  document.documentElement.style.setProperty('--brand-primary', c);
  document.documentElement.style.setProperty('--brand-primary-hover', darken(c));
}

export const BrandingProvider = ({ children }) => {
  const { user } = useAuth();
  const [branding, setBranding] = useState({ brand_name: null, primary_color: null, has_logo: false });
  const [logoUrl, setLogoUrl] = useState(null);
  const lastLogoUrl = useRef(null);

  const refreshLogo = useCallback(async (hasLogo) => {
    if (lastLogoUrl.current) {
      URL.revokeObjectURL(lastLogoUrl.current);
      lastLogoUrl.current = null;
    }
    if (!hasLogo) {
      setLogoUrl(null);
      return;
    }
    try {
      const blob = await api.fetchBrandingLogoBlob();
      if (!blob) { setLogoUrl(null); return; }
      const url = URL.createObjectURL(blob);
      lastLogoUrl.current = url;
      setLogoUrl(url);
    } catch (err) {
      console.error('Failed to load branding logo', err);
      setLogoUrl(null);
    }
  }, []);

  const refresh = useCallback(async () => {
    if (!user) {
      setBranding({ brand_name: null, primary_color: null, has_logo: false });
      applyColor(null);
      await refreshLogo(false);
      return;
    }
    try {
      const data = await api.getMyBranding();
      setBranding(data);
      applyColor(data.primary_color);
      await refreshLogo(data.has_logo);
    } catch (err) {
      console.error('Failed to load branding', err);
      applyColor(null);
    }
  }, [user, refreshLogo]);

  useEffect(() => { refresh(); }, [refresh]);

  useEffect(() => () => {
    if (lastLogoUrl.current) URL.revokeObjectURL(lastLogoUrl.current);
  }, []);

  const displayName = branding.brand_name || DEFAULT_NAME;

  return (
    <BrandingContext.Provider value={{ branding, displayName, logoUrl, refresh }}>
      {children}
    </BrandingContext.Provider>
  );
};

export const useBranding = () => useContext(BrandingContext);
