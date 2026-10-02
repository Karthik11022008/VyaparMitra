import React, { useState, useEffect, useRef } from 'react'
import {
  IconX,
  IconCopilot,
  IconSearch,
  IconArrowRight,
  IconCheck,
  IconCheckCircle,
  IconAlertTriangle,
  IconAlertCircle,
  IconRefresh,
  IconBuilding,
  IconLedger,
  IconEye,
  IconHistory,
} from './Icons'

export const GlobalAssistantDrawer = ({
  isOpen,
  onClose,
  sessionId,
  currentSupplierContext,
  currentInvoiceContext,
  onClearSupplierContext,
  onClearInvoiceContext,
  onInspectInvoice,
  onNoticeAction,
}) => {
  const [conversations, setConversations] = useState([])
  const [activeConversationId, setActiveConversationId] = useState(null)
  const [messages, setMessages] = useState([])
  const [inputValue, setInputValue] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [expandedTraces, setExpandedTraces] = useState({})
  const [expandedEvidence, setExpandedEvidence] = useState({})
  const [noticeActionsState, setNoticeActionsState] = useState({})

  const messagesEndRef = useRef(null)
  const skipMessageLoadRef = useRef(null)

  // Auto-scroll to bottom on new messages
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages, loading])

  // Load conversations when drawer opens or session changes
  useEffect(() => {
    if (!isOpen) return

    const sid = sessionId || 'demo-session'
    const loadConversations = async () => {
      try {
        const res = await fetch(`http://localhost:8000/api/agent/conversations/${sid}`)
        if (res.ok) {
          const data = await res.json()
          setConversations(data || [])
          if (data && data.length > 0 && !activeConversationId) {
            setActiveConversationId(data[0].conversation_id)
          }
        }
      } catch (e) {
        console.warn('Could not load conversations:', e)
      }
    }

    loadConversations()
  }, [isOpen, sessionId])

  // Load messages whenever activeConversationId changes
  useEffect(() => {
    if (skipMessageLoadRef.current === activeConversationId) {
      skipMessageLoadRef.current = null
      return
    }

    if (!activeConversationId) {
      // Default welcome message for blank session
      setMessages([
        {
          message_id: 'welcome-init',
          role: 'assistant',
          content: 'Hello! I am your VyaparMitra AI Reconciliation Assistant. Ask any question about your active ledger records, at-risk ITC, counterparty compliance, or statutory rules. All answers are deterministically verified.',
          timestamp: new Date().toISOString(),
          tools_used: [],
          evidence: [],
          steps_executed: [],
        }
      ])
      return
    }

    const loadMessages = async () => {
      try {
        const res = await fetch(`http://localhost:8000/api/agent/conversations/${activeConversationId}/messages`)
        if (res.ok) {
          const data = await res.json()
          if (data && data.length > 0) {
            setMessages(data)
          } else {
            setMessages([
              {
                message_id: 'welcome-blank',
                role: 'assistant',
                content: 'Conversation initialized. What would you like to investigate in this reconciliation session?',
                timestamp: new Date().toISOString(),
              }
            ])
          }
        }
      } catch (e) {
        console.warn('Failed to load messages for conversation:', e)
      }
    }

    loadMessages()
  }, [activeConversationId])

  // Create a brand new conversation
  const handleNewConversation = async () => {
    const sid = sessionId || 'demo-session'
    try {
      const res = await fetch('http://localhost:8000/api/agent/conversations', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sid,
          title: `Inquiry ${new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`
        })
      })
      if (res.ok) {
        const newConv = await res.json()
        setConversations(prev => [newConv, ...prev])
        setActiveConversationId(newConv.conversation_id)
        setMessages([
          {
            message_id: 'welcome-blank',
            role: 'assistant',
            content: 'New investigation thread initialized. What would you like to investigate in this reconciliation session?',
            timestamp: new Date().toISOString(),
          }
        ])
      }
    } catch (e) {
      console.warn('Could not create conversation:', e)
    }
  }

  // Delete current conversation
  const handleDeleteConversation = async () => {
    if (!activeConversationId) return
    const idToDelete = activeConversationId
    try {
      const res = await fetch(`http://localhost:8000/api/agent/conversations/${idToDelete}`, {
        method: 'DELETE'
      })
      if (res.ok) {
        const remaining = conversations.filter(c => c.conversation_id !== idToDelete)
        setConversations(remaining)
        if (remaining.length > 0) {
          setActiveConversationId(remaining[0].conversation_id)
        } else {
          setActiveConversationId(null)
          setMessages([
            {
              message_id: 'welcome-init',
              role: 'assistant',
              content: 'Hello! I am your VyaparMitra AI Reconciliation Assistant. Ask any question about your active ledger records, at-risk ITC, counterparty compliance, or statutory rules. All answers are deterministically verified.',
              timestamp: new Date().toISOString(),
              tools_used: [],
              evidence: [],
              steps_executed: [],
            }
          ])
        }
      }
    } catch (e) {
      console.warn('Could not delete conversation:', e)
    }
  }

  // Notice Action Handlers (HITL)
  const handleNoticeApprove = async (noticeId) => {
    setNoticeActionsState(prev => ({
      ...prev,
      [noticeId]: { ...(prev[noticeId] || {}), status: 'APPROVED', isEditing: false }
    }))
    if (onNoticeAction) {
      await onNoticeAction(noticeId, 'APPROVE')
    }
  }

  const handleNoticeReject = async (noticeId) => {
    setNoticeActionsState(prev => ({
      ...prev,
      [noticeId]: { ...(prev[noticeId] || {}), status: 'REJECTED', isEditing: false }
    }))
    if (onNoticeAction) {
      await onNoticeAction(noticeId, 'REJECT')
    }
  }

  const handleNoticeStartEdit = (notice) => {
    const current = noticeActionsState[notice.notice_id] || {}
    setNoticeActionsState(prev => ({
      ...prev,
      [notice.notice_id]: {
        ...current,
        isEditing: true,
        editedSubject: current.editedSubject !== undefined ? current.editedSubject : notice.subject,
        editedBody: current.editedBody !== undefined ? current.editedBody : (notice.body || ''),
      }
    }))
  }

  const handleNoticeSaveEdit = async (noticeId) => {
    const current = noticeActionsState[noticeId] || {}
    setNoticeActionsState(prev => ({
      ...prev,
      [noticeId]: {
        ...current,
        isEditing: false,
        status: 'DRAFT',
      }
    }))
    if (onNoticeAction) {
      await onNoticeAction(noticeId, 'EDIT')
    }
  }

  // Send question to /api/agent/investigate
  const handleSend = async (questionText = null) => {
    const q = (questionText !== null ? questionText : inputValue).trim()
    if (!q) return

    setInputValue('')
    setLoading(true)
    setError(null)

    const sid = sessionId || 'demo-session'
    let convId = activeConversationId

    // If no conversation exists yet, create one
    if (!convId) {
      try {
        const createRes = await fetch('http://localhost:8000/api/agent/conversations', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ session_id: sid, title: q.slice(0, 35) })
        })
        if (createRes.ok) {
          const newConv = await createRes.json()
          setConversations(prev => [newConv, ...prev])
          convId = newConv.conversation_id
          skipMessageLoadRef.current = convId
          setActiveConversationId(convId)
        }
      } catch (err) {
        console.warn('Error auto-creating conversation:', err)
      }
    }

    // Optimistically append user message
    const tempUserMsg = {
      message_id: 'temp-user-' + Date.now(),
      role: 'user',
      content: q,
      timestamp: new Date().toISOString(),
    }
    setMessages(prev => [...prev, tempUserMsg])

    try {
      const payload = {
        question: q,
        session_id: sid,
        conversation_id: convId || undefined,
        supplier_context: currentSupplierContext || undefined,
        invoice_context: currentInvoiceContext || undefined,
      }

      const res = await fetch('http://localhost:8000/api/agent/investigate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })

      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Investigation failed')

      const asstMsg = {
        message_id: data.message_id || 'asst-' + Date.now(),
        role: 'assistant',
        content: data.answer,
        intent: data.intent,
        tools_used: data.tools_used || [],
        plan: data.plan || [],
        steps_executed: data.steps_executed || [],
        evidence: data.evidence || [],
        suggested_action: data.suggested_action,
        draft_notice: data.draft_notice,
        timestamp: new Date().toISOString(),
      }

      setMessages(prev => [...prev, asstMsg])
      setExpandedTraces(prev => ({ ...prev, [asstMsg.message_id]: true }))
    } catch (err) {
      setError(err.message)
      setMessages(prev => [
        ...prev,
        {
          message_id: 'err-' + Date.now(),
          role: 'assistant',
          content: `⚠️ Investigation error: ${err.message}. Please verify the active session.`,
          isError: true,
          timestamp: new Date().toISOString(),
        }
      ])
    } finally {
      setLoading(false)
    }
  }

  if (!isOpen) return null

  const suggestions = [
    'Why is my ITC at risk?',
    'Show invoices missing from GSTR-2B',
    'Which suppliers are most delinquent?',
    'Calculate Section 50 interest exposure',
    'Explain CGST Section 16(2)(aa)',
  ]

  return (
    <div className="assistant-backdrop" onClick={onClose}>
      <div className="assistant-drawer" onClick={(e) => e.stopPropagation()}>
        {/* Top Header */}
        <div className="assistant-header">
          <div className="assistant-title-group">
            <div className="assistant-bot-avatar">
              <IconCopilot size={16} />
            </div>
            <div>
              <div className="assistant-title">Ask VyaparMitra</div>
              <div className="assistant-status">
                <span className="dot online"></span>
                <span>Deterministic Financial Assistant</span>
              </div>
            </div>
          </div>

          <div className="assistant-header-actions">
            <button
              className="btn btn-secondary-sm"
              onClick={handleNewConversation}
              title="Start a new investigation thread"
            >
              + New Chat
            </button>
            {activeConversationId && (
              <button
                className="btn btn-secondary-sm text-danger"
                onClick={handleDeleteConversation}
                title="Delete current conversation thread"
                style={{ color: 'var(--status-danger)' }}
              >
                Clear Chat
              </button>
            )}
            <button className="assistant-close-btn" onClick={onClose} aria-label="Close assistant">
              <IconX size={18} />
            </button>
          </div>
        </div>

        {/* Conversation Picker Ribbon if multi-conversation */}
        {conversations.length > 1 && (
          <div className="conversations-ribbon">
            <span className="ribbon-label">Threads:</span>
            <div className="ribbon-items">
              {conversations.slice(0, 4).map(c => (
                <button
                  key={c.conversation_id}
                  className={`ribbon-chip ${c.conversation_id === activeConversationId ? 'active' : ''}`}
                  onClick={() => setActiveConversationId(c.conversation_id)}
                >
                  {c.title || 'Inquiry'}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Active Context Badges */}
        {(currentSupplierContext || currentInvoiceContext) && (
          <div className="active-context-bar">
            <span className="context-label">Active Context:</span>
            {currentSupplierContext && (
              <span className="context-pill">
                <IconBuilding size={11} className="mr-1 inline text-accent" />
                <span>Supplier: {currentSupplierContext}</span>
                <button onClick={onClearSupplierContext} className="context-pill-clear" title="Clear supplier context">
                  <IconX size={10} />
                </button>
              </span>
            )}
            {currentInvoiceContext && (
              <span className="context-pill">
                <IconLedger size={11} className="mr-1 inline text-accent" />
                <span>Invoice: {currentInvoiceContext}</span>
                <button onClick={onClearInvoiceContext} className="context-pill-clear" title="Clear invoice context">
                  <IconX size={10} />
                </button>
              </span>
            )}
          </div>
        )}

        {/* Message Thread */}
        <div className="assistant-messages-container">
          {messages.map((msg, idx) => {
            const isAsst = msg.role === 'assistant'
            const msgId = msg.message_id || `msg-${idx}`

            return (
              <div key={msgId} className={`chat-bubble-row ${isAsst ? 'assistant-row' : 'user-row'}`}>
                {isAsst && (
                  <div className="chat-avatar">
                    <IconCopilot size={13} />
                  </div>
                )}

                <div className={`chat-bubble ${isAsst ? 'bubble-assistant' : 'bubble-user'} ${msg.isError ? 'bubble-error' : ''}`}>
                  <div className="chat-bubble-text">{msg.content}</div>

                  {/* Multi-Step Agentic Reasoning Traces */}
                  {isAsst && msg.steps_executed && msg.steps_executed.length > 0 && (
                    <div className="steps-collapsible mt-2.5">
                      <button
                        className="steps-toggle-btn"
                        onClick={() =>
                          setExpandedTraces(prev => ({ ...prev, [msgId]: !prev[msgId] }))
                        }
                      >
                        <span className="font-semibold text-accent" style={{ fontSize: '0.74rem' }}>
                          ⚡ Executed {msg.steps_executed.length} Deterministic Tool Step(s)
                        </span>
                        <span className="text-muted" style={{ fontSize: '0.7rem' }}>
                          {expandedTraces[msgId] ? '▲ Hide Trace' : '▼ Show Trace'}
                        </span>
                      </button>

                      {expandedTraces[msgId] && (
                        <div className="steps-trace-list mt-1.5">
                          {msg.steps_executed.map((st, sIdx) => (
                            <div key={sIdx} className="step-trace-item">
                              <div className="step-trace-top">
                                <span className="step-trace-badge">Step {st.step_index || sIdx + 1}</span>
                                <code className="step-trace-name mono">{st.tool_name}</code>
                                <span className="step-trace-duration mono">{Number(st.duration_ms || 0).toFixed(1)}ms</span>
                              </div>
                              <div className="step-trace-obs">{st.observation_summary}</div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}

                  {/* Structured Evidence Items */}
                  {isAsst && msg.evidence && msg.evidence.length > 0 && (
                    <div className="evidence-collapsible mt-2">
                      <button
                        className="evidence-toggle-btn"
                        onClick={() =>
                          setExpandedEvidence(prev => ({ ...prev, [msgId]: !prev[msgId] }))
                        }
                      >
                        <span style={{ fontSize: '0.74rem', fontWeight: 600 }}>
                          📋 Grounded Evidence ({msg.evidence.length} Record{msg.evidence.length > 1 ? 's' : ''})
                        </span>
                        <span className="text-muted" style={{ fontSize: '0.7rem' }}>
                          {expandedEvidence[msgId] ? '▲ Hide Evidence' : '▼ Show Evidence'}
                        </span>
                      </button>

                      {expandedEvidence[msgId] && (
                        <div className="evidence-table-mini mt-1.5">
                          <table className="fintech-table" style={{ fontSize: '0.74rem' }}>
                            <thead>
                              <tr>
                                <th>Invoice / Ref</th>
                                <th>Supplier</th>
                                <th>Status</th>
                                <th>Difference</th>
                              </tr>
                            </thead>
                            <tbody>
                              {msg.evidence.map((ev, eIdx) => (
                                <tr key={eIdx}>
                                  <td>
                                    <strong className="mono">{ev.invoice_number}</strong>
                                    {onInspectInvoice && ev.invoice_number && ev.invoice_number.includes('-') && (
                                      <button
                                        className="btn-link-xs ml-1"
                                        onClick={() => onInspectInvoice(ev.invoice_number)}
                                        title="Inspect in ledger"
                                      >
                                        [view]
                                      </button>
                                    )}
                                  </td>
                                  <td>{ev.supplier_name || ev.supplier_gstin}</td>
                                  <td><span className="status-badge" style={{ fontSize: '0.65rem' }}>{ev.status}</span></td>
                                  <td className="mono text-danger font-bold">
                                    ₹{Number(ev.tax_difference || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Embedded HITL Dispute Notice Card */}
                  {isAsst && msg.draft_notice && (() => {
                    const nid = msg.draft_notice.notice_id
                    const nState = noticeActionsState[nid] || { status: 'DRAFT', isEditing: false }
                    const isDraft = !nState.status || nState.status === 'DRAFT'
                    const isApproved = nState.status === 'APPROVED'
                    const isRejected = nState.status === 'REJECTED'

                    return (
                      <div className="embedded-notice-card mt-3">
                        <div className="notice-card-header">
                          {isDraft && (
                            <span className="notice-badge-review">DRAFT — REQUIRES HUMAN REVIEW</span>
                          )}
                          {isApproved && (
                            <span className="notice-badge-review" style={{ backgroundColor: '#10b981', color: '#fff' }}>
                              <IconCheck size={11} className="inline mr-1" /> APPROVED
                            </span>
                          )}
                          {isRejected && (
                            <span className="notice-badge-review" style={{ backgroundColor: '#ef4444', color: '#fff' }}>
                              <IconX size={11} className="inline mr-1" /> REJECTED
                            </span>
                          )}
                          <span className="mono text-muted" style={{ fontSize: '0.7rem' }}>{nid}</span>
                        </div>
                        <div className="notice-card-body">
                          <div><strong>Counterparty:</strong> {msg.draft_notice.supplier_reference}</div>
                          <div><strong>Invoice:</strong> {msg.draft_notice.invoice_reference}</div>
                          {nState.isEditing ? (
                            <div className="notice-edit-form mt-2">
                              <label className="text-muted block text-xs font-semibold mb-1">Subject Line:</label>
                              <input
                                type="text"
                                className="form-input text-xs w-full mb-2 p-1 border rounded"
                                value={nState.editedSubject !== undefined ? nState.editedSubject : msg.draft_notice.subject}
                                onChange={(e) => setNoticeActionsState(prev => ({
                                  ...prev,
                                  [nid]: { ...prev[nid], editedSubject: e.target.value }
                                }))}
                              />
                              <label className="text-muted block text-xs font-semibold mb-1">Draft Message Body:</label>
                              <textarea
                                className="form-input text-xs w-full p-1 border rounded font-mono"
                                rows={3}
                                value={nState.editedBody !== undefined ? nState.editedBody : (msg.draft_notice.body || '')}
                                onChange={(e) => setNoticeActionsState(prev => ({
                                  ...prev,
                                  [nid]: { ...prev[nid], editedBody: e.target.value }
                                }))}
                              />
                            </div>
                          ) : (
                            <>
                              <div><strong>Subject:</strong> {nState.editedSubject || msg.draft_notice.subject}</div>
                              {nState.editedBody && (
                                <div className="mt-1 text-muted text-xs bg-light p-1 rounded font-mono">
                                  {nState.editedBody}
                                </div>
                              )}
                            </>
                          )}
                          <div className="notice-at-risk mono font-bold text-danger mt-1">
                            Verified Amount: ₹{Number(msg.draft_notice.verified_amount || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                          </div>
                        </div>

                        {/* HITL Action Controls */}
                        <div className="notice-card-actions mt-2 flex gap-2">
                          {nState.isEditing ? (
                            <>
                              <button
                                className="btn btn-primary-sm"
                                onClick={() => handleNoticeSaveEdit(nid)}
                                title="Save edits to draft"
                              >
                                Save Changes
                              </button>
                              <button
                                className="btn btn-secondary-sm"
                                onClick={() => setNoticeActionsState(prev => ({
                                  ...prev,
                                  [nid]: { ...prev[nid], isEditing: false }
                                }))}
                              >
                                Cancel
                              </button>
                            </>
                          ) : isDraft ? (
                            <>
                              <button
                                className="btn btn-success-sm"
                                onClick={() => handleNoticeApprove(nid)}
                                title="Explicitly authorize and approve notice"
                              >
                                <IconCheck size={12} className="mr-1 inline" /> Approve Notice
                              </button>
                              <button
                                className="btn btn-secondary-sm"
                                onClick={() => handleNoticeStartEdit(msg.draft_notice)}
                                title="Edit notice subject and text"
                              >
                                Edit Draft
                              </button>
                              <button
                                className="btn btn-secondary-sm"
                                onClick={() => handleNoticeReject(nid)}
                                title="Explicitly reject notice dispatch"
                                style={{ color: 'var(--status-danger)' }}
                              >
                                <IconX size={12} className="mr-1 inline" /> Reject Notice
                              </button>
                            </>
                          ) : (
                            <span className="text-muted text-xs italic" style={{ fontSize: '0.75rem' }}>
                              Human decision recorded: <strong>{nState.status}</strong>. Assistant will not modify.
                            </span>
                          )}
                        </div>
                      </div>
                    )
                  })()}

                  <div className="chat-bubble-time">
                    {new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </div>
                </div>
              </div>
            )
          })}

          {loading && (
            <div className="chat-bubble-row assistant-row">
              <div className="chat-avatar">
                <IconCopilot size={13} className="spin" />
              </div>
              <div className="chat-bubble bubble-assistant bubble-loading">
                <div className="typing-dots">
                  <span></span><span></span><span></span>
                </div>
                <span className="loading-label ml-2">Reasoning over verified session ledger...</span>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Suggestion Chips */}
        <div className="assistant-suggestions">
          {suggestions.map((sug, idx) => (
            <button
              key={idx}
              className="suggestion-chip"
              onClick={() => handleSend(sug)}
              disabled={loading}
            >
              {sug}
            </button>
          ))}
        </div>

        {/* Input Bar */}
        <div className="assistant-input-bar">
          <textarea
            className="assistant-textarea"
            placeholder={
              currentSupplierContext
                ? `Ask about supplier ${currentSupplierContext}...`
                : 'Ask a question about this reconciliation session...'
            }
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                handleSend()
              }
            }}
            rows={1}
            disabled={loading}
          />
          <button
            className="btn btn-primary assistant-send-btn"
            onClick={() => handleSend()}
            disabled={loading || !inputValue.trim()}
            title="Send query"
          >
            <IconArrowRight size={14} />
          </button>
        </div>

        {/* Assistant Footer Guardrail Notice */}
        <div className="assistant-footer-note">
          <span>Zero-LLM-Math Guarantee • All numbers computed deterministically</span>
        </div>
      </div>
    </div>
  )
}
