import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import './index.css'
import { AuthProvider } from './context/AuthContext.jsx'
import { UIProvider } from './context/UIContext.jsx'
import { BrandingProvider } from './context/BrandingContext.jsx'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <UIProvider>
      <AuthProvider>
        <BrandingProvider>
          <App />
        </BrandingProvider>
      </AuthProvider>
    </UIProvider>
  </React.StrictMode>,
)
