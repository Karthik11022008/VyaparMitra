import React, { useState, useEffect } from 'react'
import {
  IconX,
  IconAlertTriangle,
  IconCheckCircle,
  IconEye,
  IconCopilot,
  IconRefresh,
  IconBuilding,
  IconHistory,
  IconAlertCircle,
} from './Icons'

export const SupplierDrillDownModal = ({
  isOpen,
  onClose,
  supplierGstin,
  sessionId,
  onInspectInvoice,
  onAskAboutSupplier,
  onDraftNotice,
}) => {
  const [profile, setProfile] = useState(null)
  const [history, setHistory] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [activeSubTab, setActiveSubTab] = useState('profile') // 'profile' | 'invoices' | 'history'

  useEffect(() => {
    if (!isOpen || !supplierGstin) {
      setProfile(null)
      setHistory(null)
      setError(null)
      return
    }

    let isMounted = true
    const fetchData = async () => {
      setLoading(true)
      setError(null)
      const sid = sessionId || 'demo-session'

      try {
        const [profRes, histRes] = await Promise.all([
          fetch(`http://localhost:8000/api/suppliers/${sid}/${supplierGstin}/profile`),
          fetch(`http://localhost:8000/api/suppliers/${sid}/${supplierGstin}/history`)
        ])

        if (!profRes.ok) throw new Error(`Failed to load profile for ${supplierGstin}`)
        const profData = await profRes.json()

        let histData = null
        if (histRes.ok) {
          histData = await histRes.json()
        }

        if (isMounted) {
          setProfile(profData)
          setHistory(histData)
        }
      } catch (err) {
        if (isMounted) setError(err.message)
      } finally {
        if (isMounted) setLoading(false)
      }
    }

    fetchData()

    return () => {
      isMounted = false
    }
  }, [isOpen, supplierGstin, sessionId])

  if (!isOpen) return null

  const getRiskColor = (score, category) => {
    if (category === 'CRITICAL' || score >= 75) return 'var(--status-danger)'
    if (category === 'HIGH' || score >= 50) return '#f59e0b'
    if (category === 'MEDIUM' || score >= 25) return '#eab308'
    return 'var(--status-success)'
  }

  const riskColor = getRiskColor(profile?.risk_score || 0, profile?.risk_category)

  return (
    <div className="drilldown-backdrop" onClick={onClose}>
      <div className="drilldown-drawer" onClick={(e) => e.stopPropagation()}>
        {/* Drawer Header */}
        <div className="drilldown-header">
          <div>
            <div className="drilldown-pretitle">
              <IconBuilding size={14} className="inline mr-1 text-accent" />
              <span>SUPPLIER COMPLIANCE INTELLIGENCE</span>
            </div>
            <h2 className="drilldown-title">{profile?.supplier_name || 'Counterparty Vendor'}</h2>
            <code className="drilldown-gstin mono">{supplierGstin}</code>
          </div>
          <button className="drilldown-close-btn" onClick={onClose} aria-label="Close supplier details">
            <IconX size={18} />
          </button>
        </div>

        {/* Content Body */}
        <div className="drilldown-body">
          {loading && (
            <div className="drilldown-loading">
              <IconRefresh size={22} className="spin text-accent" />
              <span>Computing deterministic supplier risk factors...</span>
            </div>
          )}

          {error && (
            <div className="drilldown-error">
              <IconAlertTriangle size={18} className="text-danger mr-2 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {profile && !loading && (
            <>
              {/* Risk Hero Banner */}
              <div
                className="supplier-risk-hero"
                style={{ borderLeft: `4px solid ${riskColor}` }}
              >
                <div className="risk-score-circle" style={{ borderColor: riskColor, color: riskColor }}>
                  <span className="risk-num">{profile.risk_score}</span>
                  <span className="risk-denom">/ 100</span>
                </div>
                <div className="risk-hero-info">
                  <div className="risk-category-badge" style={{ backgroundColor: `${riskColor}20`, color: riskColor }}>
                    {profile.risk_category} RISK LEVEL
                  </div>
                  <div className="risk-hero-exposure">
                    At-Risk Exposure: <strong>₹{Number(profile.at_risk_itc || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</strong>
                  </div>
                  <div className="risk-hero-meta text-muted">
                    {profile.total_invoices} invoice(s) evaluated • {profile.missing_in_2b} missing in 2B • {profile.tax_mismatches} tax mismatch(es)
                  </div>
                </div>
              </div>

              {/* Sub-tab Navigation */}
              <div className="drilldown-tabs">
                <button
                  className={`drilldown-tab ${activeSubTab === 'profile' ? 'active' : ''}`}
                  onClick={() => setActiveSubTab('profile')}
                >
                  Risk Breakdown & Signals
                </button>
                <button
                  className={`drilldown-tab ${activeSubTab === 'invoices' ? 'active' : ''}`}
                  onClick={() => setActiveSubTab('invoices')}
                >
                  Affected Invoices ({profile.affected_invoices?.length || 0})
                </button>
                <button
                  className={`drilldown-tab ${activeSubTab === 'history' ? 'active' : ''}`}
                  onClick={() => setActiveSubTab('history')}
                >
                  Multi-Session Trends
                </button>
              </div>

              {/* TAB 1: Profile & Signals */}
              {activeSubTab === 'profile' && (
                <div className="drilldown-section">
                  <h3 className="section-heading">Deterministic Score Breakdown</h3>
                  <div className="score-breakdown-grid">
                    <div className="breakdown-item">
                      <span className="breakdown-label">Missing in 2B Factor:</span>
                      <strong className="mono">+{profile.score_breakdown?.missing_2b_factor || 0} pts</strong>
                    </div>
                    <div className="breakdown-item">
                      <span className="breakdown-label">Tax Mismatch Factor:</span>
                      <strong className="mono">+{profile.score_breakdown?.tax_mismatch_factor || 0} pts</strong>
                    </div>
                    <div className="breakdown-item">
                      <span className="breakdown-label">Duplicate / Invalid Data:</span>
                      <strong className="mono">+{profile.score_breakdown?.duplicate_invalid_factor || 0} pts</strong>
                    </div>
                    <div className="breakdown-item">
                      <span className="breakdown-label">Exposure Magnitude:</span>
                      <strong className="mono">+{profile.score_breakdown?.exposure_factor || 0} pts</strong>
                    </div>
                    <div className="breakdown-item">
                      <span className="breakdown-label">Fuzzy Match Review:</span>
                      <strong className="mono">+{profile.score_breakdown?.fuzzy_match_factor || 0} pts</strong>
                    </div>
                  </div>

                  <h3 className="section-heading mt-4">Active Compliance Risk Signals</h3>
                  {profile.signals && profile.signals.length > 0 ? (
                    <div className="signals-list">
                      {profile.signals.map((sig, sIdx) => (
                        <div key={sIdx} className={`signal-card severity-${sig.severity.toLowerCase()}`}>
                          <div className="signal-top">
                            <span className={`signal-pill pill-${sig.severity.toLowerCase()}`}>
                              {sig.severity}
                            </span>
                            <strong className="signal-label">{sig.label}</strong>
                            {Number(sig.amount || 0) > 0 && (
                              <span className="signal-amount mono">
                                ₹{Number(sig.amount).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                              </span>
                            )}
                          </div>
                          <p className="signal-reason">{sig.reason}</p>
                          <div className="signal-footer text-muted">
                            Code: <code className="mono">{sig.code}</code> • Affects {sig.count} invoice(s)
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="clean-signals-card">
                      <IconCheckCircle size={16} className="text-success inline mr-1.5" />
                      <span>Zero adverse risk signals detected. This supplier has clean reconciliation status.</span>
                    </div>
                  )}

                  <h3 className="section-heading mt-4">Statutory Action Guidelines</h3>
                  <ul className="guidelines-list">
                    {(profile.recommended_actions || []).map((action, aIdx) => (
                      <li key={aIdx} className="guideline-item">
                        <span className="guideline-bullet">•</span>
                        <span>{action}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* TAB 2: Affected Invoices */}
              {activeSubTab === 'invoices' && (
                <div className="drilldown-section">
                  <h3 className="section-heading">Non-Compliant & Discrepancy Invoices</h3>
                  {profile.affected_invoices && profile.affected_invoices.length > 0 ? (
                    <div className="data-table-container">
                      <table className="fintech-table">
                        <thead>
                          <tr>
                            <th>Invoice #</th>
                            <th>Status</th>
                            <th>Purchase Tax</th>
                            <th>2B Tax</th>
                            <th>Difference</th>
                            <th>Statutory Rule</th>
                            <th>Action</th>
                          </tr>
                        </thead>
                        <tbody>
                          {profile.affected_invoices.map((inv, iIdx) => (
                            <tr key={iIdx}>
                              <td><strong className="mono">{inv.invoice_number}</strong></td>
                              <td><span className={`status-badge badge-${inv.status}`}>{inv.status}</span></td>
                              <td className="mono">{inv.purchase_tax !== null ? `₹${Number(inv.purchase_tax).toLocaleString('en-IN', { minimumFractionDigits: 2 })}` : '-'}</td>
                              <td className="mono">{inv.gstr2b_tax !== null ? `₹${Number(inv.gstr2b_tax).toLocaleString('en-IN', { minimumFractionDigits: 2 })}` : '-'}</td>
                              <td className="mono font-bold text-danger">
                                ₹{Number(inv.tax_difference || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                              </td>
                              <td className="mono text-muted" style={{ fontSize: '0.72rem' }}>
                                {inv.statutory_rule || 'Section 16(2)(aa)'}
                              </td>
                              <td>
                                <button
                                  className="btn btn-secondary-sm"
                                  onClick={() => onInspectInvoice && onInspectInvoice(inv)}
                                  title="Inspect invoice details"
                                >
                                  <IconEye size={12} className="mr-1" /> Inspect
                                </button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <div className="clean-signals-card">
                      <IconCheckCircle size={16} className="text-success inline mr-1.5" />
                      <span>No discrepancy invoices detected for this counterparty.</span>
                    </div>
                  )}
                </div>
              )}

              {/* TAB 3: Multi-Session Trends */}
              {activeSubTab === 'history' && (
                <div className="drilldown-section">
                  <h3 className="section-heading">Multi-Session Historical Performance</h3>
                  {history ? (
                    <div>
                      <div className="history-summary-box">
                        <div className="summary-stat">
                          <span className="stat-label">Sessions Evaluated:</span>
                          <span className="stat-val mono">{history.sessions_seen_count || 1}</span>
                        </div>
                        <div className="summary-stat">
                          <span className="stat-label">Historical Invoices:</span>
                          <span className="stat-val mono">{history.total_historical_invoices || profile.total_invoices}</span>
                        </div>
                        <div className="summary-stat">
                          <span className="stat-label">Historical At-Risk ITC:</span>
                          <span className="stat-val mono text-danger">
                            ₹{Number(history.total_historical_at_risk_itc || profile.at_risk_itc).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                          </span>
                        </div>
                      </div>

                      <div className="mt-3">
                        <strong className="text-muted" style={{ fontSize: '0.76rem', textTransform: 'uppercase' }}>
                          Compliance Patterns Detected:
                        </strong>
                        {history.has_sufficient_history && history.detected_patterns && history.detected_patterns.length > 0 ? (
                          <div className="patterns-pill-container mt-1.5">
                            {history.detected_patterns.map((pat, pIdx) => (
                              <span key={pIdx} className="pattern-pill">
                                <IconAlertCircle size={12} className="inline mr-1 text-danger" />
                                {pat}
                              </span>
                            ))}
                          </div>
                        ) : (
                          <p className="text-muted mt-1" style={{ fontSize: '0.82rem' }}>
                            {history.has_sufficient_history
                              ? 'No chronic non-compliance patterns detected across historical sessions.'
                              : 'Insufficient historical data (minimum 2 historical sessions required to establish chronic patterns).'}
                          </p>
                        )}
                      </div>

                      <div className="history-data-quality-notice mt-3 p-2 bg-light border rounded text-muted" style={{ fontSize: '0.76rem', lineHeight: '1.4' }}>
                        <IconAlertCircle size={13} className="inline mr-1 text-primary" style={{ verticalAlign: '-2px' }} />
                        <span><strong>Data Quality Notice:</strong> Historical session metrics reflect runs recorded in the local developer database (including automated test suites and demo reconciliations). These should be evaluated as test telemetry rather than verified multi-year statutory filings.</span>
                      </div>

                      {history.trends && history.trends.length > 0 && (
                        <div className="data-table-container mt-3">
                          <div className="text-muted mb-1 font-semibold" style={{ fontSize: '0.72rem' }}>
                            Showing latest {Math.min(10, history.trends.length)} of {history.trends.length} recorded session runs
                          </div>
                          <table className="fintech-table">
                            <thead>
                              <tr>
                                <th>Session ID</th>
                                <th>Date</th>
                                <th>Invoices</th>
                                <th>Missing 2B</th>
                                <th>Tax Mismatches</th>
                                <th>At-Risk ITC</th>
                              </tr>
                            </thead>
                            <tbody>
                              {history.trends.slice(-10).reverse().map((tr, tIdx) => (
                                <tr key={tIdx}>
                                  <td><code className="mono">{tr.session_id}</code></td>
                                  <td className="text-muted" style={{ fontSize: '0.75rem' }}>{tr.created_at?.slice(0, 10) || '-'}</td>
                                  <td className="mono">{tr.total_invoices}</td>
                                  <td className="mono">{tr.missing_in_2b}</td>
                                  <td className="mono">{tr.tax_mismatches}</td>
                                  <td className="mono text-danger font-bold">
                                    ₹{Number(tr.at_risk_itc || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      )}
                    </div>
                  ) : (
                    <p className="text-muted">Loading multi-session records...</p>
                  )}
                </div>
              )}
            </>
          )}
        </div>

        {/* Drawer Footer Actions */}
        <div className="drilldown-footer">
          <button
            className="btn btn-secondary-sm"
            onClick={() => onAskAboutSupplier && onAskAboutSupplier(supplierGstin, profile?.supplier_name)}
            title="Ask Copilot about this supplier"
          >
            <IconCopilot size={13} className="mr-1 text-accent" />
            <span>Ask VyaparMitra</span>
          </button>
          <button
            className="btn btn-primary-sm"
            onClick={() => onDraftNotice && onDraftNotice(supplierGstin, profile?.supplier_name)}
            title="Draft dispute notice for this supplier"
          >
            <IconCopilot size={13} className="mr-1" />
            <span>Draft Dispute Notice</span>
          </button>
        </div>
      </div>
    </div>
  )
}
