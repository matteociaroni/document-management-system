import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { useAuth } from './context/AuthContext';
import AuthPage from './pages/AuthPage';
import DrivePage from './pages/DrivePage';
import AdminPage from './pages/AdminPage';

const ProtectedRoute = ({ children }) => {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  return children;
};

function App() {
  const { user } = useAuth();

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={user ? <Navigate to="/drive" replace /> : <AuthPage />} />
        <Route path="/drive" element={
          <ProtectedRoute>
            <DrivePage />
          </ProtectedRoute>
        } />
        <Route path="/admin" element={
          <ProtectedRoute>
            <AdminPage />
          </ProtectedRoute>
        } />
        <Route path="/" element={<Navigate to={user ? "/drive" : "/login"} replace />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
