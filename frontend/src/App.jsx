import { useState, useEffect, useMemo } from 'react'
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
  IconSearch,
  IconFilter,
  IconX,
  IconUsers,
  IconBuilding,
  IconHistory,
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

  // Phase 1 Search, Filtering & Sorting State
  const [searchQuery, setSearchQuery] = useState('')
  const [riskFilter, setRiskFilter] = useState('ALL') // ALL, AT_RISK, ZERO_RISK
  const [sortBy, setSortBy] = useState('atRisk') // atRisk, invoiceNumber, supplier, variance
  const [sortOrder, setSortOrder] = useState('desc') // desc, asc
  const [reconSubView, setReconSubView] = useState('invoices') // invoices, suppliers

  // Phase 1 Supplier Intelligence Workspace State
  const [supplierSearchQuery, setSupplierSearchQuery] = useState('')
  const [supplierSortBy, setSupplierSortBy] = useState('atRisk') // atRisk, invoices, name, missing
  const [supplierSortOrder, setSupplierSortOrder] = useState('desc') // desc, asc

  // Phase 1 Session History & Recovery State
  const [sessionHistory, setSessionHistory] = useState([])
  const [historyLoading, setHistoryLoading] = useState(false)

  // Slide-over Evidence Drawer
  const [inspectingItem, setInspectingItem] = useState(null)
  const [isSlideOverOpen, setIsSlideOverOpen] = useState(false)

  // AI Agent Copilot State (Batch & Lifecycle)
  const [agentPrompt, setAgentPrompt] = useState(
    'Reconcile recent purchase invoices against GSTR-2B, identify at-risk ITC discrepancies, and draft supplier dispute notices.'
  )
  const [agentLoading, setAgentLoading] = useState(false)
  const [agentError, setAgentError] = useState(null)
  const [agentResult, setAgentResult] = useState(null)
  const [agentActiveStage, setAgentActiveStage] = useState(0) // 0-6 for lifecycle

  // Phase 2 Conversational Investigation Assistant State
  const [copilotMode, setCopilotMode] = useState('investigate') // 'investigate' | 'workflow'
  const [chatQuestion, setChatQuestion] = useState('')
  const [chatLoading, setChatLoading] = useState(false)
  const [chatError, setChatError] = useState(null)
  const [expandedEvidence, setExpandedEvidence] = useState({})
  const [chatMessages, setChatMessages] = useState([
    {
      id: 'welcome-01',
      role: 'assistant',
      text: 'Welcome to VyaparMitra AI Investigation Assistant. I answer natural language audit queries grounded 100% strictly in your active reconciliation session data. All calculations and rule checks are performed by deterministic tools with zero math hallucinations.',
      data: null,
      timestamp: 'Active Session'
    }
  ])

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

  // Phase 1: Fetch Historical Reconciliation Sessions from SQLite
  const fetchSessionHistory = async () => {
    setHistoryLoading(true)
    try {
      const res = await fetch('http://localhost:8000/api/reconciliation/history')
      if (res.ok) {
        const data = await res.json()
        setSessionHistory(data.sessions || [])
      }
    } catch (e) {
      console.warn('Failed to fetch session history:', e)
    } finally {
      setHistoryLoading(false)
    }
  }

  // Phase 1: Restore a Historical Session from SQLite
  const loadHistoricalSession = async (targetSessionId) => {
    if (!targetSessionId) return
    setReconLoading(true)
    setReconError(null)
    try {
      const res = await fetch(`http://localhost:8000/api/reconciliation/session/${targetSessionId}/results`)
      if (!res.ok) throw new Error(`Could not restore session ${targetSessionId}`)
      const data = await res.json()
      setReconResult(data)
      setSessionId(targetSessionId)
      fetchAuditTrail(targetSessionId)
      fetchSessionHistory()
      setActiveTab('reconciliation')
    } catch (e) {
      setReconError(e.message)
    } finally {
      setReconLoading(false)
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
      fetchSessionHistory()
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
      fetchSessionHistory()
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

  // Phase 2: Run Conversational Investigation
  const runInvestigate = async (overridePrompt = null, invoiceContext = null) => {
    const q = (overridePrompt !== null ? overridePrompt : chatQuestion).trim()
    if (!q) return

    setChatLoading(true)
    setChatError(null)

    const nowTime = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    const userMsgId = 'user-' + Date.now()
    const asstMsgId = 'asst-' + (Date.now() + 1)

    // Add user message to conversation thread
    setChatMessages(prev => [
      ...prev,
      {
        id: userMsgId,
        role: 'user',
        text: q,
        timestamp: nowTime
      }
    ])
    setChatQuestion('')

    try {
      const payload = {
        question: q,
        session_id: sessionId || null,
        invoice_context: invoiceContext || null
      }
      const res = await fetch('http://localhost:8000/api/agent/investigate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Investigation failed')

      const asstTime = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      setChatMessages(prev => [
        ...prev,
        {
          id: asstMsgId,
          role: 'assistant',
          text: data.answer,
          data: data,
          timestamp: asstTime
        }
      ])

      // Auto-expand evidence for the fresh response
      setExpandedEvidence(prev => ({ ...prev, [asstMsgId]: true }))

      // If a draft notice is produced, automatically queue for HITL review
      if (data.draft_notice) {
        setDisputeNotices(prev => {
          if (prev.some(n => n.notice_id === data.draft_notice.notice_id)) return prev
          return [
            {
              ...data.draft_notice,
              approvalStatus: 'DRAFT_REVIEW_REQUIRED'
            },
            ...prev
          ]
        })
      }

      if (sessionId) fetchAuditTrail(sessionId)
    } catch (err) {
      setChatError(err.message)
      const errTime = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      setChatMessages(prev => [
        ...prev,
        {
          id: asstMsgId,
          role: 'assistant',
          text: `⚠️ Investigation query failed: ${err.message}. Please verify the reconciliation session status.`,
          isError: true,
          timestamp: errTime
        }
      ])
    } finally {
      setChatLoading(false)
    }
  }

  const toggleEvidence = (msgId) => {
    setExpandedEvidence(prev => ({
      ...prev,
      [msgId]: !prev[msgId]
    }))
  }

  const inspectFromEvidence = (evidenceItem) => {
    if (!evidenceItem) return
    const invNo = evidenceItem.invoice_number
    if (reconResult && reconResult.detailed_results && invNo) {
      const match = reconResult.detailed_results.find(r => {
        const pNum = r.purchase_invoice?.invoice_number || ''
        const bNum = r.matched_2b_invoice?.invoice_number || ''
        return pNum.toLowerCase() === invNo.toLowerCase() || bNum.toLowerCase() === invNo.toLowerCase()
      })
      if (match) {
        openInspector(match)
        return
      }
    }
    // Synthetic fallback for slideover inspection
    const synthItem = {
      status: evidenceItem.status || 'UNRECONCILED',
      confidence: 1.0,
      tax_difference: evidenceItem.tax_difference || 0,
      taxable_difference: 0,
      reason: evidenceItem.details || 'Identified during conversational investigation.',
      purchase_invoice: {
        invoice_number: evidenceItem.invoice_number,
        supplier_gstin: evidenceItem.supplier_gstin,
        supplier_name: evidenceItem.supplier_name || 'Vendor',
        invoice_date: '2026-04-15',
        total_tax: evidenceItem.purchase_tax || evidenceItem.tax_difference || 0,
        taxable_value: (Number(evidenceItem.purchase_tax || evidenceItem.tax_difference || 0) / 0.18).toFixed(2),
      },
      matched_2b_invoice: evidenceItem.gstr2b_tax ? {
        invoice_number: evidenceItem.invoice_number,
        supplier_gstin: evidenceItem.supplier_gstin,
        supplier_name: evidenceItem.supplier_name || 'Vendor',
        invoice_date: '2026-04-15',
        total_tax: evidenceItem.gstr2b_tax,
        taxable_value: (Number(evidenceItem.gstr2b_tax) / 0.18).toFixed(2),
      } : null
    }
    openInspector(synthItem)
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
    fetchSessionHistory()
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

  // Phase 1 Reset Controls
  const handleResetFilters = () => {
    setSearchQuery('')
    setFindingsFilter('ALL')
    setRiskFilter('ALL')
    setSortBy('atRisk')
    setSortOrder('desc')
  }

  // Phase 1: Filtered and Sorted Detailed Invoices (Instant Search + Match Status + Risk Type + Multi-column Sort)
  const filteredResults = useMemo(() => {
    let list = reconResult?.detailed_results || []

    // 1. Match status category filter (Chips)
    if (findingsFilter !== 'ALL') {
      list = list.filter(item => {
        if (findingsFilter === 'MATCHED') return item.status === 'EXACT_MATCH'
        if (findingsFilter === 'REVIEW') return item.status === 'FUZZY_MATCH_REQUIRES_REVIEW'
        if (findingsFilter === 'MISMATCH') return item.status === 'AMOUNT_MISMATCH'
        if (findingsFilter === 'MISSING') return item.status === 'MISSING_IN_2B' || item.status === 'MISSING_IN_PURCHASE_REGISTER'
        if (findingsFilter === 'INVALID') return item.status === 'INVALID_DATA' || item.status === 'DUPLICATE_CANDIDATE'
        return true
      })
    }

    // 2. Risk / Discrepancy Type filter
    if (riskFilter === 'AT_RISK') {
      list = list.filter(item => {
        const diff = Number(item.tax_difference || 0)
        const pVal = item.purchase_invoice ? Number(item.purchase_invoice.total_tax) : 0
        const atRisk = diff > 0 ? diff : (item.status === 'MISSING_IN_2B' || item.status === 'INVALID_DATA' || item.status === 'DUPLICATE_CANDIDATE' ? pVal : 0)
        return atRisk > 0
      })
    } else if (riskFilter === 'ZERO_RISK') {
      list = list.filter(item => {
        const diff = Number(item.tax_difference || 0)
        return diff === 0 && item.status === 'EXACT_MATCH'
      })
    }

    // 3. Instant Search: case-insensitive across invoice_number, supplier_gstin, supplier_name
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase().trim()
      list = list.filter(item => {
        const pInv = item.purchase_invoice
        const bInv = item.matched_2b_invoice
        const invNum = (pInv?.invoice_number || bInv?.invoice_number || '').toLowerCase()
        const gstin = (pInv?.supplier_gstin || bInv?.supplier_gstin || '').toLowerCase()
        const name = (pInv?.supplier_name || bInv?.supplier_name || '').toLowerCase()
        return invNum.includes(q) || gstin.includes(q) || name.includes(q)
      })
    }

    // 4. Sorting
    list = [...list].sort((a, b) => {
      let comp = 0
      const pA = a.purchase_invoice
      const bA = a.matched_2b_invoice
      const pB = b.purchase_invoice
      const bB = b.matched_2b_invoice

      if (sortBy === 'atRisk') {
        const diffA = Number(a.tax_difference || 0)
        const valA = pA ? Number(pA.total_tax) : 0
        const atRiskA = diffA > 0 ? diffA : (a.status === 'MISSING_IN_2B' || a.status === 'INVALID_DATA' || a.status === 'DUPLICATE_CANDIDATE' ? valA : 0)

        const diffB = Number(b.tax_difference || 0)
        const valB = pB ? Number(pB.total_tax) : 0
        const atRiskB = diffB > 0 ? diffB : (b.status === 'MISSING_IN_2B' || b.status === 'INVALID_DATA' || b.status === 'DUPLICATE_CANDIDATE' ? valB : 0)

        comp = atRiskA - atRiskB
      } else if (sortBy === 'invoiceNumber') {
        const numA = (pA?.invoice_number || bA?.invoice_number || '').toLowerCase()
        const numB = (pB?.invoice_number || bB?.invoice_number || '').toLowerCase()
        comp = numA.localeCompare(numB)
      } else if (sortBy === 'supplier') {
        const nameA = (pA?.supplier_name || bA?.supplier_name || pA?.supplier_gstin || bA?.supplier_gstin || '').toLowerCase()
        const nameB = (pB?.supplier_name || bB?.supplier_name || pB?.supplier_gstin || bB?.supplier_gstin || '').toLowerCase()
        comp = nameA.localeCompare(nameB)
      } else if (sortBy === 'variance') {
        comp = Number(a.tax_difference || 0) - Number(b.tax_difference || 0)
      }

      return sortOrder === 'desc' ? -comp : comp
    })

    return list
  }, [reconResult, findingsFilter, riskFilter, searchQuery, sortBy, sortOrder])

  // Phase 1: Filtered and Sorted Supplier Intelligence (100% Deterministic Arithmetic)
  const filteredSuppliers = useMemo(() => {
    let list = reconResult?.supplier_summaries || []

    if (supplierSearchQuery.trim()) {
      const q = supplierSearchQuery.toLowerCase().trim()
      list = list.filter(s =>
        (s.supplier_name || '').toLowerCase().includes(q) ||
        (s.supplier_gstin || '').toLowerCase().includes(q)
      )
    }

    list = [...list].sort((a, b) => {
      let comp = 0
      if (supplierSortBy === 'atRisk') {
        comp = Number(a.total_at_risk_itc || 0) - Number(b.total_at_risk_itc || 0)
      } else if (supplierSortBy === 'invoices') {
        comp = Number(a.total_invoices || 0) - Number(b.total_invoices || 0)
      } else if (supplierSortBy === 'name') {
        comp = (a.supplier_name || a.supplier_gstin).localeCompare(b.supplier_name || b.supplier_gstin)
      } else if (supplierSortBy === 'missing') {
        comp = Number(a.missing_in_2b || 0) - Number(b.missing_in_2b || 0)
      }
      return supplierSortOrder === 'desc' ? -comp : comp
    })

    return list
  }, [reconResult, supplierSearchQuery, supplierSortBy, supplierSortOrder])

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

              {/* Phase 1: Session History & Recovery Section */}
              {sessionHistory.length > 0 && (
                <div className="content-card">
                  <div className="content-card-header">
                    <div>
                      <h3 className="content-card-title">
                        <IconHistory size={16} className="text-accent inline mr-1.5" />
                        Reconciliation Session History & Recovery
                      </h3>
                      <p className="subtitle">
                        Historical reconciliation runs persisted in SQLite. Sessions are fully recoverable after application restart.
                      </p>
                    </div>
                    <button className="btn btn-secondary-sm" onClick={fetchSessionHistory} disabled={historyLoading}>
                      <IconRefresh size={12} className="mr-1" /> {historyLoading ? 'Refreshing...' : 'Refresh History'}
                    </button>
                  </div>

                  <div className="session-history-grid">
                    {sessionHistory.slice(0, 6).map((s) => {
                      const isActive = s.session_id === sessionId
                      const dateFormatted = s.created_at ? new Date(s.created_at).toLocaleString('en-IN') : '-'
                      let summaryData = null
                      try {
                        summaryData = s.summary_json ? JSON.parse(s.summary_json) : null
                      } catch (e) {}

                      return (
                        <div key={s.session_id} className={`session-history-card ${isActive ? 'active' : ''}`}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.4rem' }}>
                            <strong className="mono" style={{ fontSize: '0.8rem' }}>{s.session_id}</strong>
                            <span className={`status-badge ${s.status === 'RECONCILED' ? 'badge-EXACT_MATCH' : 'badge-AMOUNT_MISMATCH'}`}>
                              {s.status}
                            </span>
                          </div>
                          <div className="text-muted" style={{ fontSize: '0.72rem', marginBottom: '0.4rem' }}>
                            Created: {dateFormatted}
                          </div>
                          <div style={{ fontSize: '0.75rem', marginBottom: '0.65rem' }}>
                            Records: <strong>{s.purchase_row_count}</strong> Books / <strong>{s.gstr2b_row_count}</strong> 2B
                            {summaryData?.total_at_risk_itc && Number(summaryData.total_at_risk_itc) > 0 && (
                              <div style={{ color: 'var(--status-danger)', fontWeight: '600', marginTop: '0.2rem' }}>
                                At-Risk ITC: ₹{Number(summaryData.total_at_risk_itc).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                              </div>
                            )}
                          </div>
                          <button
                            className="btn btn-secondary-sm"
                            onClick={() => loadHistoricalSession(s.session_id)}
                            disabled={reconLoading || isActive}
                            style={{ alignSelf: 'flex-start' }}
                          >
                            {isActive ? 'Active Session' : 'Restore Session'}
                          </button>
                        </div>
                      )
                    })}
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
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', flexWrap: 'wrap' }}>
                    <div className="subview-tabs">
                      <button
                        type="button"
                        className={`subview-tab ${reconSubView === 'invoices' ? 'active' : ''}`}
                        onClick={() => setReconSubView('invoices')}
                      >
                        <IconLedger size={13} />
                        <span>Invoices Ledger ({filteredResults.length})</span>
                      </button>
                      <button
                        type="button"
                        className={`subview-tab ${reconSubView === 'suppliers' ? 'active' : ''}`}
                        onClick={() => setReconSubView('suppliers')}
                      >
                        <IconUsers size={13} />
                        <span>Supplier Summary ({filteredSuppliers.length})</span>
                      </button>
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
                </div>

                {reconSubView === 'invoices' ? (
                  <>
                    {/* Phase 1 Powerful Search & Filter Controls */}
                    <div className="recon-controls-bar">
                      <div className="fintech-search-container">
                        <IconSearch size={14} className="text-muted flex-shrink-0" />
                        <input
                          type="text"
                          className="fintech-search-input"
                          placeholder="Search invoice #, supplier GSTIN, or name..."
                          value={searchQuery}
                          onChange={(e) => setSearchQuery(e.target.value)}
                        />
                        {searchQuery && (
                          <button
                            type="button"
                            onClick={() => setSearchQuery('')}
                            style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}
                            title="Clear search"
                          >
                            <IconX size={14} className="text-muted" />
                          </button>
                        )}
                      </div>

                      <select
                        className="fintech-select"
                        value={riskFilter}
                        onChange={(e) => setRiskFilter(e.target.value)}
                        title="Filter by risk category"
                      >
                        <option value="ALL">All Risk Levels</option>
                        <option value="AT_RISK">At-Risk ITC Only</option>
                        <option value="ZERO_RISK">Zero Risk / Matched</option>
                      </select>

                      <select
                        className="fintech-select"
                        value={`${sortBy}-${sortOrder}`}
                        onChange={(e) => {
                          const [b, o] = e.target.value.split('-')
                          setSortBy(b)
                          setSortOrder(o)
                        }}
                        title="Sort invoices"
                      >
                        <option value="atRisk-desc">Sort: Highest At-Risk ITC</option>
                        <option value="atRisk-asc">Sort: Lowest At-Risk ITC</option>
                        <option value="invoiceNumber-asc">Sort: Invoice # (A-Z)</option>
                        <option value="invoiceNumber-desc">Sort: Invoice # (Z-A)</option>
                        <option value="supplier-asc">Sort: Supplier Name (A-Z)</option>
                        <option value="variance-desc">Sort: Tax Variance (High-Low)</option>
                      </select>

                      {(searchQuery || findingsFilter !== 'ALL' || riskFilter !== 'ALL' || sortBy !== 'atRisk' || sortOrder !== 'desc') && (
                        <button className="btn btn-secondary-sm" onClick={handleResetFilters} title="Reset all search and filter controls">
                          <IconRefresh size={12} className="mr-1" /> Reset Filters
                        </button>
                      )}
                    </div>

                    {/* Filter Category Chips */}
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
                        Showing {filteredResults.length} of {reconResult?.detailed_results?.length || 0} record(s)
                      </span>
                    </div>

                    {/* Detailed Invoices Ledger Table */}
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
                              <td colSpan="9" style={{ textAlign: 'center', padding: '2.5rem', color: 'var(--text-muted)' }}>
                                No invoice records found matching your active filter criteria.
                                <div style={{ marginTop: '0.5rem' }}>
                                  <button className="btn btn-secondary-sm" onClick={handleResetFilters}>
                                    Clear Filters
                                  </button>
                                </div>
                              </td>
                            </tr>
                          ) : (
                            filteredResults.map((item, idx) => {
                              const pInv = item.purchase_invoice
                              const bInv = item.matched_2b_invoice
                              const pVal = pInv ? Number(pInv.total_tax) : 0
                              const bVal = bInv ? Number(bInv.total_tax) : 0
                              const diff = Number(item.tax_difference || 0)
                              const atRisk = diff > 0 ? diff : (item.status === 'MISSING_IN_2B' || item.status === 'INVALID_DATA' || item.status === 'DUPLICATE_CANDIDATE' ? pVal : 0)

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
                                  <td className="mono" style={{ color: atRisk > 0 ? 'var(--status-danger)' : 'inherit', fontWeight: 'bold' }}>
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
                  </>
                ) : (
                  <>
                    {/* Supplier Intelligence Summary Subview */}
                    <div className="data-table-container">
                      <table className="fintech-table">
                        <thead>
                          <tr>
                            <th>Supplier Name & GSTIN</th>
                            <th>Total Invoices</th>
                            <th>Exact Matches</th>
                            <th>Fuzzy Review</th>
                            <th>Amount Mismatch</th>
                            <th>Missing in 2B</th>
                            <th>Total At-Risk ITC</th>
                            <th>Actions</th>
                          </tr>
                        </thead>
                        <tbody>
                          {filteredSuppliers.length === 0 ? (
                            <tr>
                              <td colSpan="8" style={{ textAlign: 'center', padding: '2.5rem', color: 'var(--text-muted)' }}>
                                No supplier records available. Run or restore reconciliation first.
                              </td>
                            </tr>
                          ) : (
                            filteredSuppliers.map((s) => {
                              const atRisk = Number(s.total_at_risk_itc || 0)
                              return (
                                <tr key={s.supplier_gstin}>
                                  <td>
                                    <div><strong>{s.supplier_name || 'Counterparty Vendor'}</strong></div>
                                    <code className="mono text-muted" style={{ fontSize: '0.72rem' }}>{s.supplier_gstin}</code>
                                  </td>
                                  <td className="mono font-semibold">{s.total_invoices}</td>
                                  <td><span className="status-badge badge-EXACT_MATCH">{s.exact_matches}</span></td>
                                  <td>{s.fuzzy_matches > 0 ? <span className="status-badge badge-FUZZY_MATCH_REQUIRES_REVIEW">{s.fuzzy_matches}</span> : <span className="text-muted">-</span>}</td>
                                  <td>{s.amount_mismatches > 0 ? <span className="status-badge badge-AMOUNT_MISMATCH">{s.amount_mismatches}</span> : <span className="text-muted">-</span>}</td>
                                  <td>{s.missing_in_2b > 0 ? <span className="status-badge badge-MISSING_IN_2B">{s.missing_in_2b}</span> : <span className="text-muted">-</span>}</td>
                                  <td className="mono" style={{ color: atRisk > 0 ? 'var(--status-danger)' : 'inherit', fontWeight: 'bold' }}>
                                    ₹{atRisk.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                                  </td>
                                  <td>
                                    <div style={{ display: 'flex', gap: '0.35rem' }}>
                                      <button
                                        className="btn btn-secondary-sm"
                                        onClick={() => {
                                          setSearchQuery(s.supplier_gstin)
                                          setReconSubView('invoices')
                                        }}
                                        title="Inspect all invoices for this supplier"
                                      >
                                        <IconEye size={12} className="mr-1" /> Invoices
                                      </button>
                                      <button
                                        className="btn btn-secondary-sm"
                                        onClick={() => {
                                          setAgentPrompt(`Investigate tax discrepancies and prepare formal supplier dispute notice for ${s.supplier_name || s.supplier_gstin} (GSTIN: ${s.supplier_gstin}) with Rs. ${s.total_at_risk_itc} at-risk ITC under Section 16(2)(aa).`)
                                          setActiveTab('agent')
                                        }}
                                        title="Draft notice with Copilot"
                                      >
                                        <IconCopilot size={12} className="mr-1" /> Notice
                                      </button>
                                    </div>
                                  </td>
                                </tr>
                              )
                            })
                          )}
                        </tbody>
                      </table>
                    </div>
                  </>
                )}
              </div>
            </div>
          )}

          {/* TAB: DEDICATED SUPPLIER INTELLIGENCE WORKSPACE */}
          {activeTab === 'suppliers' && (
            <div className="suppliers-workspace">
              {/* Executive Metrics for Suppliers */}
              <div className="kpi-grid">
                <div className="kpi-card">
                  <div className="kpi-header">
                    <span className="kpi-label">Total Suppliers</span>
                    <IconUsers size={16} className="text-accent flex-shrink-0" />
                  </div>
                  <div className="kpi-value">{filteredSuppliers.length}</div>
                  <div className="kpi-sub">Audited Counterparty Entities</div>
                </div>

                <div className="kpi-card kpi-card-danger">
                  <div className="kpi-header">
                    <span className="kpi-label">Non-Compliant Vendors</span>
                    <IconAlertTriangle size={16} className="text-danger flex-shrink-0" />
                  </div>
                  <div className="kpi-value text-danger">
                    {filteredSuppliers.filter(s => Number(s.total_at_risk_itc) > 0 || s.missing_in_2b > 0).length}
                  </div>
                  <div className="kpi-sub">Vendors with Blocked or At-Risk ITC</div>
                </div>

                <div className="kpi-card">
                  <div className="kpi-header">
                    <span className="kpi-label">Missing 2B Invoices</span>
                    <IconReports size={16} className="text-muted flex-shrink-0" />
                  </div>
                  <div className="kpi-value">
                    {filteredSuppliers.reduce((acc, s) => acc + s.missing_in_2b, 0)}
                  </div>
                  <div className="kpi-sub">Unreflected in GSTR-2B Statement</div>
                </div>

                <div className="kpi-card kpi-card-danger">
                  <div className="kpi-header">
                    <span className="kpi-label">Total At-Risk ITC</span>
                    <IconAlertTriangle size={16} className="text-danger flex-shrink-0" />
                  </div>
                  <div className="kpi-value text-danger">
                    ₹{filteredSuppliers.reduce((acc, s) => acc + Number(s.total_at_risk_itc), 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                  </div>
                  <div className="kpi-sub">Subject to DRC-01B & Section 50</div>
                </div>
              </div>

              {/* Supplier Intelligence Card */}
              <div className="content-card">
                <div className="content-card-header">
                  <div>
                    <h2 className="content-card-title">
                      <IconUsers size={16} className="text-accent inline mr-1.5" />
                      Supplier Intelligence & Counterparty Risk
                    </h2>
                    <p className="subtitle">
                      Deterministic aggregation of GSTIN-level compliance, filing status, and blocked Input Tax Credit.
                    </p>
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

                {/* Controls Bar for Suppliers */}
                <div className="recon-controls-bar">
                  <div className="fintech-search-container">
                    <IconSearch size={14} className="text-muted flex-shrink-0" />
                    <input
                      type="text"
                      className="fintech-search-input"
                      placeholder="Search vendor by name or GSTIN..."
                      value={supplierSearchQuery}
                      onChange={(e) => setSupplierSearchQuery(e.target.value)}
                    />
                    {supplierSearchQuery && (
                      <button
                        type="button"
                        onClick={() => setSupplierSearchQuery('')}
                        style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}
                      >
                        <IconX size={14} className="text-muted" />
                      </button>
                    )}
                  </div>

                  <select
                    className="fintech-select"
                    value={`${supplierSortBy}-${supplierSortOrder}`}
                    onChange={(e) => {
                      const [b, o] = e.target.value.split('-')
                      setSupplierSortBy(b)
                      setSupplierSortOrder(o)
                    }}
                  >
                    <option value="atRisk-desc">Sort: Highest At-Risk ITC</option>
                    <option value="invoices-desc">Sort: Most Invoices</option>
                    <option value="missing-desc">Sort: Most Missing in 2B</option>
                    <option value="name-asc">Sort: Supplier Name (A-Z)</option>
                  </select>

                  {supplierSearchQuery && (
                    <button className="btn btn-secondary-sm" onClick={() => setSupplierSearchQuery('')}>
                      <IconRefresh size={12} className="mr-1" /> Clear Search
                    </button>
                  )}

                  <span className="text-muted mono" style={{ fontSize: '0.72rem', marginLeft: 'auto' }}>
                    Showing {filteredSuppliers.length} supplier(s)
                  </span>
                </div>

                {/* Supplier Table */}
                <div className="data-table-container">
                  <table className="fintech-table">
                    <thead>
                      <tr>
                        <th>Supplier Details</th>
                        <th>Total Invoices</th>
                        <th>Exact Matches</th>
                        <th>Fuzzy Review</th>
                        <th>Amount Mismatches</th>
                        <th>Missing in 2B</th>
                        <th>At-Risk ITC</th>
                        <th>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredSuppliers.length === 0 ? (
                        <tr>
                          <td colSpan="8" style={{ textAlign: 'center', padding: '2.5rem', color: 'var(--text-muted)' }}>
                            No supplier records found. Run or restore reconciliation to generate supplier intelligence.
                          </td>
                        </tr>
                      ) : (
                        filteredSuppliers.map((s) => {
                          const atRisk = Number(s.total_at_risk_itc || 0)
                          return (
                            <tr key={s.supplier_gstin}>
                              <td>
                                <div><strong>{s.supplier_name || 'Vendor Entity'}</strong></div>
                                <code className="mono text-muted" style={{ fontSize: '0.72rem' }}>{s.supplier_gstin}</code>
                              </td>
                              <td className="mono font-semibold">{s.total_invoices}</td>
                              <td><span className="status-badge badge-EXACT_MATCH">{s.exact_matches}</span></td>
                              <td>{s.fuzzy_matches > 0 ? <span className="status-badge badge-FUZZY_MATCH_REQUIRES_REVIEW">{s.fuzzy_matches}</span> : <span className="text-muted">-</span>}</td>
                              <td>{s.amount_mismatches > 0 ? <span className="status-badge badge-AMOUNT_MISMATCH">{s.amount_mismatches}</span> : <span className="text-muted">-</span>}</td>
                              <td>{s.missing_in_2b > 0 ? <span className="status-badge badge-MISSING_IN_2B">{s.missing_in_2b}</span> : <span className="text-muted">-</span>}</td>
                              <td className="mono" style={{ color: atRisk > 0 ? 'var(--status-danger)' : 'inherit', fontWeight: 'bold' }}>
                                ₹{atRisk.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                              </td>
                              <td>
                                <div style={{ display: 'flex', gap: '0.35rem' }}>
                                  <button
                                    className="btn btn-secondary-sm"
                                    onClick={() => {
                                      setSearchQuery(s.supplier_gstin)
                                      setReconSubView('invoices')
                                      setActiveTab('reconciliation')
                                    }}
                                    title="View invoices for this supplier"
                                  >
                                    <IconEye size={12} className="mr-1" /> View Invoices
                                  </button>
                                  <button
                                    className="btn btn-primary-sm"
                                    onClick={() => {
                                      setAgentPrompt(`Investigate tax discrepancies and prepare formal supplier dispute notice for ${s.supplier_name || s.supplier_gstin} (GSTIN: ${s.supplier_gstin}) with Rs. ${s.total_at_risk_itc} at-risk ITC under Section 16(2)(aa).`)
                                      setActiveTab('agent')
                                    }}
                                    title="Draft vendor dispute notice"
                                  >
                                    <IconCopilot size={12} className="mr-1" /> Notice
                                  </button>
                                </div>
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
              {/* Copilot Mode Switcher Tabs */}
              <div className="copilot-mode-tabs">
                <button
                  type="button"
                  className={`mode-tab-btn ${copilotMode === 'investigate' ? 'active' : ''}`}
                  onClick={() => setCopilotMode('investigate')}
                >
                  <IconCopilot size={14} className="mr-1.5 text-accent" />
                  Conversational Investigation Assistant
                </button>
                <button
                  type="button"
                  className={`mode-tab-btn ${copilotMode === 'workflow' ? 'active' : ''}`}
                  onClick={() => setCopilotMode('workflow')}
                >
                  <IconLedger size={14} className="mr-1.5" />
                  Batch Diagnostic Workflow (6-Stage)
                </button>
              </div>

              {/* MODE 1: Conversational Investigation Assistant */}
              {copilotMode === 'investigate' && (
                <div className="content-card">
                  <div className="content-card-header">
                    <div>
                      <h2 className="content-card-title">
                        <IconCopilot size={16} className="text-accent inline mr-1.5" />
                        Conversational Investigation Assistant
                      </h2>
                      <p className="subtitle">
                        Ask natural language questions grounded 100% strictly in active session reconciliation data. Zero LLM math hallucinations.
                      </p>
                    </div>
                    {sessionId && (
                      <span className="session-indicator-pill">
                        Session: <code className="mono">{sessionId}</code>
                      </span>
                    )}
                  </div>

                  {/* Chat Conversation Stream */}
                  <div className="chat-thread-container">
                    {chatMessages.map((msg) => (
                      <div key={msg.id} className={`chat-message-row ${msg.role}`}>
                        {msg.role === 'user' ? (
                          <div className="chat-bubble user">
                            <div className="chat-header-row">
                              <span className="chat-author">You</span>
                              <span className="chat-timestamp">{msg.timestamp}</span>
                            </div>
                            <div className="chat-answer-text" style={{ marginBottom: 0 }}>
                              {msg.text}
                            </div>
                          </div>
                        ) : (
                          <div className={`chat-bubble assistant ${msg.isError ? 'error' : ''}`}>
                            <div className="chat-header-row">
                              <div className="chat-author">
                                <IconCopilot size={14} className="text-accent" />
                                <span>VyaparMitra AI Investigator</span>
                              </div>
                              <div style={{ display: 'flex', gap: '0.4rem', alignItems: 'center' }}>
                                {msg.data?.intent && (
                                  <span className="chat-intent-pill">{msg.data.intent}</span>
                                )}
                                <span className="chat-timestamp">{msg.timestamp}</span>
                              </div>
                            </div>

                            <div className="chat-answer-text">
                              {msg.text}
                            </div>

                            {/* Collapsible Evidence & Tools Executed Drawer */}
                            {msg.data && (
                              <div className="chat-evidence-box">
                                <div
                                  className="evidence-header-toggle"
                                  onClick={() => toggleEvidence(msg.id)}
                                >
                                  <div className="evidence-title-group">
                                    <IconCheckCircle size={14} className="text-success" />
                                    <span>
                                      Evidence & Tools Executed ({msg.data.tools_used?.length || 0} tools, {msg.data.evidence?.length || 0} records)
                                    </span>
                                  </div>
                                  <button
                                    type="button"
                                    className="btn-chip"
                                    style={{ fontSize: '0.7rem', padding: '0.15rem 0.5rem' }}
                                  >
                                    {expandedEvidence[msg.id] ? 'Hide Evidence ▲' : 'View Evidence ▼'}
                                  </button>
                                </div>

                                {/* Tools Executed Badge Row */}
                                <div className="tools-badge-row" style={{ marginTop: '0.5rem', marginBottom: '0.35rem' }}>
                                  <span className="label" style={{ fontSize: '0.68rem' }}>Deterministic Tools:</span>
                                  {msg.data.tools_used && msg.data.tools_used.map((tool, idx) => (
                                    <span key={idx} className="tool-tag" style={{ fontSize: '0.68rem', padding: '0.15rem 0.4rem' }}>{tool}</span>
                                  ))}
                                </div>

                                {/* Expandable Evidence Table */}
                                {expandedEvidence[msg.id] && msg.data.evidence && msg.data.evidence.length > 0 && (
                                  <div className="evidence-table-wrap">
                                    <table className="evidence-mini-table">
                                      <thead>
                                        <tr>
                                          <th>Item / Invoice</th>
                                          <th>Supplier</th>
                                          <th>GSTIN</th>
                                          <th>Purchase Tax</th>
                                          <th>GSTR-2B Tax</th>
                                          <th>Variance / Risk</th>
                                          <th>Status</th>
                                          <th>Statutory Citation</th>
                                          <th>Action</th>
                                        </tr>
                                      </thead>
                                      <tbody>
                                        {msg.data.evidence.map((ev, eIdx) => {
                                          const pTax = ev.purchase_tax !== null && ev.purchase_tax !== undefined ? Number(ev.purchase_tax) : null
                                          const bTax = ev.gstr2b_tax !== null && ev.gstr2b_tax !== undefined ? Number(ev.gstr2b_tax) : null
                                          const diff = ev.tax_difference !== null && ev.tax_difference !== undefined ? Number(ev.tax_difference) : null

                                          return (
                                            <tr key={eIdx}>
                                              <td><strong className="mono">{ev.invoice_number || '-'}</strong></td>
                                              <td>{ev.supplier_name || 'Vendor'}</td>
                                              <td><code className="mono">{ev.supplier_gstin || '-'}</code></td>
                                              <td className="mono">{pTax !== null ? `₹${pTax.toLocaleString('en-IN', { minimumFractionDigits: 2 })}` : '-'}</td>
                                              <td className="mono">{bTax !== null ? `₹${bTax.toLocaleString('en-IN', { minimumFractionDigits: 2 })}` : '-'}</td>
                                              <td className="mono" style={{ color: diff && diff > 0 ? 'var(--status-danger)' : 'inherit', fontWeight: 'bold' }}>
                                                {diff !== null ? `₹${diff.toLocaleString('en-IN', { minimumFractionDigits: 2 })}` : '-'}
                                              </td>
                                              <td><span className={`status-badge badge-${ev.status}`}>{ev.status}</span></td>
                                              <td><span className="tool-tag" style={{ fontSize: '0.65rem' }}>{ev.statutory_rule || 'Sec 16(2)(aa)'}</span></td>
                                              <td>
                                                <button
                                                  className="btn btn-secondary-sm"
                                                  style={{ padding: '0.2rem 0.5rem', fontSize: '0.7rem' }}
                                                  onClick={() => inspectFromEvidence(ev)}
                                                >
                                                  <IconEye size={11} className="inline mr-1" /> Inspect
                                                </button>
                                              </td>
                                            </tr>
                                          )
                                        })}
                                      </tbody>
                                    </table>
                                  </div>
                                )}
                              </div>
                            )}

                            {/* Inline Draft Dispute Notice Card (HITL Guardrail) */}
                            {msg.data?.draft_notice && (
                              <div className="notice-workspace-card" style={{ marginTop: '0.75rem', borderColor: 'var(--accent)' }}>
                                <div className="notice-top-row">
                                  <div>
                                    <div className="notice-supplier-name">
                                      Dispute Notice: {msg.data.draft_notice.supplier_reference}
                                    </div>
                                    <div className="notice-sub-meta">
                                      <span>Invoice: <code className="mono">{msg.data.draft_notice.invoice_reference}</code></span>
                                      <span> • </span>
                                      <span>At-Risk ITC: <strong className="mono" style={{ color: 'var(--status-danger)' }}>₹{Number(msg.data.draft_notice.verified_amount).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</strong></span>
                                    </div>
                                  </div>
                                  <span className="status-badge badge-DRAFT_REVIEW_REQUIRED">
                                    DRAFT — REQUIRES HUMAN REVIEW
                                  </span>
                                </div>
                                <div className="notice-provisions" style={{ marginBottom: '0.45rem' }}>
                                  <span className="text-muted" style={{ fontSize: '0.72rem' }}>Governing Rule: </span>
                                  <span className="tool-tag">{msg.data.draft_notice.applicable_statutory_reference}</span>
                                </div>
                                <pre className="notice-text-preview">{msg.data.draft_notice.notice_body}</pre>
                                <div className="notice-action-bar">
                                  <button
                                    className="btn btn-secondary-sm"
                                    onClick={() => handleStartEdit(msg.data.draft_notice)}
                                  >
                                    Edit Notice
                                  </button>
                                  <button
                                    className="btn btn-primary-sm"
                                    style={{ background: 'var(--status-success)', color: '#fff' }}
                                    onClick={() => handleApproveNotice(msg.data.draft_notice.notice_id)}
                                  >
                                    Approve Notice
                                  </button>
                                  <button
                                    className="btn btn-secondary-sm"
                                    style={{ borderColor: 'rgba(239, 68, 68, 0.4)', color: 'var(--status-danger)' }}
                                    onClick={() => handleRejectNotice(msg.data.draft_notice.notice_id)}
                                  >
                                    Reject Notice
                                  </button>
                                </div>
                              </div>
                            )}

                            {/* Recommended Action Box */}
                            {msg.data?.suggested_action && (
                              <div className="chat-suggested-action">
                                <IconAlertCircle size={14} className="text-warning flex-shrink-0" />
                                <span><strong>Recommendation:</strong> {msg.data.suggested_action}</span>
                              </div>
                            )}

                            {/* Statutory Legal Disclaimer */}
                            <div className="chat-disclaimer">
                              {msg.data?.disclaimer || "VyaparMitra is an accounting and reconciliation assistance system. It does not constitute statutory legal advice. All supplier communications require human review."}
                            </div>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>

                  {/* Interactive Composer Box */}
                  <div className="chat-composer-box">
                    <div className="quick-prompts-tray">
                      <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', fontWeight: 600 }}>Suggested Questions:</span>
                      <button
                        type="button"
                        className="quick-prompt-chip"
                        onClick={() => runInvestigate("Why is my ITC at risk?")}
                        disabled={chatLoading}
                      >
                        ⚖️ Why is my ITC at risk?
                      </button>
                      <button
                        type="button"
                        className="quick-prompt-chip"
                        onClick={() => runInvestigate("Show me all invoices missing from GSTR-2B")}
                        disabled={chatLoading}
                      >
                        📄 Missing in GSTR-2B
                      </button>
                      <button
                        type="button"
                        className="quick-prompt-chip"
                        onClick={() => runInvestigate("Which suppliers have the most discrepancies?")}
                        disabled={chatLoading}
                      >
                        🏢 Supplier Discrepancies
                      </button>
                      <button
                        type="button"
                        className="quick-prompt-chip"
                        onClick={() => runInvestigate("What is the tax difference between books and 2B?")}
                        disabled={chatLoading}
                      >
                        🔍 Tax Variance
                      </button>
                      <button
                        type="button"
                        className="quick-prompt-chip"
                        onClick={() => runInvestigate("Explain Section 16(2)(aa) statutory rule")}
                        disabled={chatLoading}
                      >
                        📜 Sec 16(2)(aa) Rule
                      </button>
                      <button
                        type="button"
                        className="quick-prompt-chip"
                        onClick={() => runInvestigate("What is our potential Section 50 interest exposure?")}
                        disabled={chatLoading}
                      >
                        ⏳ Sec 50 Interest Exposure
                      </button>
                      <button
                        type="button"
                        className="quick-prompt-chip"
                        onClick={() => runInvestigate("Draft dispute notices for delinquent suppliers")}
                        disabled={chatLoading}
                      >
                        📝 Draft Supplier Notices
                      </button>
                    </div>

                    <div className="chat-input-row">
                      <input
                        type="text"
                        className="chat-input-field"
                        placeholder="Ask a question about this reconciliation session (e.g. 'Why was invoice VM-INV-2026-0419 flagged?')..."
                        value={chatQuestion}
                        onChange={(e) => setChatQuestion(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' && !e.shiftKey) {
                            e.preventDefault()
                            runInvestigate()
                          }
                        }}
                        disabled={chatLoading}
                      />
                      <button
                        className="btn btn-primary"
                        onClick={() => runInvestigate()}
                        disabled={chatLoading || !chatQuestion.trim()}
                        style={{ whiteSpace: 'nowrap' }}
                      >
                        <IconCopilot size={14} className="mr-1.5" />
                        {chatLoading ? 'Investigating...' : 'Ask Copilot'}
                      </button>
                      <button
                        className="btn btn-secondary"
                        onClick={() => setChatMessages([
                          {
                            id: 'welcome-reset',
                            role: 'assistant',
                            text: 'Conversation thread cleared. How can I assist your GST investigation?',
                            data: null,
                            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
                          }
                        ])}
                        style={{ padding: '0.55rem 0.8rem', fontSize: '0.78rem' }}
                        title="Clear conversation history"
                      >
                        Clear
                      </button>
                    </div>
                    {chatError && <div className="alert-error" style={{ margin: 0, padding: '0.5rem 0.75rem', fontSize: '0.78rem' }}>{chatError}</div>}
                  </div>
                </div>
              )}

              {/* MODE 2: Batch Diagnostic Workflow (Preserved 100% Backward Compatible) */}
              {copilotMode === 'workflow' && (
                <div className="content-card">
                  <div className="content-card-header">
                    <div>
                      <h2 className="content-card-title">
                        <IconLedger size={16} className="text-accent inline mr-1.5" />
                        Batch Diagnostic Workflow (6-Stage)
                      </h2>
                      <p className="subtitle">
                        Executes multi-stage autonomous batch audit: parsing tax periods, matching books against GSTR-2B, and synthesizing dispute communications.
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
              )}

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
