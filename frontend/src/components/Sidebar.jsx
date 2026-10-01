import React from 'react'
import {
  IconOverview,
  IconUpload,
  IconLedger,
  IconCopilot,
  IconAudit,
  IconReports,
} from './Icons'

export const Sidebar = ({ activeTab, setActiveTab, health, sessionId }) => {
  const navItems = [
    { id: 'overview', label: 'Command Center', icon: IconOverview, badge: null },
    { id: 'ingestion', label: 'File Ingestion', icon: IconUpload, badge: null },
    { id: 'reconciliation', label: 'Reconciliation', icon: IconLedger, badge: null },
    { id: 'agent', label: 'AI Copilot', icon: IconCopilot, badge: 'Agentic' },
    { id: 'audit', label: 'Audit Trail', icon: IconAudit, badge: null },
    { id: 'reports', label: 'Reports & Export', icon: IconReports, badge: null },
  ]

  return (
    <aside className="app-sidebar">
      {/* Brand Header */}
      <div className="sidebar-brand">
        <div className="brand-logo-container">
          <div className="brand-icon">
            <span>VM</span>
          </div>
          <div className="brand-titles">
            <div className="brand-name">
              VyaparMitra <span className="brand-hindi">व्यापार मित्र</span>
            </div>
            <div className="brand-sub">AI GST RECONCILIATION</div>
          </div>
        </div>
        <div className="hackathon-tag">
          BHARAT AGENTIC 2026
        </div>
      </div>

      {/* Navigation List */}
      <nav className="sidebar-nav">
        <div className="nav-section-title">WORKSPACES</div>
        {navItems.map((item) => {
          const Icon = item.icon
          const isActive = activeTab === item.id
          return (
            <button
              key={item.id}
              className={`nav-item ${isActive ? 'nav-item-active' : ''}`}
              onClick={() => setActiveTab(item.id)}
            >
              <span className="nav-icon-wrapper">
                <Icon size={16} />
              </span>
              <span className="nav-label">{item.label}</span>
              {item.badge && (
                <span className="nav-badge-pill">{item.badge}</span>
              )}
            </button>
          )
        })}
      </nav>

      {/* Sidebar Footer: System Status */}
      <div className="sidebar-footer">
        <div className="system-status-card">
          <div className="status-row-top">
            <span className="status-indicator-dot online"></span>
            <span className="status-title">FastAPI Engine</span>
            <span className="status-phase-tag">{health?.phase || 'v2026.1'}</span>
          </div>
          <div className="status-details">
            <div className="detail-item">
              <span className="detail-label">Model:</span>
              <span className="detail-value text-accent">gemini-2.5-flash</span>
            </div>
            {sessionId && (
              <div className="detail-item">
                <span className="detail-label">Session:</span>
                <span className="detail-value mono text-muted">{sessionId.slice(0, 10)}...</span>
              </div>
            )}
          </div>
        </div>
        <div className="sidebar-disclaimer">
          Accounting assistant • Non-legal advice
        </div>
      </div>
    </aside>
  )
}
