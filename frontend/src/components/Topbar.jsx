import React from 'react'
import { IconCopilot, IconLedger, IconAlertTriangle, IconMenu, IconArrowLeft } from './Icons'
import { ThemeSwitcher } from './ThemeSwitcher'

export const Topbar = ({
  activeTab,
  sessionId,
  onRunDemo,
  onOpenAgent,
  onOpenAskAssistant,
  reconLoading,
  atRiskAmount,
  onToggleSidebar,
  isSidebarCollapsed,
  onBack,
  canGoBack,
}) => {
  const titles = {
    overview: 'Command Center & Executive Intelligence',
    ingestion: 'File Ingestion & Ledger Validation',
    reconciliation: 'Audit Ledger & Variance Investigation',
    suppliers: 'Supplier Intelligence & Counterparty Risk',
    agent: 'AI Copilot & Dispute Draft Workspace',
    audit: 'Immutable Compliance Audit Trail',
    reports: 'Certified Reconciliation & Export Suite'
  }

  return (
    <header className="app-topbar">
      <div className="topbar-left">
        <button
          type="button"
          className="topbar-nav-btn topbar-menu-btn"
          onClick={onToggleSidebar}
          aria-label={isSidebarCollapsed ? "Show sidebar" : "Hide sidebar"}
          title={isSidebarCollapsed ? "Show sidebar" : "Hide sidebar"}
          aria-expanded={!isSidebarCollapsed}
        >
          <IconMenu size={16} />
        </button>

        <button
          type="button"
          className={`topbar-nav-btn topbar-back-btn ${!canGoBack ? 'disabled' : ''}`}
          onClick={onBack}
          disabled={!canGoBack}
          aria-label="Go back to previous workspace"
          title={canGoBack ? "Go back to previous workspace" : "At Command Center"}
        >
          <IconArrowLeft size={13} />
          <span>Back</span>
        </button>

        <div className="workspace-breadcrumb">
          <span className="crumb-root">VyaparMitra</span>
          <span className="crumb-sep">/</span>
          <span className="crumb-active">{titles[activeTab] || 'Workspace'}</span>
        </div>
      </div>

      <div className="topbar-right">
        {atRiskAmount > 0 && (
          <div className="statutory-risk-pill" title="Unreflected ITC subject to DRC-01B & Sec 50(1) interest">
            <IconAlertTriangle size={14} className="text-danger flex-shrink-0" />
            <span>At-Risk ITC: <strong>Rs. {atRiskAmount.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</strong></span>
          </div>
        )}

        {sessionId && (
          <div className="session-indicator-pill" title={`Session ID: ${sessionId}`}>
            <span className="dot"></span>
            <span>Session: <code>{sessionId.slice(0, 10)}</code></span>
          </div>
        )}

        <ThemeSwitcher />

        <div className="topbar-actions">
          <button
            className="btn btn-secondary-sm"
            onClick={onRunDemo}
            disabled={reconLoading}
            title="Load synthetic sample business dataset"
          >
            <IconLedger size={14} className="inline mr-1" /> Demo Data
          </button>
          <button
            className="btn btn-ask-assistant"
            onClick={onOpenAskAssistant}
            title="Ask VyaparMitra AI Assistant (Anytime slide-out)"
          >
            <IconCopilot size={14} className="inline mr-1 text-accent" />
            <span>Ask VyaparMitra</span>
          </button>
          <button
            className="btn btn-primary-sm"
            onClick={onOpenAgent}
            title="Open AI Copilot and Dispute Resolution"
          >
            <IconCopilot size={14} className="inline mr-1" /> Batch Notice
          </button>
        </div>
      </div>
    </header>
  )
}
