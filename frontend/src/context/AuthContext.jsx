import { createContext, useState, useContext, useEffect, useCallback } from 'react';
import { api, isTokenExpired } from '../services/api';

const AuthContext = createContext();

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  const logout = useCallback(() => {
    api.logout();
    setUser(null);
  }, []);

  // On mount: load user only if the token is still valid
  useEffect(() => {
    const loadedUser = api.getCurrentUser();
    if (loadedUser && !isTokenExpired()) {
      setUser(loadedUser);
    } else if (loadedUser) {
      // Token exists but is expired — clean up
      api.logout();
    }
    setLoading(false);
  }, []);

  // Periodic check: auto-logout when the token expires mid-session
  useEffect(() => {
    if (!user) return;
    const interval = setInterval(() => {
      if (isTokenExpired()) {
        logout();
      }
    }, 60_000); // check every 60 seconds
    return () => clearInterval(interval);
  }, [user, logout]);

  const login = async (email, password) => {
    const u = await api.login(email, password);
    setUser(u);
  };

  const register = async (username, email, password) => {
    const u = await api.register(username, email, password);
    setUser(u);
  };

  return (
    <AuthContext.Provider value={{ user, login, register, logout, loading }}>
      {!loading && children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => useContext(AuthContext);
