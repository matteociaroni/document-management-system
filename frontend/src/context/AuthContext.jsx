import { createContext, useState, useContext, useEffect } from 'react';
import { api } from '../services/api';

const AuthContext = createContext();

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadedUser = api.getCurrentUser();
    if (loadedUser) {
      setUser(loadedUser);
    }
    setLoading(false);
  }, []);

  const login = async (email, password) => {
    const u = await api.login(email, password);
    setUser(u);
  };

  const register = async (username, email, password) => {
    const u = await api.register(username, email, password);
    setUser(u);
  };

  const logout = () => {
    api.logout();
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, login, register, logout, loading }}>
      {!loading && children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => useContext(AuthContext);
