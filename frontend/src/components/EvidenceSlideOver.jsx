import React from 'react'
import { IconX, IconAlertCircle, IconAlertTriangle, IconArrowRight } from './Icons'

export const EvidenceSlideOver = ({ isOpen, onClose, resultItem, onDraftNotice }) => {
  if (!isOpen || !resultItem) return null

  const pInv = resultItem.purchase_invoice
  const bInv = resultItem.matched_2b_invoice
  const status = resultItem.status

  const isExact = status === 'EXACT_MATCH'
  const isFuzzy = status === 'FUZZY_MATCH_REQUIRES_REVIEW'
  const isMismatch = status === 'AMOUNT_MISMATCH'
  const isMissing2B = status === 'MISSING_IN_2B'
  const isMissingBooks = status === 'MISSING_IN_PURCHASE_REGISTER'
  const isInvalid = status === 'INVALID_DATA' || status === 'DUPLICATE_CANDIDATE'

  const taxDiff = Number(resultItem.tax_difference || 0)
  const taxableDiff = Number(resultItem.taxable_difference || 0)
  const confidence = Math.round(Number(resultItem.confidence || 0) * 100)

  return (
    <div className="slideover-backdrop" onClick={onClose}>
      <div className="slideover-panel" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="slideover-header">
          <div>
            <div className="slideover-pretitle">DISCREPANCY EVIDENCE INSPECTOR</div>
            <h2 className="slideover-title">
              {pInv?.invoice_number || bInv?.invoice_number || 'Invoice Investigation'}
            </h2>
            <div className="slideover-meta">
              <span>GSTIN: <code>{pInv?.supplier_gstin || bInv?.supplier_gstin || '-'}</code></span>
              <span className={`status-badge badge-${status}`}>{status}</span>
            </div>
          </div>
          <button className="btn-close" onClick={onClose} aria-label="Close Inspector">
            <IconX size={16} />
          </button>
        </div>

        <div className="slideover-body">
          {/* Side-by-Side Comparison */}
          <div className="evidence-grid">
            {/* Left: Purchase Register */}
            <div className="evidence-card evidence-left">
              <div className="evidence-card-header">
                <span className="source-tag source-books">BUYER'S BOOKS</span>
                <span className="source-sub">Purchase Register (ERP)</span>
              </div>
              {pInv ? (
                <div className="evidence-specs">
                  <div className="spec-row">
                    <span className="spec-label">Invoice Ref</span>
                    <span className="spec-value mono"><strong>{pInv.invoice_number}</strong></span>
                  </div>
                  <div className="spec-row">
                    <span className="spec-label">Invoice Date</span>
                    <span className="spec-value">{pInv.invoice_date || '-'}</span>
                  </div>
                  <div className="spec-row">
                    <span className="spec-label">Taxable Value</span>
                    <span className="spec-value mono">Rs. {Number(pInv.taxable_value).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                  </div>
                  <div className="spec-row">
                    <span className="spec-label">CGST + SGST</span>
                    <span className="spec-value mono">Rs. {(Number(pInv.cgst) + Number(pInv.sgst)).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                  </div>
                  <div className="spec-row">
                    <span className="spec-label">IGST</span>
                    <span className="spec-value mono">Rs. {Number(pInv.igst).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                  </div>
                  <div className="spec-row total-row">
                    <span className="spec-label">Claimed ITC</span>
                    <span className="spec-value mono text-accent">Rs. {Number(pInv.total_tax).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                  </div>
                </div>
              ) : (
                <div className="unreflected-box">
                  <IconAlertCircle size={24} className="text-muted mb-1" />
                  <p>Unrecorded in internal purchase books. Tax invoice missing from buyer accounting records.</p>
                </div>
              )}
            </div>

            {/* Right: GSTR-2B Statement */}
            <div className="evidence-card evidence-right">
              <div className="evidence-card-header">
                <span className="source-tag source-portal">GSTN PORTAL</span>
                <span className="source-sub">Auto-Drafted GSTR-2B</span>
              </div>
              {bInv ? (
                <div className="evidence-specs">
                  <div className="spec-row">
                    <span className="spec-label">Invoice Ref</span>
                    <span className="spec-value mono"><strong>{bInv.invoice_number}</strong></span>
                  </div>
                  <div className="spec-row">
                    <span className="spec-label">Filing Date</span>
                    <span className="spec-value">{bInv.invoice_date || '-'}</span>
                  </div>
                  <div className="spec-row">
                    <span className="spec-label">Taxable Value</span>
                    <span className="spec-value mono">Rs. {Number(bInv.taxable_value).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                  </div>
                  <div className="spec-row">
                    <span className="spec-label">CGST + SGST</span>
                    <span className="spec-value mono">Rs. {(Number(bInv.cgst) + Number(bInv.sgst)).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                  </div>
                  <div className="spec-row">
                    <span className="spec-label">IGST</span>
                    <span className="spec-value mono">Rs. {Number(bInv.igst).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                  </div>
                  <div className="spec-row total-row">
                    <span className="spec-label">Reflected ITC</span>
                    <span className="spec-value mono text-success">Rs. {Number(bInv.total_tax).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                  </div>
                </div>
              ) : (
                <div className="unreflected-box danger">
                  <IconAlertTriangle size={24} className="text-danger mb-1" />
                  <p><strong>Not reflected in GSTR-2B.</strong> Vendor has not filed GSTR-1 for this invoice.</p>
                </div>
              )}
            </div>
          </div>

          {/* Variance & Audit Findings Analysis */}
          <div className="analysis-card">
            <h4 className="analysis-title">Deterministic Variance Assessment</h4>
            <div className="analysis-metrics-grid">
              <div className="analysis-metric">
                <span className="label">Tax Difference</span>
                <span className="val mono" style={{ color: taxDiff > 0 ? 'var(--status-danger)' : 'var(--text-primary)' }}>
                  Rs. {taxDiff.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                </span>
              </div>
              <div className="analysis-metric">
                <span className="label">Taxable Difference</span>
                <span className="val mono">
                  Rs. {taxableDiff.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                </span>
              </div>
              <div className="analysis-metric">
                <span className="label">Matching Confidence</span>
                <span className="val mono">
                  {confidence}%
                </span>
              </div>
            </div>

            <div className="reasoning-box">
              <span className="reasoning-label">Finding Details:</span>
              <p>{resultItem.reason}</p>
            </div>
          </div>

          {/* Statutory Implications & Risk Guidance */}
          <div className="statutory-guidance-card">
            <div className="statutory-header">
              <IconAlertTriangle size={16} className="text-warning flex-shrink-0" />
              <span>Statutory Compliance Assessment</span>
            </div>
            {isMissing2B && (
              <p>
                <strong>CGST Act Section 16(2)(aa):</strong> Input Tax Credit cannot be availed in GSTR-3B because the outward supply was not furnished by the supplier in GSTR-1. Claiming this unreflected ITC triggers automated DRC-01B discrepancy notice with 18% p.a. interest under Section 50(1).
              </p>
            )}
            {isMismatch && (
              <p>
                <strong>Value/Tax Discrepancy:</strong> The ITC reported in GSTR-2B is lower than internal books. Claiming excess ITC beyond GSTR-2B without supplier credit/debit amendment creates statutory exposure.
              </p>
            )}
            {isFuzzy && (
              <p>
                <strong>Invoice Number Format Variance:</strong> The supplier reported this invoice under an alternate formatting structure. Confirm document identity before manual ledger reconciliation.
              </p>
            )}
            {isExact && (
              <p>
                <strong>Statutory Compliant:</strong> Invoice matches within the statutory tolerance (Rs. 1.00). Eligible for full ITC claim in GSTR-3B.
              </p>
            )}
            {isMissingBooks && (
              <p>
                <strong>Unbooked ITC Opportunity:</strong> Vendor filed this invoice in GSTR-1/2B, but your purchase books lack a corresponding voucher. Verify whether goods/services were received.
              </p>
            )}
            {isInvalid && (
              <p>
                <strong>Data Anomaly:</strong> Invalid GSTIN checksum or internal duplicate ledger record. Rectification required before return submission.
              </p>
            )}
          </div>
        </div>

        {/* Footer Actions */}
        <div className="slideover-footer">
          <button className="btn btn-secondary" onClick={onClose}>
            Close Inspector
          </button>
          {!isExact && (
            <button
              className="btn btn-primary"
              onClick={() => {
                onClose()
                if (onDraftNotice) onDraftNotice(resultItem)
              }}
            >
              Draft Vendor Dispute Notice <IconArrowRight size={14} className="ml-1 inline" />
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
