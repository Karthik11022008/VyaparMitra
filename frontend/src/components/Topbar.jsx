import React from 'react'
import { IconCopilot, IconLedger, IconAlertTriangle } from './Icons'
import { ThemeSwitcher } from './ThemeSwitcher'

export const Topbar = ({
  activeTab,
  sessionId,
  onRunDemo,
  onOpenAgent,
  reconLoading,
  atRiskAmount
}) => {
  const titles = {
    overview: 'Command Center & Executive Intelligence',
    ingestion: 'File Ingestion & Ledger Validation',
    reconciliation: 'Audit Ledger & Variance Investigation',
    agent: 'AI Copilot & Dispute Draft Workspace',
    audit: 'Immutable Compliance Audit Trail',
    reports: 'Certified Reconciliation & Export Suite'
  }

  return (
    <header className="app-topbar">
      <div className="topbar-left">
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
            className="btn btn-primary-sm"
            onClick={onOpenAgent}
            title="Open AI Copilot and Dispute Resolution"
          >
            <IconCopilot size={14} className="inline mr-1" /> Run Copilot
          </button>
        </div>
      </div>
    </header>
  )
}
