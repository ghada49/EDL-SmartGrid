import "leaflet/dist/leaflet.css"; 
import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './styles.css'
import './i18n'
import { AuthProvider } from './context/AuthContext'
import { BrowserRouter } from 'react-router-dom'


ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <App />
      </AuthProvider>
    </BrowserRouter>
  </React.StrictMode>
)
