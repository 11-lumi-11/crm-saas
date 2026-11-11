import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import './styles.css'

// Las sesiones de demostración solo funcionan con el servidor de desarrollo.
if (!import.meta.env.DEV && localStorage.getItem('crm-saas.sesion')?.includes('demo-local')) localStorage.removeItem('crm-saas.sesion')

ReactDOM.createRoot(document.getElementById('root')!).render(<React.StrictMode><BrowserRouter><App /></BrowserRouter></React.StrictMode>)
