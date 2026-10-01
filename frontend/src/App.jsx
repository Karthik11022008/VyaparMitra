import { useState, useEffect } from 'react'
import './App.css'

function App() {
  const [health, setHealth] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const checkHealth = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch('http://localhost:8000/api/health')
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}: ${res.statusText}`)
      }
      const data = await res.json()
      setHealth(data)
    } catch (err) {
      setError(err.message || 'Unable to connect to backend service')
      setHealth(null)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    checkHealth()
  }, [])

  return (
    <div className="container">
      <header className="header">
        <div className="badge">BHARAT AGENTIC 2026</div>
        <h1>VyaparMitra <span className="hindi">(व्यापार मित्र)</span></h1>
        <p className="subtitle">Autonomous MSME GST Reconciliation & Dispute-Resolution Agent</p>
      </header>

      <main className="card">
        <h2>Phase 1: Foundation Status Dashboard</h2>

        <div className="status-grid">
          <div className="status-item">
            <span className="label">Service Name</span>
            <span className="value">{health ? health.service : 'VyaparMitra'}</span>
          </div>

          <div className="status-item">
            <span className="label">Target Phase</span>
            <span className="value">{health ? health.phase : 'phase-1'}</span>
          </div>

          <div className="status-item">
            <span className="label">Backend Status</span>
            <span className={`status-pill ${loading ? 'pending' : health ? 'online' : 'offline'}`}>
              {loading ? 'Checking...' : health ? `● ${health.status.toUpperCase()}` : '● OFFLINE'}
            </span>
          </div>
        </div>

        {error && (
          <div className="alert-error">
            <strong>Backend Unavailable:</strong> {error}
            <p className="hint">Ensure FastAPI backend is running at <code>http://localhost:8000</code></p>
          </div>
        )}

        {health && (
          <div className="alert-success">
            <strong>Connected:</strong> Full-stack foundation verified. Frontend (5173) ↔ Backend (8000) roundtrip operational.
          </div>
        )}

        <div className="actions">
          <button className="btn" onClick={checkHealth} disabled={loading}>
            {loading ? 'Refreshing...' : 'Re-check Backend Health'}
          </button>
        </div>
      </main>

      <footer className="footer">
        Phase 1 Full-Stack Verification • BHARAT AGENTIC 2026
      </footer>
    </div>
  )
}

export default App
