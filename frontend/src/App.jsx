import { useState, useEffect } from 'react'
import './App.css'
import { Sidebar } from './components/Sidebar'
import { Topbar } from './components/Topbar'
import { EvidenceSlideOver } from './components/EvidenceSlideOver'
import {
  IconOverview,
  IconUpload,
  IconLedger,
  IconCopilot,
  IconAudit,
  IconReports,
  IconAlertTriangle,
  IconAlertCircle,
  IconCheck,
  IconCheckCircle,
  IconDownload,
  IconEye,
  IconArrowRight,
  IconRefresh,
} from './components/Icons'

function App() {
  const [activeTab, setActiveTabRaw] = useState('overview')
  const [tabHistory, setTabHistory] = useState(['overview'])
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(() => {
    if (typeof window !== 'undefined') {
      return window.innerWidth <= 768
    }
    return false
  })

  const setActiveTab = (tab) => {
    setActiveTabRaw(prev => {
      if (prev !== tab) {
        setTabHistory(h => {
          if (h.length > 0 && h[h.length - 1] === tab) return h
          return [...h.slice(-30), tab]
        })
      }
      return tab
    })
  }

  const handleBack = () => {
    if (tabHistory.length > 1) {
      const newHistory = [...tabHistory]
      newHistory.pop()
      const prevTab = newHistory[newHistory.length - 1]
      setTabHistory(newHistory)
      setActiveTabRaw(prevTab)
    } else if (activeTab !== 'overview') {
      setActiveTabRaw('overview')
      setTabHistory(['overview'])
    }
  }

  const canGoBack = tabHistory.length > 1 || activeTab !== 'overview'
  const toggleSidebar = () => setIsSidebarCollapsed(prev => !prev)

  const [health, setHealth] = useState(null)
  const [healthLoading, setHealthLoading] = useState(true)

  // Session & Ingestion State
  const [sessionId, setSessionId] = useState('')
  const [purchaseUpload, setPurchaseUpload] = useState(null)
  const [purchaseLoading, setPurchaseLoading] = useState(false)
  const [purchaseError, setPurchaseError] = useState(null)

  const [gstr2bUpload, setGstr2bUpload] = useState(null)
  const [gstr2bLoading, setGstr2bLoading] = useState(false)
  const [gstr2bError, setGstr2bError] = useState(null)

  // Reconciliation Execution & Results
  const [reconLoading, setReconLoading] = useState(false)
  const [reconError, setReconError] = useState(null)
  const [reconResult, setReconResult] = useState(null)
  const [findingsFilter, setFindingsFilter] = useState('ALL')

  // Slide-over Evidence Drawer
  const [inspectingItem, setInspectingItem] = useState(null)
  const [isSlideOverOpen, setIsSlideOverOpen] = useState(false)

  // AI Agent Copilot State
  const [agentPrompt, setAgentPrompt] = useState(
    'Reconcile recent purchase invoices against GSTR-2B, identify at-risk ITC discrepancies, and draft supplier dispute notices.'
  )
  const [agentLoading, setAgentLoading] = useState(false)
  const [agentError, setAgentError] = useState(null)
  const [agentResult, setAgentResult] = useState(null)
  const [agentActiveStage, setAgentActiveStage] = useState(0) // 0-6 for lifecycle

  // Dispute Notices & HITL Review
  const [disputeNotices, setDisputeNotices] = useState([])
  const [editingNoticeId, setEditingNoticeId] = useState(null)
  const [editedBody, setEditedBody] = useState('')

  // Audit Trail State
  const [auditEvents, setAuditEvents] = useState([])

  // Health Check
  const checkHealth = async () => {
    setHealthLoading(true)
    try {
      const res = await fetch('http://localhost:8000/api/health')
      if (res.ok) {
        const data = await res.json()
        setHealth(data)
      }
    } catch (e) {
      console.warn('Backend unavailable:', e)
    } finally {
      setHealthLoading(false)
    }
  }

  // Fetch Audit Trail from SQLite
  const fetchAuditTrail = async (sid) => {
    const id = sid || sessionId
    if (!id) return
    try {
      const res = await fetch(`http://localhost:8000/api/reconciliation/audit/${id}`)
      if (res.ok) {
        const data = await res.json()
        setAuditEvents(data.events || [])
      }
    } catch (e) {
      console.warn('Failed to load audit trail:', e)
    }
  }

  // Handle Purchase Register Upload
  const handlePurchaseUpload = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    setPurchaseLoading(true)
    setPurchaseError(null)

    const formData = new FormData()
    formData.append('file', file)
    if (sessionId) formData.append('session_id', sessionId)

    try {
      const res = await fetch('http://localhost:8000/api/reconciliation/upload/purchase-register', {
        method: 'POST',
        body: formData,
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || `Upload failed (HTTP ${res.status})`)
      setPurchaseUpload(data)
      setSessionId(data.session_id)
      fetchAuditTrail(data.session_id)
    } catch (err) {
      setPurchaseError(err.message)
      setPurchaseUpload(null)
    } finally {
      setPurchaseLoading(false)
    }
  }

  // Handle GSTR-2B Upload
  const handleGstr2bUpload = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    setGstr2bLoading(true)
    setGstr2bError(null)

    const formData = new FormData()
    formData.append('file', file)
    if (sessionId) formData.append('session_id', sessionId)

    try {
      const res = await fetch('http://localhost:8000/api/reconciliation/upload/gstr2b', {
        method: 'POST',
        body: formData,
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || `Upload failed (HTTP ${res.status})`)
      setGstr2bUpload(data)
      setSessionId(data.session_id)
      fetchAuditTrail(data.session_id)
    } catch (err) {
      setGstr2bError(err.message)
      setGstr2bUpload(null)
    } finally {
      setGstr2bLoading(false)
    }
  }

  // Run Deterministic Reconciliation
  const runReconciliation = async () => {
    if (!sessionId) return
    setReconLoading(true)
    setReconError(null)

    try {
      const res = await fetch('http://localhost:8000/api/reconciliation/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId })
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Reconciliation failed')
      setReconResult(data)
      fetchAuditTrail(sessionId)
      setActiveTab('reconciliation')
    } catch (err) {
      setReconError(err.message)
      setReconResult(null)
    } finally {
      setReconLoading(false)
    }
  }

  // Fallback: Run Demo Reconciliation
  const runDemoReconciliation = async () => {
    setReconLoading(true)
    setReconError(null)
    try {
      const res = await fetch('http://localhost:8000/api/reconciliation/demo', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Failed to run demo reconciliation')
      setReconResult(data)
      const sid = data.session_id || 'demo-session'
      setSessionId(sid)
      fetchAuditTrail(sid)
      setActiveTab('reconciliation')
    } catch (err) {
      setReconError(err.message)
      setReconResult(null)
    } finally {
      setReconLoading(false)
    }
  }

  // Run AI Agent Analysis
  const runAgentAnalysis = async () => {
    if (!agentPrompt.trim()) return
    setAgentLoading(true)
    setAgentError(null)
    setAgentActiveStage(1)

    const timer = setInterval(() => {
      setAgentActiveStage(prev => (prev < 6 ? prev + 1 : prev))
    }, 450)

    try {
      const payload = {
        request: agentPrompt,
        session_id: sessionId || null
      }
      const res = await fetch('http://localhost:8000/api/agent/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Agent execution failed')
      setAgentResult(data)
      setDisputeNotices(
        (data.actions || []).map(action => ({
          ...action,
          approvalStatus: 'DRAFT_REVIEW_REQUIRED'
        }))
      )
      setAgentActiveStage(6)
      if (sessionId) fetchAuditTrail(sessionId)
      setActiveTab('agent')
    } catch (err) {
      setAgentError(err.message)
      setAgentResult(null)
    } finally {
      clearInterval(timer)
      setAgentLoading(false)
    }
  }

  // HITL Notice Approval / Rejection
  const handleApproveNotice = async (noticeId) => {
    try {
      await fetch(`http://localhost:8000/api/agent/notice/${noticeId}/action`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId || 'global', action: 'APPROVE' })
      })
      setDisputeNotices(prev =>
        prev.map(n => n.notice_id === noticeId ? { ...n, approvalStatus: 'APPROVED' } : n)
      )
      if (sessionId) fetchAuditTrail(sessionId)
    } catch (e) {
      console.error('Failed to log notice approval:', e)
    }
  }

  const handleRejectNotice = async (noticeId) => {
    try {
      await fetch(`http://localhost:8000/api/agent/notice/${noticeId}/action`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId || 'global', action: 'REJECT' })
      })
      setDisputeNotices(prev =>
        prev.map(n => n.notice_id === noticeId ? { ...n, approvalStatus: 'REJECTED' } : n)
      )
      if (sessionId) fetchAuditTrail(sessionId)
    } catch (e) {
      console.error('Failed to log notice rejection:', e)
    }
  }

  const handleStartEdit = (notice) => {
    setEditingNoticeId(notice.notice_id)
    setEditedBody(notice.notice_body)
  }

  const handleSaveEdit = async (noticeId) => {
    try {
      await fetch(`http://localhost:8000/api/agent/notice/${noticeId}/action`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId || 'global', action: 'EDIT', updated_body: editedBody })
      })
      setDisputeNotices(prev =>
        prev.map(n => n.notice_id === noticeId ? { ...n, notice_body: editedBody, approvalStatus: 'DRAFT_REVIEW_REQUIRED' } : n)
      )
      setEditingNoticeId(null)
      if (sessionId) fetchAuditTrail(sessionId)
    } catch (e) {
      console.error('Failed to log notice edit:', e)
    }
  }

  // Open Slide-Over Evidence Inspector
  const openInspector = (item) => {
    setInspectingItem(item)
    setIsSlideOverOpen(true)
  }

  // Download Reports
  const downloadReport = (format) => {
    if (!sessionId) return
    window.open(`http://localhost:8000/api/reconciliation/export/${sessionId}/${format}`, '_blank')
  }

  useEffect(() => {
    checkHealth()
  }, [])

  // Metrics calculation
  const summary = reconResult?.summary
  const atRiskAmount = summary ? Number(summary.total_at_risk_itc) : 0
  const netVariance = summary ? Number(summary.total_difference) : 0
  const totalAudited = summary ? summary.total_purchase_invoices + summary.total_2b_invoices : 0
  const exactMatches = summary ? summary.exact_matches : 0
  const fuzzyMatches = summary ? summary.fuzzy_matches : 0
  const amountMismatches = summary ? summary.amount_mismatches : 0
  const missing2B = summary ? summary.missing_in_2b : 0
  const invalidData = summary ? (summary.invalid_records + summary.duplicate_candidates) : 0

  const matchRate = summary && summary.total_purchase_invoices > 0
    ? ((exactMatches / summary.total_purchase_invoices) * 100).toFixed(0)
    : 0

  // Filtered detailed results
  const filteredResults = (reconResult?.detailed_results || []).filter(item => {
    if (findingsFilter === 'ALL') return true
    if (findingsFilter === 'MATCHED') return item.status === 'EXACT_MATCH'
    if (findingsFilter === 'REVIEW') return item.status === 'FUZZY_MATCH_REQUIRES_REVIEW'
    if (findingsFilter === 'MISMATCH') return item.status === 'AMOUNT_MISMATCH'
    if (findingsFilter === 'MISSING') return item.status === 'MISSING_IN_2B' || item.status === 'MISSING_IN_PURCHASE_REGISTER'
    if (findingsFilter === 'INVALID') return item.status === 'INVALID_DATA' || item.status === 'DUPLICATE_CANDIDATE'
    return true
  })

  const canRunReconcile = Boolean(
    purchaseUpload?.validation_status === 'VALID' &&
    gstr2bUpload?.validation_status === 'VALID'
  )

  return (
    <div className={`app-shell ${isSidebarCollapsed ? 'sidebar-collapsed' : ''}`}>
      {/* Mobile Sidebar Backdrop */}
      {!isSidebarCollapsed && (
        <div
          className="sidebar-backdrop"
          onClick={() => setIsSidebarCollapsed(true)}
          aria-hidden="true"
        />
      )}

      {/* Sidebar Navigation */}
      <Sidebar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        health={health}
        sessionId={sessionId}
        onClose={() => setIsSidebarCollapsed(true)}
      />

      {/* Main Workspace View */}
      <main className="app-main">
        <Topbar
          activeTab={activeTab}
          sessionId={sessionId}
          onRunDemo={runDemoReconciliation}
          onOpenAgent={() => setActiveTab('agent')}
          reconLoading={reconLoading}
          atRiskAmount={atRiskAmount}
          onToggleSidebar={toggleSidebar}
          isSidebarCollapsed={isSidebarCollapsed}
          onBack={handleBack}
          canGoBack={canGoBack}
        />

        <div className="workspace-container">
          {/* Statutory Compliance Notice Banner */}
          <div className="statutory-banner">
            <IconAlertTriangle size={15} className="text-warning flex-shrink-0" />
            <div>
              <strong>Statutory Compliance Notice:</strong> VyaparMitra is an accounting and reconciliation assistance system.
              It does not constitute statutory legal advice. All supplier communications require human review and approval.
            </div>
          </div>

          {/* TAB 1: OVERVIEW & COMMAND CENTER */}
          {activeTab === 'overview' && (
            <div className="overview-workspace">
              {/* Executive Command Header */}
              <div className="hero-command-card">
                <div className="hero-header-row">
                  <div>
                    <h1 className="hero-title">
                      Command Center
                    </h1>
                    <p className="hero-subtitle">
                      GST reconciliation intelligence for the current workspace with zero LLM math.
                    </p>
                  </div>
                  <div className="topbar-actions">
                    <button
                      className="btn btn-primary"
                      onClick={() => setActiveTab('agent')}
                    >
                      <IconCopilot size={14} className="mr-1.5" /> Run Agent
                    </button>
                    <button
                      className="btn btn-secondary"
                      onClick={() => setActiveTab('ingestion')}
                    >
                      <IconUpload size={14} className="mr-1.5" /> Upload Files
                    </button>
                  </div>
                </div>

                {/* Copilot Natural Language Prompt Bar */}
                <div className="copilot-prompt-bar">
                  <textarea
                    className="prompt-textarea"
                    rows="2"
                    value={agentPrompt}
                    onChange={(e) => setAgentPrompt(e.target.value)}
                    placeholder="Ask the AI Copilot to audit invoices, detect missing 2B entries, or draft supplier dispute notices..."
                    disabled={agentLoading}
                  />
                  <div className="prompt-actions-row">
                    <div className="prompt-chips-group">
                      <button
                        type="button"
                        className="btn-chip"
                        onClick={() => setAgentPrompt("Reconcile recent purchase invoices against GSTR-2B, identify at-risk ITC discrepancies, and draft supplier dispute notices.")}
                      >
                        ⚡ Reconcile all invoices
                      </button>
                      <button
                        type="button"
                        className="btn-chip"
                        onClick={() => setAgentPrompt("Audit unreflected GSTR-2B invoices and calculate Section 50 interest risk.")}
                      >
                        ⚖️ Find ITC at risk
                      </button>
                      <button
                        type="button"
                        className="btn-chip"
                        onClick={() => setAgentPrompt("Investigate value and tax amount mismatches between books and GSTR-2B.")}
                      >
                        🔍 Investigate mismatches
                      </button>
                    </div>
                    <button
                      className="btn btn-primary"
                      onClick={runAgentAnalysis}
                      disabled={agentLoading || !agentPrompt.trim()}
                    >
                      <IconCopilot size={14} className="mr-1.5" />
                      {agentLoading ? 'Agent Reasoning...' : 'Instruct Copilot'}
                    </button>
                  </div>
                </div>
              </div>

              {/* KPI Metrics Dashboard Grid */}
              <div className="kpi-grid">
                <div className="kpi-card kpi-card-danger">
                  <div className="kpi-header">
                    <span className="kpi-label">At-Risk ITC</span>
                    <IconAlertTriangle size={16} className="text-danger flex-shrink-0" />
                  </div>
                  <div className="kpi-value text-danger">
                    ₹{atRiskAmount.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                  </div>
                  <div className="kpi-sub">
                    {missing2B} missing in 2B • {amountMismatches} value mismatches
                  </div>
                </div>

                <div className="kpi-card">
                  <div className="kpi-header">
                    <span className="kpi-label">Net ITC Variance</span>
                    <IconLedger size={16} className="text-accent flex-shrink-0" />
                  </div>
                  <div className="kpi-value">
                    ₹{netVariance.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                  </div>
                  <div className="kpi-sub">
                    Difference between Books & GSTR-2B
                  </div>
                </div>

                <div className="kpi-card">
                  <div className="kpi-header">
                    <span className="kpi-label">Records Audited</span>
                    <IconReports size={16} className="text-muted flex-shrink-0" />
                  </div>
                  <div className="kpi-value">{totalAudited}</div>
                  <div className="kpi-sub">
                    {summary?.total_purchase_invoices || 0} Purchase vs {summary?.total_2b_invoices || 0} GSTR-2B
                  </div>
                </div>

                <div className="kpi-card kpi-card-success">
                  <div className="kpi-header">
                    <span className="kpi-label">Exact Match Rate</span>
                    <IconCheck size={16} className="text-success flex-shrink-0" />
                  </div>
                  <div className="kpi-value text-success">
                    {matchRate}%
                  </div>
                  <div className="kpi-sub">
                    {exactMatches} compliant • {fuzzyMatches} format matches
                  </div>
                </div>
              </div>

              {/* Reconciliation Breakdown Progress Bar */}
              {summary ? (
                <div className="breakdown-bar-card">
                  <div className="breakdown-bar-header">
                    <span className="kpi-label">Reconciliation Intelligence Breakdown</span>
                    <span className="text-muted mono" style={{ fontSize: '0.72rem' }}>100% Deterministic Python Engine</span>
                  </div>

                  <div className="multi-progress-bar">
                    <div className="prog-segment prog-exact" style={{ width: `${(exactMatches / (totalAudited || 1)) * 100}%` }} title="Exact Matches" />
                    <div className="prog-segment prog-fuzzy" style={{ width: `${(fuzzyMatches / (totalAudited || 1)) * 100}%` }} title="Fuzzy Format Matches" />
                    <div className="prog-segment prog-mismatch" style={{ width: `${(amountMismatches / (totalAudited || 1)) * 100}%` }} title="Amount Mismatches" />
                    <div className="prog-segment prog-missing" style={{ width: `${(missing2B / (totalAudited || 1)) * 100}%` }} title="Missing in 2B" />
                    <div className="prog-segment prog-invalid" style={{ width: `${(invalidData / (totalAudited || 1)) * 100}%` }} title="Invalid Records" />
                  </div>

                  <div className="breakdown-legend">
                    <div className="legend-item"><span className="legend-dot" style={{ background: 'var(--status-success)' }} /> MATCHED ({exactMatches})</div>
                    <div className="legend-item"><span className="legend-dot" style={{ background: 'var(--accent)' }} /> FUZZY REVIEW ({fuzzyMatches})</div>
                    <div className="legend-item"><span className="legend-dot" style={{ background: 'var(--status-warning)' }} /> MISMATCH ({amountMismatches})</div>
                    <div className="legend-item"><span className="legend-dot" style={{ background: 'var(--status-danger)' }} /> MISSING IN 2B ({missing2B})</div>
                    <div className="legend-item"><span className="legend-dot" style={{ background: '#f43f5e' }} /> INVALID/DUPLICATE ({invalidData})</div>
                  </div>
                </div>
              ) : (
                <div className="content-card empty-state-box">
                  <IconLedger size={32} className="empty-state-icon" />
                  <h3 className="empty-state-title">No reconciliation workspace is active.</h3>
                  <p className="empty-state-desc">
                    Upload buyer purchase registers and GSTR-2B statements in File Ingestion, or load the verified demo dataset to inspect real-time reconciliation intelligence.
                  </p>
                  <div className="empty-state-actions">
                    <button className="btn btn-primary" onClick={() => setActiveTab('ingestion')}>
                      <IconUpload size={14} className="mr-1.5" /> Upload Files
                    </button>
                    <button className="btn btn-secondary" onClick={runDemoReconciliation} disabled={reconLoading}>
                      <IconLedger size={14} className="mr-1.5" /> Load Verified Demo Dataset
                    </button>
                  </div>
                </div>
              )}

              {/* Executive Briefing / Agent Findings Preview */}
              {agentResult && (
                <div className="content-card">
                  <div className="content-card-header">
                    <h3 className="content-card-title">
                      <IconCopilot size={16} className="text-accent inline mr-1.5" />
                      Executive Briefing & Discrepancy Findings
                    </h3>
                    <button className="btn btn-secondary-sm" onClick={() => setActiveTab('agent')}>
                      Open Dispute Center <IconArrowRight size={14} className="ml-1 inline" />
                    </button>
                  </div>
                  <p className="summary-text">{agentResult.summary}</p>

                  <div className="tools-badge-row" style={{ marginTop: '0.85rem' }}>
                    <span className="label">Registered Tools Dispatched:</span>
                    {agentResult.tools_used && agentResult.tools_used.map((tool, idx) => (
                      <span key={idx} className="tool-tag">{tool}</span>
                    ))}
                  </div>
                </div>
              )}

              {/* Action Items / Discrepancy Preview */}
              {reconResult && (
                <div className="content-card">
                  <div className="content-card-header">
                    <div>
                      <h3 className="content-card-title">Priority Audit Discrepancies</h3>
                      <p className="subtitle">Click any invoice row to inspect side-by-side evidence.</p>
                    </div>
                    <button className="btn btn-secondary-sm" onClick={() => setActiveTab('reconciliation')}>
                      View Full Audit Ledger ({reconResult.detailed_results.length})
                    </button>
                  </div>

                  <div className="data-table-container">
                    <table className="fintech-table">
                      <thead>
                        <tr>
                          <th>Status</th>
                          <th>Invoice</th>
                          <th>Supplier</th>
                          <th>GSTIN</th>
                          <th>Purchase Value</th>
                          <th>GSTR-2B Value</th>
                          <th>Variance</th>
                          <th>ITC at Risk</th>
                          <th>Action</th>
                        </tr>
                      </thead>
                      <tbody>
                        {reconResult.detailed_results.slice(0, 5).map((item, idx) => {
                          const pInv = item.purchase_invoice
                          const bInv = item.matched_2b_invoice
                          const pVal = pInv ? Number(pInv.total_tax) : 0
                          const bVal = bInv ? Number(bInv.total_tax) : 0
                          const diff = Number(item.tax_difference || 0)
                          const atRisk = diff > 0 ? diff : (item.status === 'MISSING_IN_2B' ? pVal : 0)

                          return (
                            <tr key={idx} onClick={() => openInspector(item)} style={{ cursor: 'pointer' }}>
                              <td><span className={`status-badge badge-${item.status}`}>{item.status}</span></td>
                              <td><strong className="mono">{pInv?.invoice_number || bInv?.invoice_number || '-'}</strong></td>
                              <td>{pInv?.supplier_name || bInv?.supplier_name || 'Vendor'}</td>
                              <td><code className="mono">{pInv?.supplier_gstin || bInv?.supplier_gstin || '-'}</code></td>
                              <td className="mono">{pInv ? `₹${pVal.toLocaleString('en-IN', { minimumFractionDigits: 2 })}` : '-'}</td>
                              <td className="mono">{bInv ? `₹${bVal.toLocaleString('en-IN', { minimumFractionDigits: 2 })}` : '-'}</td>
                              <td className="mono" style={{ color: diff > 0 ? 'var(--status-danger)' : 'inherit', fontWeight: 'bold' }}>
                                ₹{diff.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                              </td>
                              <td className="mono" style={{ color: atRisk > 0 ? 'var(--status-danger)' : 'inherit' }}>
                                ₹{atRisk.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                              </td>
                              <td>
                                <button className="btn btn-secondary-sm" onClick={(e) => { e.stopPropagation(); openInspector(item); }}>
                                  <IconEye size={13} className="inline mr-1" /> Inspect
                                </button>
                              </td>
                            </tr>
                          )
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* TAB 2: FILE INGESTION & DATASET WORKSPACE */}
          {activeTab === 'ingestion' && (
            <div className="ingestion-workspace">
              <div className="content-card">
                <div className="content-card-header">
                  <div>
                    <h2 className="content-card-title">File Ingestion</h2>
                    <p className="subtitle">Upload buyer Purchase Register and portal GSTR-2B files in CSV, XLSX, or JSON formats.</p>
                  </div>
                  {sessionId && (
                    <span className="session-indicator-pill">Session: <code>{sessionId}</code></span>
                  )}
                </div>

                <div className="ingestion-cards-grid">
                  {/* Step 1: Purchase Register */}
                  <div className="upload-zone-card">
                    <span className="upload-step-pill">STEP 1 • BUYER BOOKS</span>
                    <h3>Purchase Register</h3>
                    <p className="upload-desc">Internal accounting register from Tally, Zoho, SAP, or ERP (CSV or XLSX).</p>

                    <label className="drop-target">
                      <input
                        type="file"
                        accept=".csv, .xlsx"
                        onChange={handlePurchaseUpload}
                        disabled={purchaseLoading}
                      />
                      <IconUpload size={28} className="text-accent mx-auto mb-1.5" />
                      <div className="font-semibold text-accent" style={{ fontSize: '0.815rem' }}>
                        {purchaseLoading ? 'Uploading & Normalizing...' : 'Drop file / Browse Purchase Register'}
                      </div>
                      <div className="text-muted" style={{ fontSize: '0.72rem', marginTop: '0.2rem' }}>
                        Supports .csv, .xlsx (Max 10 MB)
                      </div>
                    </label>

                    {purchaseUpload && (
                      <div className="upload-file-status">
                        <div className="upload-status-top">
                          <span className="filename-tag">{purchaseUpload.filename}</span>
                          <span className={`status-badge ${purchaseUpload.validation_status === 'VALID' ? 'badge-EXACT_MATCH' : 'badge-INVALID_DATA'}`}>
                            {purchaseUpload.validation_status}
                          </span>
                        </div>
                        <div className="record-count">{purchaseUpload.row_count} records detected • {purchaseUpload.detected_format}</div>

                        {purchaseUpload.validation_errors.length > 0 && (
                          <div className="validation-warnings-box">
                            <strong>Validation Notices:</strong>
                            <ul>
                              {purchaseUpload.validation_errors.map((err, i) => (
                                <li key={i}>{err}</li>
                              ))}
                            </ul>
                          </div>
                        )}
                      </div>
                    )}
                    {purchaseError && <div className="alert-error">{purchaseError}</div>}
                  </div>

                  {/* Step 2: GSTR-2B Statement */}
                  <div className="upload-zone-card">
                    <span className="upload-step-pill">STEP 2 • GSTN PORTAL</span>
                    <h3>GSTR-2B Statement</h3>
                    <p className="upload-desc">Auto-drafted ITC statement downloaded from GST portal (CSV, JSON, or XLSX).</p>

                    <label className="drop-target">
                      <input
                        type="file"
                        accept=".csv, .json, .xlsx"
                        onChange={handleGstr2bUpload}
                        disabled={gstr2bLoading}
                      />
                      <IconUpload size={28} className="text-success mx-auto mb-1.5" />
                      <div className="font-semibold text-success" style={{ fontSize: '0.815rem' }}>
                        {gstr2bLoading ? 'Uploading & Normalizing...' : 'Drop file / Browse GSTR-2B Statement'}
                      </div>
                      <div className="text-muted" style={{ fontSize: '0.72rem', marginTop: '0.2rem' }}>
                        Supports .csv, .json (Portal Schema), .xlsx (Max 10 MB)
                      </div>
                    </label>

                    {gstr2bUpload && (
                      <div className="upload-file-status">
                        <div className="upload-status-top">
                          <span className="filename-tag">{gstr2bUpload.filename}</span>
                          <span className={`status-badge ${gstr2bUpload.validation_status === 'VALID' ? 'badge-EXACT_MATCH' : 'badge-INVALID_DATA'}`}>
                            {gstr2bUpload.validation_status}
                          </span>
                        </div>
                        <div className="record-count">{gstr2bUpload.row_count} records detected • {gstr2bUpload.detected_format}</div>

                        {gstr2bUpload.validation_errors.length > 0 && (
                          <div className="validation-warnings-box">
                            <strong>Validation Notices:</strong>
                            <ul>
                              {gstr2bUpload.validation_errors.map((err, i) => (
                                <li key={i}>{err}</li>
                              ))}
                            </ul>
                          </div>
                        )}
                      </div>
                    )}
                    {gstr2bError && <div className="alert-error">{gstr2bError}</div>}
                  </div>
                </div>

                {/* Previews */}
                {purchaseUpload?.preview_rows?.length > 0 && (
                  <div className="preview-table-box">
                    <h4>Purchase Register Preview (First 5 Rows)</h4>
                    <div className="data-table-container">
                      <table className="fintech-table">
                        <thead>
                          <tr>
                            <th>GSTIN</th>
                            <th>Invoice No</th>
                            <th>Date</th>
                            <th>Taxable</th>
                            <th>CGST</th>
                            <th>SGST</th>
                            <th>IGST</th>
                            <th>Total Tax</th>
                          </tr>
                        </thead>
                        <tbody>
                          {purchaseUpload.preview_rows.map((r, i) => (
                            <tr key={i}>
                              <td><code className="mono">{r.supplier_gstin}</code></td>
                              <td><strong className="mono">{r.invoice_number}</strong></td>
                              <td>{r.invoice_date || '-'}</td>
                              <td className="mono">₹{r.taxable_value}</td>
                              <td className="mono">₹{r.cgst}</td>
                              <td className="mono">₹{r.sgst}</td>
                              <td className="mono">₹{r.igst}</td>
                              <td className="mono" style={{ color: 'var(--accent)', fontWeight: 'bold' }}>₹{r.total_tax}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}

                {gstr2bUpload?.preview_rows?.length > 0 && (
                  <div className="preview-table-box" style={{ marginTop: '1rem' }}>
                    <h4>GSTR-2B Statement Preview (First 5 Rows)</h4>
                    <div className="data-table-container">
                      <table className="fintech-table">
                        <thead>
                          <tr>
                            <th>GSTIN</th>
                            <th>Invoice No</th>
                            <th>Date</th>
                            <th>Taxable</th>
                            <th>CGST</th>
                            <th>SGST</th>
                            <th>IGST</th>
                            <th>Total Tax</th>
                          </tr>
                        </thead>
                        <tbody>
                          {gstr2bUpload.preview_rows.map((r, i) => (
                            <tr key={i}>
                              <td><code className="mono">{r.supplier_gstin}</code></td>
                              <td><strong className="mono">{r.invoice_number}</strong></td>
                              <td>{r.invoice_date || '-'}</td>
                              <td className="mono">₹{r.taxable_value}</td>
                              <td className="mono">₹{r.cgst}</td>
                              <td className="mono">₹{r.sgst}</td>
                              <td className="mono">₹{r.igst}</td>
                              <td className="mono" style={{ color: 'var(--status-success)', fontWeight: 'bold' }}>₹{r.total_tax}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}

                {/* Step 3 Action Bar */}
                <div style={{ marginTop: '1.25rem', display: 'flex', gap: '0.6rem', flexWrap: 'wrap', alignItems: 'center' }}>
                  <button
                    className="btn btn-primary"
                    onClick={runReconciliation}
                    disabled={reconLoading || !canRunReconcile}
                  >
                    <IconLedger size={14} className="mr-1.5" />
                    {reconLoading ? 'Reconciling...' : 'Run Reconciliation'}
                  </button>
                  <button
                    className="btn btn-secondary"
                    onClick={runDemoReconciliation}
                    disabled={reconLoading}
                  >
                    Load Verified Sample Dataset
                  </button>
                  {!canRunReconcile && (
                    <span className="text-muted" style={{ fontSize: '0.75rem' }}>
                      Upload and validate both Purchase Register and GSTR-2B to enable reconciliation.
                    </span>
                  )}
                </div>

                {reconError && <div className="alert-error">{reconError}</div>}
              </div>
            </div>
          )}

          {/* TAB 3: RECONCILIATION & AUDIT LEDGER */}
          {activeTab === 'reconciliation' && (
            <div className="reconciliation-workspace">
              <div className="content-card">
                <div className="content-card-header">
                  <div>
                    <h2 className="content-card-title">Reconciliation Ledger</h2>
                    <p className="subtitle">Deterministic cross-examination of internal purchase books against GSTR-2B returns.</p>
                  </div>
                  <div className="topbar-actions">
                    <button className="btn btn-secondary-sm" onClick={() => downloadReport('csv')}>
                      <IconDownload size={13} className="mr-1" /> Export CSV
                    </button>
                    <button className="btn btn-secondary-sm" onClick={() => downloadReport('html')}>
                      <IconDownload size={13} className="mr-1" /> Certified HTML
                    </button>
                  </div>
                </div>

                {/* Filter Tabs */}
                <div className="filter-tabs-row">
                  <div className="filter-chips">
                    {[
                      { id: 'ALL', label: 'All Invoices' },
                      { id: 'MATCHED', label: 'Exact Matches' },
                      { id: 'REVIEW', label: 'Fuzzy Review' },
                      { id: 'MISMATCH', label: 'Amount Mismatch' },
                      { id: 'MISSING', label: 'Missing in 2B' },
                      { id: 'INVALID', label: 'Data Anomalies' },
                    ].map(tab => (
                      <button
                        key={tab.id}
                        className={`chip-tab ${findingsFilter === tab.id ? 'active' : ''}`}
                        onClick={() => setFindingsFilter(tab.id)}
                      >
                        {tab.label}
                      </button>
                    ))}
                  </div>
                  <span className="text-muted mono" style={{ fontSize: '0.72rem' }}>
                    Showing {filteredResults.length} record(s)
                  </span>
                </div>

                {/* Detailed Findings Table */}
                <div className="data-table-container">
                  <table className="fintech-table">
                    <thead>
                      <tr>
                        <th>Status</th>
                        <th>Invoice</th>
                        <th>Supplier</th>
                        <th>GSTIN</th>
                        <th>Purchase Value</th>
                        <th>GSTR-2B Value</th>
                        <th>Variance</th>
                        <th>ITC at Risk</th>
                        <th>Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredResults.length === 0 ? (
                        <tr>
                          <td colSpan="9" style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted)' }}>
                            No invoice records found for this category.
                          </td>
                        </tr>
                      ) : (
                        filteredResults.map((item, idx) => {
                          const pInv = item.purchase_invoice
                          const bInv = item.matched_2b_invoice
                          const pVal = pInv ? Number(pInv.total_tax) : 0
                          const bVal = bInv ? Number(bInv.total_tax) : 0
                          const diff = Number(item.tax_difference || 0)
                          const atRisk = diff > 0 ? diff : (item.status === 'MISSING_IN_2B' ? pVal : 0)

                          return (
                            <tr key={idx} onClick={() => openInspector(item)} style={{ cursor: 'pointer' }}>
                              <td><span className={`status-badge badge-${item.status}`}>{item.status}</span></td>
                              <td><strong className="mono">{pInv?.invoice_number || bInv?.invoice_number || '-'}</strong></td>
                              <td>{pInv?.supplier_name || bInv?.supplier_name || 'Vendor'}</td>
                              <td><code className="mono">{pInv?.supplier_gstin || bInv?.supplier_gstin || '-'}</code></td>
                              <td className="mono">{pInv ? `₹${pVal.toLocaleString('en-IN', { minimumFractionDigits: 2 })}` : '-'}</td>
                              <td className="mono">{bInv ? `₹${bVal.toLocaleString('en-IN', { minimumFractionDigits: 2 })}` : '-'}</td>
                              <td className="mono" style={{ color: diff > 0 ? 'var(--status-danger)' : 'inherit', fontWeight: 'bold' }}>
                                ₹{diff.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                              </td>
                              <td className="mono" style={{ color: atRisk > 0 ? 'var(--status-danger)' : 'inherit' }}>
                                ₹{atRisk.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                              </td>
                              <td>
                                <button className="btn btn-secondary-sm" onClick={(e) => { e.stopPropagation(); openInspector(item); }}>
                                  <IconEye size={13} className="inline mr-1" /> Inspect
                                </button>
                              </td>
                            </tr>
                          )
                        })
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

          {/* TAB 4: AI COPILOT & DISPUTE WORKSPACE */}
          {activeTab === 'agent' && (
            <div className="agent-workspace">
              {/* Agent Orchestrator Command Box */}
              <div className="content-card">
                <div className="content-card-header">
                  <div>
                    <h2 className="content-card-title">
                      <IconCopilot size={16} className="text-accent inline mr-1.5" />
                      AI Copilot
                    </h2>
                    <p className="subtitle">
                      Gemini orchestrates deterministic tools, evaluates CGST statutory provisions, and synthesizes reviewable vendor communications.
                    </p>
                  </div>
                </div>

                <div className="copilot-prompt-bar">
                  <textarea
                    className="prompt-textarea"
                    rows="3"
                    value={agentPrompt}
                    onChange={(e) => setAgentPrompt(e.target.value)}
                    placeholder="Enter natural language instructions for reconciliation, interest exposure, or vendor notices..."
                    disabled={agentLoading}
                  />
                  <div className="prompt-actions-row">
                    <div className="prompt-chips-group">
                      <button
                        type="button"
                        className="btn-chip"
                        onClick={() => setAgentPrompt("Reconcile recent purchase invoices against GSTR-2B, identify at-risk ITC discrepancies, and draft supplier dispute notices.")}
                      >
                        ⚡ Reconcile all invoices
                      </button>
                      <button
                        type="button"
                        className="btn-chip"
                        onClick={() => setAgentPrompt("Audit unreflected GSTR-2B invoices and calculate Section 50 interest risk.")}
                      >
                        ⚖️ Find ITC at risk
                      </button>
                      <button
                        type="button"
                        className="btn-chip"
                        onClick={() => setAgentPrompt("Investigate value and tax amount mismatches between books and GSTR-2B.")}
                      >
                        🔍 Investigate mismatches
                      </button>
                      <button
                        type="button"
                        className="btn-chip"
                        onClick={() => setAgentPrompt("Prepare draft supplier dispute notices for unreflected invoices.")}
                      >
                        📝 Prepare supplier notices
                      </button>
                      <button
                        type="button"
                        className="btn-chip"
                        onClick={() => setAgentPrompt("Check Section 50 interest exposure at 18% per annum.")}
                      >
                        ⏳ Check Section 50 exposure
                      </button>
                    </div>
                    <button
                      className="btn btn-primary"
                      onClick={runAgentAnalysis}
                      disabled={agentLoading || !agentPrompt.trim()}
                    >
                      <IconCopilot size={14} className="mr-1.5" />
                      {agentLoading ? 'Agent Orchestrating...' : 'Execute Agent Workflow'}
                    </button>
                  </div>
                </div>

                {/* Subtle Linear 6-Stage Execution Lifecycle */}
                <div className="agent-lifecycle-track">
                  {[
                    { step: 1, name: 'UNDERSTAND', desc: 'Parses tax period & business intent' },
                    { step: 2, name: 'ANALYZE', desc: 'Maps requirements to tool sequence' },
                    { step: 3, name: 'MATCH', desc: 'Runs deterministic Python engine' },
                    { step: 4, name: 'VERIFY', desc: 'Checks Luhn GSTIN & Decimal math' },
                    { step: 5, name: 'RISK', desc: 'Evaluates CGST Sec 16(2)(aa) & 50' },
                    { step: 6, name: 'ACTION', desc: 'Drafts human-reviewable notices' },
                  ].map((node) => {
                    const isNodeActive = agentActiveStage === node.step && agentLoading
                    const isNodeCompleted = agentActiveStage >= node.step
                    return (
                      <div
                        key={node.step}
                        className={`lifecycle-node ${isNodeActive ? 'active' : ''} ${isNodeCompleted ? 'completed' : ''}`}
                      >
                        <div className="node-step-tag">STAGE {node.step}</div>
                        <div className="node-name">{node.name}</div>
                        <div className="node-desc">{node.desc}</div>
                      </div>
                    )
                  })}
                </div>

                {agentError && <div className="alert-error">{agentError}</div>}
              </div>

              {/* Executive Briefing */}
              {agentResult && (
                <div className="content-card">
                  <div className="content-card-header">
                    <h3 className="content-card-title">Executive Briefing & Findings</h3>
                  </div>
                  <p className="summary-text">{agentResult.summary}</p>

                  <div className="tools-badge-row" style={{ marginTop: '0.85rem' }}>
                    <span className="label">Deterministic Tools Executed:</span>
                    {agentResult.tools_used && agentResult.tools_used.map((tool, idx) => (
                      <span key={idx} className="tool-tag">{tool}</span>
                    ))}
                  </div>
                </div>
              )}

              {/* Supplier Dispute Notices (Human-in-the-Loop) */}
              <div className="content-card">
                <div className="content-card-header">
                  <div>
                    <h3 className="content-card-title">Draft Supplier Dispute Notices</h3>
                    <p className="subtitle">Mandatory human-in-the-loop review. Approve or edit notices prior to dispatch.</p>
                  </div>
                  <span className="nav-badge-pill">HUMAN-IN-THE-LOOP REQUIRED</span>
                </div>

                {disputeNotices.length === 0 ? (
                  <div className="alert-success">No pending supplier disputes requiring action at this time.</div>
                ) : (
                  <div className="notices-list">
                    {disputeNotices.map((notice) => (
                      <div key={notice.notice_id} className="notice-workspace-card">
                        <div className="notice-top-row">
                          <div>
                            <div className="notice-supplier-name">{notice.supplier_reference}</div>
                            <div className="notice-sub-meta">
                              <span>Invoice: <code className="mono">{notice.invoice_reference}</code></span>
                              <span> • </span>
                              <span>At-Risk ITC: <strong className="mono" style={{ color: 'var(--status-danger)' }}>₹{Number(notice.verified_amount).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</strong></span>
                            </div>
                          </div>
                          <div>
                            <span className={`status-badge badge-${notice.approvalStatus}`}>
                              {notice.approvalStatus === 'APPROVED' && 'APPROVED FOR DISPATCH'}
                              {notice.approvalStatus === 'REJECTED' && 'REJECTED / ARCHIVED'}
                              {notice.approvalStatus === 'DRAFT_REVIEW_REQUIRED' && 'DRAFT — REQUIRES HUMAN REVIEW'}
                            </span>
                          </div>
                        </div>

                        <div className="notice-provisions" style={{ marginBottom: '0.65rem' }}>
                          <span className="text-muted" style={{ fontSize: '0.72rem' }}>Applicable Section: </span>
                          <span className="tool-tag">{notice.applicable_statutory_reference}</span>
                        </div>

                        {editingNoticeId === notice.notice_id ? (
                          <div>
                            <textarea
                              className="notice-textarea-editor"
                              rows="10"
                              value={editedBody}
                              onChange={(e) => setEditedBody(e.target.value)}
                            />
                            <div className="notice-action-bar">
                              <button
                                className="btn btn-primary"
                                onClick={() => handleSaveEdit(notice.notice_id)}
                              >
                                Save Changes
                              </button>
                              <button
                                className="btn btn-secondary"
                                onClick={() => setEditingNoticeId(null)}
                              >
                                Cancel
                              </button>
                            </div>
                          </div>
                        ) : (
                          <div>
                            <pre className="notice-text-preview">{notice.notice_body}</pre>
                            <div className="notice-action-bar">
                              <button
                                className="btn btn-secondary-sm"
                                onClick={() => handleStartEdit(notice)}
                              >
                                Edit Notice
                              </button>
                              <button
                                className="btn btn-primary-sm"
                                style={{ background: 'var(--status-success)', color: '#fff' }}
                                disabled={notice.approvalStatus === 'APPROVED'}
                                onClick={() => handleApproveNotice(notice.notice_id)}
                              >
                                Approve Notice
                              </button>
                              <button
                                className="btn btn-secondary-sm"
                                style={{ borderColor: 'rgba(239, 68, 68, 0.4)', color: 'var(--status-danger)' }}
                                disabled={notice.approvalStatus === 'REJECTED'}
                                onClick={() => handleRejectNotice(notice.notice_id)}
                              >
                                Reject Notice
                              </button>
                            </div>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* TAB 5: COMPLIANCE AUDIT TRAIL */}
          {activeTab === 'audit' && (
            <div className="audit-workspace">
              <div className="content-card">
                <div className="content-card-header">
                  <div>
                    <h2 className="content-card-title">Audit Trail</h2>
                    <p className="subtitle">Cryptographic and chronological logging of all ingestion, reconciliation, and agent actions in SQLite.</p>
                  </div>
                  {sessionId && (
                    <button className="btn btn-secondary-sm" onClick={() => fetchAuditTrail(sessionId)}>
                      <IconRefresh size={13} className="mr-1" /> Refresh Audit Trail
                    </button>
                  )}
                </div>

                {auditEvents.length === 0 ? (
                  <div className="text-muted" style={{ padding: '2rem 0', textAlign: 'center' }}>
                    No audit events recorded for current session yet. Ingest files or run reconciliation to generate audit records.
                  </div>
                ) : (
                  <div className="audit-timeline">
                    {auditEvents.map((evt) => (
                      <div key={evt.id} className="timeline-event-card">
                        <div className="timeline-dot" />
                        <div className="timeline-event-header">
                          <span className="timeline-event-type">{evt.event_type}</span>
                          <span className="timeline-event-time">
                            {new Date(evt.timestamp).toLocaleString()}
                          </span>
                        </div>
                        <p className="timeline-event-details">{evt.details}</p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* TAB 6: REPORTS & EXPORTS */}
          {activeTab === 'reports' && (
            <div className="reports-workspace">
              <div className="content-card">
                <div className="content-card-header">
                  <div>
                    <h2 className="content-card-title">Reports & Export</h2>
                    <p className="subtitle">Audit-ready document exports compliant with Indian GST statutory accounting requirements.</p>
                  </div>
                  {sessionId && reconResult && (
                    <span className="session-indicator-pill">Reconciliation complete • Session: <code>{sessionId}</code></span>
                  )}
                </div>

                {!reconResult ? (
                  <div className="recon-empty-export-card" style={{
                    background: 'var(--bg-surface-alt)',
                    border: '1px dashed var(--border-medium)',
                    borderRadius: '8px',
                    padding: '2.5rem 1.5rem',
                    textAlign: 'center',
                    marginBottom: '1.25rem'
                  }}>
                    <div style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      width: '42px',
                      height: '42px',
                      borderRadius: '50%',
                      background: 'var(--status-warning-bg)',
                      color: 'var(--status-warning)',
                      marginBottom: '0.85rem'
                    }}>
                      <IconAlertTriangle size={22} />
                    </div>
                    <h3 style={{ margin: '0 0 0.35rem 0', fontSize: '1.05rem', fontWeight: 600, color: 'var(--text-primary)' }}>
                      No completed reconciliation
                    </h3>
                    <p style={{ margin: '0 0 1.25rem 0', fontSize: '0.825rem', color: 'var(--text-secondary)' }}>
                      Run reconciliation to generate audit-ready reports
                    </p>
                    <button
                      className="btn btn-primary"
                      onClick={() => setActiveTab('reconciliation')}
                      style={{ display: 'inline-flex', alignItems: 'center', margin: '0 auto' }}
                    >
                      <IconArrowRight size={14} className="mr-1.5" /> Go to Reconciliation
                    </button>
                  </div>
                ) : (
                  <div className="recon-complete-banner" style={{
                    background: 'var(--bg-surface-alt)',
                    border: '1px solid var(--border-subtle)',
                    borderRadius: '8px',
                    padding: '1rem 1.25rem',
                    marginBottom: '1.25rem',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    flexWrap: 'wrap',
                    gap: '1rem'
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.85rem' }}>
                      <div style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        width: '36px',
                        height: '36px',
                        borderRadius: '50%',
                        background: 'var(--status-success-bg)',
                        color: 'var(--status-success)',
                        flexShrink: 0
                      }}>
                        <IconCheckCircle size={18} />
                      </div>
                      <div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.55rem', marginBottom: '0.2rem' }}>
                          <span style={{ fontWeight: 600, fontSize: '0.9rem', color: 'var(--text-primary)' }}>Reconciliation complete</span>
                          <span className="session-indicator-pill" style={{ margin: 0 }}>
                            Session: <code className="mono">{sessionId}</code>
                          </span>
                        </div>
                        <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                          Deterministic reconciliation verified across purchase register and GSTR-2B datasets.
                        </div>
                      </div>
                    </div>
                    <div style={{ display: 'flex', gap: '1.75rem', alignItems: 'center' }}>
                      <div style={{ textAlign: 'right' }}>
                        <span style={{ display: 'block', fontSize: '0.68rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>Records Reconciled</span>
                        <span style={{ fontWeight: 700, fontSize: '0.95rem', color: 'var(--text-primary)' }} className="mono">
                          {summary ? summary.total_purchase_invoices + summary.total_2b_invoices : 0}
                        </span>
                      </div>
                      <div style={{ textAlign: 'right' }}>
                        <span style={{ display: 'block', fontSize: '0.68rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>At-Risk ITC</span>
                        <span style={{ fontWeight: 700, fontSize: '0.95rem', color: 'var(--status-danger)' }} className="mono">
                          ₹{atRiskAmount.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                        </span>
                      </div>
                    </div>
                  </div>
                )}

                <div className="reports-grid">
                  {/* CSV Export Card */}
                  <div className="export-card">
                    <div>
                      <IconReports size={28} className="text-accent mb-2" />
                      <h3 className="export-card-title">Audit-Ready CSV Ledger</h3>
                      <p className="export-card-desc">
                        Complete discrepancy breakdown spreadsheet containing supplier GSTINs, normalized invoice numbers, taxable values, tax variances, and statutory citations.
                      </p>
                    </div>
                    <button
                      className="btn btn-primary"
                      onClick={() => downloadReport('csv')}
                      disabled={!reconResult || !sessionId}
                    >
                      <IconDownload size={14} className="mr-1.5" /> Download CSV Export
                    </button>
                  </div>

                  {/* HTML Report Card */}
                  <div className="export-card">
                    <div>
                      <IconAlertTriangle size={28} className="text-success mb-2" />
                      <h3 className="export-card-title">Certified HTML Audit Certificate</h3>
                      <p className="export-card-desc">
                        Standalone, styled audit document with executive summary metrics cards, statutory rule assessments, detailed discrepancy ledger, and legal disclaimers. Printable to PDF.
                      </p>
                    </div>
                    <button
                      className="btn btn-primary"
                      onClick={() => downloadReport('html')}
                      disabled={!reconResult || !sessionId}
                    >
                      <IconDownload size={14} className="mr-1.5" /> Download HTML Audit Report
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </main>

      {/* Side-Over Evidence Inspector Drawer */}
      <EvidenceSlideOver
        isOpen={isSlideOverOpen}
        onClose={() => setIsSlideOverOpen(false)}
        resultItem={inspectingItem}
        onDraftNotice={(item) => {
          setActiveTab('agent')
          setAgentPrompt(`Review discrepancy for invoice ${item.purchase_invoice?.invoice_number || item.matched_2b_invoice?.invoice_number} from supplier ${item.purchase_invoice?.supplier_gstin || item.matched_2b_invoice?.supplier_gstin} and draft a dispute communication.`)
        }}
      />
    </div>
  )
}

export default App
