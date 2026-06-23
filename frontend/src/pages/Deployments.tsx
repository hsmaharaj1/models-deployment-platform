import { useState, useEffect, useCallback } from 'react'
import Layout from '../components/Layout'
import { deploymentsApi, jobsApi } from '../api'
import type { Deployment, DeploymentStatus, JobResult } from '../types'
import {
  Rocket, Square, RotateCcw, Zap, Terminal, X, ChevronRight,
  RefreshCw, AlertCircle, CheckCircle, Clock, Loader, XCircle, ListOrdered
} from 'lucide-react'

// ── Status helpers ────────────────────────────────────────────────────
const STATUS_CONFIG: Record<DeploymentStatus, { label: string; color: string; bg: string; icon: React.ReactNode }> = {
  pending:  { label: 'Pending',  color: '#f59e0b', bg: 'rgba(245,158,11,0.12)',  icon: <Clock size={12} /> },
  starting: { label: 'Starting', color: '#6366f1', bg: 'rgba(99,102,241,0.12)', icon: <Loader size={12} className="animate-spin" /> },
  running:  { label: 'Running',  color: '#10b981', bg: 'rgba(16,185,129,0.12)', icon: <CheckCircle size={12} /> },
  stopped:  { label: 'Stopped',  color: '#64748b', bg: 'rgba(100,116,139,0.12)', icon: <Square size={12} /> },
  failed:   { label: 'Failed',   color: '#ef4444', bg: 'rgba(239,68,68,0.12)',  icon: <XCircle size={12} /> },
}

const FRAMEWORK_STYLE: Record<string, { color: string; bg: string }> = {
  sklearn: { color: '#60a5fa', bg: 'rgba(59,130,246,0.1)' },
  pytorch: { color: '#f87171', bg: 'rgba(239,68,68,0.1)' },
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

// ── Predict Modal ─────────────────────────────────────────────────────
function PredictModal({ deployment, onClose }: { deployment: Deployment; onClose: () => void }) {
  const [inputText, setInputText] = useState('[[5.1, 3.5, 1.4, 0.2]]')
  const [result, setResult] = useState<{ predictions: unknown[]; latency_ms: number } | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handlePredict = async () => {
    setError('')
    setResult(null)
    setLoading(true)
    try {
      const parsed = JSON.parse(inputText)
      const inputs = Array.isArray(parsed[0]) ? parsed : [parsed]
      const res = await deploymentsApi.predict(deployment.id, inputs)
      setResult(res)
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message :
        (typeof e === 'object' && e !== null && 'response' in e
          ? (e as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : String(e)) ?? 'Prediction failed'
      setError(String(msg))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ background: 'rgba(0,0,0,0.65)', backdropFilter: 'blur(4px)' }}
      onClick={e => { if (e.target === e.currentTarget) onClose() }}>
      <div className="w-full max-w-lg mx-4 rounded-2xl border p-6"
        style={{ background: 'var(--color-bg-card)', borderColor: 'var(--color-border)', boxShadow: '0 30px 60px rgba(0,0,0,0.5)' }}>
        <div className="flex items-center justify-between mb-5">
          <div>
            <h2 className="text-base font-semibold" style={{ color: 'var(--color-text-primary)' }}>Test Inference</h2>
            <p className="text-xs mt-0.5" style={{ color: 'var(--color-text-muted)' }}>{deployment.name}</p>
          </div>
          <button onClick={onClose} style={{ color: 'var(--color-text-muted)' }}><X size={18} /></button>
        </div>

        <div className="mb-4">
          <label className="block text-xs font-medium mb-1.5" style={{ color: 'var(--color-text-secondary)' }}>
            Input JSON — array of arrays <span style={{ color: 'var(--color-text-muted)' }}>e.g. [[1.2, 3.4, 5.6]]</span>
          </label>
          <textarea
            id="predict-input"
            value={inputText}
            onChange={e => setInputText(e.target.value)}
            rows={4}
            className="w-full px-3 py-2.5 rounded-lg text-sm outline-none resize-none font-mono"
            style={{ background: 'var(--color-bg-secondary)', border: '1px solid var(--color-border)', color: 'var(--color-text-primary)' }}
            onFocus={e => (e.target.style.borderColor = 'var(--color-accent)')}
            onBlur={e => (e.target.style.borderColor = 'var(--color-border)')}
          />
        </div>

        <button
          id="run-predict-btn"
          onClick={handlePredict}
          disabled={loading}
          className="w-full py-2.5 rounded-lg text-sm font-semibold mb-4 flex items-center justify-center gap-2"
          style={{
            background: loading ? 'var(--color-border)' : 'linear-gradient(135deg, #10b981, #059669)',
            color: 'white',
            cursor: loading ? 'not-allowed' : 'pointer',
            boxShadow: loading ? 'none' : '0 0 20px rgba(16,185,129,0.25)',
          }}>
          {loading ? <><Loader size={14} className="animate-spin" /> Running...</> : <><Zap size={14} /> Run Prediction</>}
        </button>

        {error && (
          <div className="flex items-start gap-2 p-3 rounded-lg text-sm"
            style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.25)', color: 'var(--color-error)' }}>
            <AlertCircle size={14} className="mt-0.5 shrink-0" />
            <span className="font-mono text-xs break-all">{error}</span>
          </div>
        )}

        {result && (
          <div className="rounded-lg p-3 border" style={{ background: 'var(--color-bg-secondary)', borderColor: 'var(--color-border)' }}>
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-medium" style={{ color: 'var(--color-success)' }}>✓ Prediction</span>
              <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>{result.latency_ms.toFixed(1)} ms</span>
            </div>
            <pre className="text-xs font-mono overflow-auto" style={{ color: 'var(--color-text-primary)', maxHeight: '120px' }}>
              {JSON.stringify(result.predictions, null, 2)}
            </pre>
          </div>
        )}
      </div>
    </div>
  )
}

// ── Logs Modal ────────────────────────────────────────────────────────
function LogsModal({ deployment, onClose }: { deployment: Deployment; onClose: () => void }) {
  const [logs, setLogs] = useState('Loading...')

  useEffect(() => {
    deploymentsApi.getLogs(deployment.id)
      .then(r => setLogs(r.logs || 'No logs available'))
      .catch(() => setLogs('Failed to fetch logs'))
  }, [deployment.id])

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ background: 'rgba(0,0,0,0.65)', backdropFilter: 'blur(4px)' }}
      onClick={e => { if (e.target === e.currentTarget) onClose() }}>
      <div className="w-full max-w-2xl mx-4 rounded-2xl border p-6"
        style={{ background: 'var(--color-bg-card)', borderColor: 'var(--color-border)', boxShadow: '0 30px 60px rgba(0,0,0,0.5)' }}>
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Terminal size={16} style={{ color: 'var(--color-accent-hover)' }} />
            <h2 className="text-base font-semibold" style={{ color: 'var(--color-text-primary)' }}>Container Logs</h2>
          </div>
          <button onClick={onClose} style={{ color: 'var(--color-text-muted)' }}><X size={18} /></button>
        </div>
        <pre className="text-xs font-mono overflow-auto rounded-lg p-4"
          style={{ background: 'var(--color-bg-secondary)', color: '#a3e635', maxHeight: '400px', border: '1px solid var(--color-border)', lineHeight: '1.6' }}>
          {logs}
        </pre>
      </div>
    </div>
  )
}

// ── Deployment Card ───────────────────────────────────────────────────
function DeploymentCard({
  deployment,
  onStop,
  onRollback,
  onPredict,
  onLogs,
  onRecover,
  onAsyncQueue,
}: {
  deployment: Deployment
  onStop: () => void
  onRollback: () => void
  onPredict: () => void
  onLogs: () => void
  onRecover: () => void
  onAsyncQueue: () => void
}) {
  const s = STATUS_CONFIG[deployment.status]
  const fw = FRAMEWORK_STYLE[deployment.model_version?.framework ?? 'sklearn']
  const isActive = deployment.status === 'running'
  const isTransient = deployment.status === 'pending' || deployment.status === 'starting'

  return (
    <div className="rounded-xl border p-5 transition-all duration-200"
      style={{ background: 'var(--color-bg-card)', borderColor: isActive ? 'rgba(16,185,129,0.3)' : 'var(--color-border)' }}>
      {/* Header row */}
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg flex items-center justify-center"
            style={{ background: isActive ? 'rgba(16,185,129,0.12)' : 'var(--color-bg-elevated)' }}>
            <Rocket size={17} style={{ color: isActive ? '#10b981' : 'var(--color-text-muted)' }} />
          </div>
          <div>
            <h3 className="text-sm font-semibold" style={{ color: 'var(--color-text-primary)' }}>{deployment.name}</h3>
            <div className="flex items-center gap-2 mt-0.5">
              {deployment.model_version && (
                <>
                  <span className="text-xs px-1.5 py-0.5 rounded font-medium" style={fw}>
                    {deployment.model_version.framework}
                  </span>
                  <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                    {deployment.model_version.version_tag}
                  </span>
                </>
              )}
            </div>
          </div>
        </div>

        {/* Status badge */}
        <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium"
          style={{ background: s.bg, color: s.color }}>
          {isTransient && <span className="w-1.5 h-1.5 rounded-full animate-pulse" style={{ background: s.color }} />}
          {s.label}
        </div>
      </div>

      {/* Endpoint info */}
      {deployment.endpoint_url && (
        <div className="rounded-lg px-3 py-2 mb-4 flex items-center gap-2"
          style={{ background: 'var(--color-bg-secondary)', border: '1px solid var(--color-border)' }}>
          <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>Endpoint</span>
          <code className="text-xs flex-1 truncate" style={{ color: 'var(--color-accent-hover)' }}>
            {deployment.endpoint_url}/predict
          </code>
          <ChevronRight size={12} style={{ color: 'var(--color-text-muted)' }} />
        </div>
      )}

      {/* Metadata row */}
      <div className="flex items-center gap-4 mb-4 text-xs" style={{ color: 'var(--color-text-muted)' }}>
        {deployment.port && <span>Port {deployment.port}</span>}
        <span>Deployed {formatDate(deployment.created_at)}</span>
        {deployment.stopped_at && <span>Stopped {formatDate(deployment.stopped_at)}</span>}
      </div>

      {/* Actions */}
      <div className="flex items-center gap-2">
        {isActive && (
          <button
            id={`predict-btn-${deployment.id}`}
            onClick={onPredict}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all"
            style={{ background: 'rgba(16,185,129,0.12)', color: '#10b981', border: '1px solid rgba(16,185,129,0.25)' }}
            onMouseEnter={e => (e.currentTarget.style.background = 'rgba(16,185,129,0.2)')}
            onMouseLeave={e => (e.currentTarget.style.background = 'rgba(16,185,129,0.12)')}>
            <Zap size={12} /> Test Predict
          </button>
        )}

        {isActive && (
          <button
            id={`async-btn-${deployment.id}`}
            onClick={onAsyncQueue}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all"
            style={{ background: 'rgba(139,92,246,0.12)', color: '#a78bfa', border: '1px solid rgba(139,92,246,0.25)' }}
            onMouseEnter={e => (e.currentTarget.style.background = 'rgba(139,92,246,0.22)')}
            onMouseLeave={e => (e.currentTarget.style.background = 'rgba(139,92,246,0.12)')}>
            <ListOrdered size={12} /> Async Queue
          </button>
        )}

        {(isActive || deployment.status === 'failed') && (
          <button
            id={`rollback-btn-${deployment.id}`}
            onClick={onRollback}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all"
            style={{ background: 'rgba(99,102,241,0.1)', color: 'var(--color-accent-hover)', border: '1px solid rgba(99,102,241,0.2)' }}
            onMouseEnter={e => (e.currentTarget.style.background = 'rgba(99,102,241,0.2)')}
            onMouseLeave={e => (e.currentTarget.style.background = 'rgba(99,102,241,0.1)')}>
            <RotateCcw size={12} /> Rollback
          </button>
        )}

        {/* Recover — for containers that started but health-check timed out */}
        {(deployment.status === 'starting' || deployment.status === 'failed') && deployment.container_id && (
          <button
            id={`recover-btn-${deployment.id}`}
            onClick={onRecover}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all"
            style={{ background: 'rgba(245,158,11,0.1)', color: '#f59e0b', border: '1px solid rgba(245,158,11,0.25)' }}
            onMouseEnter={e => (e.currentTarget.style.background = 'rgba(245,158,11,0.2)')}
            onMouseLeave={e => (e.currentTarget.style.background = 'rgba(245,158,11,0.1)')}>
            <RefreshCw size={12} /> Recover
          </button>
        )}

        {deployment.container_id && (
          <button
            id={`logs-btn-${deployment.id}`}
            onClick={onLogs}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all"
            style={{ background: 'rgba(100,116,139,0.1)', color: 'var(--color-text-secondary)', border: '1px solid var(--color-border)' }}
            onMouseEnter={e => (e.currentTarget.style.background = 'rgba(100,116,139,0.2)')}
            onMouseLeave={e => (e.currentTarget.style.background = 'rgba(100,116,139,0.1)')}>
            <Terminal size={12} /> Logs
          </button>
        )}

        {(isActive || isTransient) && (
          <button
            id={`stop-btn-${deployment.id}`}
            onClick={onStop}
            className="ml-auto flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all"
            style={{ background: 'rgba(239,68,68,0.08)', color: '#ef4444', border: '1px solid rgba(239,68,68,0.2)' }}
            onMouseEnter={e => (e.currentTarget.style.background = 'rgba(239,68,68,0.18)')}
            onMouseLeave={e => (e.currentTarget.style.background = 'rgba(239,68,68,0.08)')}>
            <Square size={12} /> Stop
          </button>
        )}
      </div>
    </div>
  )
}

// ── Async Jobs Modal ──────────────────────────────────────────────────
function AsyncJobsModal({ deployment, onClose }: { deployment: Deployment; onClose: () => void }) {
  const [inputText, setInputText] = useState('[[5.1, 3.5, 1.4, 0.2]]')
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState('')
  const [jobs, setJobs] = useState<JobResult[]>([])
  const [pollingId, setPollingId] = useState<string | null>(null)

  // Load existing jobs on open
  useEffect(() => {
    jobsApi.list(deployment.id).then(setJobs).catch(() => {})
  }, [deployment.id])

  // Poll active job every 1.5s until it completes
  useEffect(() => {
    if (!pollingId) return
    const id = setInterval(async () => {
      try {
        const j = await jobsApi.get(pollingId)
        setJobs(prev => prev.map(p => p.job_id === j.job_id ? j : p))
        if (j.status === 'completed' || j.status === 'failed') {
          clearInterval(id)
          setPollingId(null)
        }
      } catch { clearInterval(id); setPollingId(null) }
    }, 1500)
    return () => clearInterval(id)
  }, [pollingId])

  const handleSubmit = async () => {
    setSubmitError('')
    setSubmitting(true)
    try {
      const parsed = JSON.parse(inputText)
      const inputs: number[][] = Array.isArray(parsed[0]) ? parsed : [parsed]
      const res = await jobsApi.submit(deployment.id, inputs)
      setPollingId(res.job_id)
      // Optimistically insert the new job at the top
      setJobs(prev => [{
        job_id: res.job_id, deployment_id: deployment.id,
        celery_task_id: null, status: 'queued',
        input_payload: { inputs }, output_payload: null,
        latency_ms: null, error_message: null,
        created_at: new Date().toISOString(), completed_at: null,
      }, ...prev])
    } catch (e: unknown) {
      const msg = typeof e === 'object' && e !== null && 'response' in e
        ? (e as { response?: { data?: { detail?: string } } }).response?.data?.detail
        : 'Submit failed'
      setSubmitError(String(msg ?? 'Submit failed'))
    } finally {
      setSubmitting(false)
    }
  }

  const statusColor = (s: string) =>
    s === 'completed' ? '#10b981' : s === 'failed' ? '#ef4444' : s === 'processing' ? '#6366f1' : '#f59e0b'

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ background: 'rgba(0,0,0,0.65)', backdropFilter: 'blur(4px)' }}
      onClick={e => { if (e.target === e.currentTarget) onClose() }}>
      <div className="w-full max-w-2xl mx-4 rounded-2xl border flex flex-col" style={{
        background: 'var(--color-bg-card)', borderColor: 'var(--color-border)',
        boxShadow: '0 30px 60px rgba(0,0,0,0.5)', maxHeight: '85vh',
      }}>
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b" style={{ borderColor: 'var(--color-border)' }}>
          <div>
            <h3 className="font-semibold text-base" style={{ color: 'var(--color-text-primary)' }}>
              Async Job Queue
            </h3>
            <p className="text-xs mt-0.5" style={{ color: 'var(--color-text-muted)' }}>
              {deployment.name} · jobs are processed by the Celery worker
            </p>
          </div>
          <button onClick={onClose} style={{ color: 'var(--color-text-muted)', background: 'none', border: 'none', cursor: 'pointer' }}>
            <X size={18} />
          </button>
        </div>

        {/* Submit form */}
        <div className="p-5 border-b" style={{ borderColor: 'var(--color-border)' }}>
          <label className="block text-xs font-medium mb-2" style={{ color: 'var(--color-text-secondary)' }}>
            Input payload (JSON array)
          </label>
          <textarea
            value={inputText}
            onChange={e => setInputText(e.target.value)}
            rows={2}
            className="w-full rounded-lg p-3 text-sm font-mono resize-none outline-none"
            style={{
              background: 'var(--color-bg-secondary)', border: '1px solid var(--color-border)',
              color: 'var(--color-text-primary)',
            }}
          />
          {submitError && (
            <p className="text-xs mt-1" style={{ color: '#ef4444' }}>{submitError}</p>
          )}
          <button
            id="submit-async-job-btn"
            onClick={handleSubmit}
            disabled={submitting}
            className="mt-3 flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all"
            style={{
              background: submitting ? 'rgba(139,92,246,0.1)' : 'rgba(139,92,246,0.2)',
              color: '#a78bfa', border: '1px solid rgba(139,92,246,0.3)',
              opacity: submitting ? 0.6 : 1, cursor: submitting ? 'not-allowed' : 'pointer',
            }}>
            {submitting ? <Loader size={13} className="animate-spin" /> : <ListOrdered size={13} />}
            {submitting ? 'Submitting…' : 'Submit Async Job'}
          </button>
        </div>

        {/* Job list */}
        <div className="overflow-y-auto flex-1 p-5">
          <p className="text-xs font-semibold uppercase tracking-wide mb-3" style={{ color: 'var(--color-text-muted)' }}>
            Recent Jobs ({jobs.length})
          </p>
          {jobs.length === 0 ? (
            <p className="text-sm text-center py-8" style={{ color: 'var(--color-text-muted)' }}>
              No jobs yet — submit one above
            </p>
          ) : (
            <div className="flex flex-col gap-2">
              {jobs.map(j => (
                <div key={j.job_id} className="rounded-lg p-3 border" style={{
                  background: 'var(--color-bg-secondary)', borderColor: 'var(--color-border)',
                }}>
                  <div className="flex items-center justify-between mb-1.5">
                    <code className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                      {j.job_id.slice(0, 8)}…
                    </code>
                    <span className="text-xs font-semibold px-2 py-0.5 rounded-full" style={{
                      color: statusColor(j.status),
                      background: `${statusColor(j.status)}18`,
                    }}>
                      {j.status}
                      {(j.status === 'queued' || j.status === 'processing') && (
                        <Loader size={9} className="inline ml-1 animate-spin" />
                      )}
                    </span>
                  </div>
                  {j.status === 'completed' && j.output_payload && (
                    <div className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>
                      <span style={{ color: '#10b981' }}>predictions: </span>
                      {JSON.stringify(j.output_payload.predictions)}
                      {j.latency_ms != null && (
                        <span style={{ color: 'var(--color-text-muted)', marginLeft: 8 }}>
                          {j.latency_ms.toFixed(1)}ms
                        </span>
                      )}
                    </div>
                  )}
                  {j.status === 'failed' && (
                    <p className="text-xs" style={{ color: '#ef4444' }}>{j.error_message}</p>
                  )}
                  {j.created_at && (
                    <p className="text-xs mt-1" style={{ color: 'var(--color-text-muted)' }}>
                      {new Date(j.created_at).toLocaleTimeString()}
                    </p>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// ── Main Page ─────────────────────────────────────────────────────────
export default function DeploymentsPage() {
  const [deployments, setDeployments] = useState<Deployment[]>([])
  const [loading, setLoading] = useState(true)
  const [predictTarget, setPredictTarget] = useState<Deployment | null>(null)
  const [logsTarget, setLogsTarget] = useState<Deployment | null>(null)
  const [asyncQueueTarget, setAsyncQueueTarget] = useState<Deployment | null>(null)
  const [actionError, setActionError] = useState('')

  const load = useCallback(async () => {
    try {
      const data = await deploymentsApi.list()
      setDeployments(data)
    } catch {
      // handled by interceptor
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  // Auto-refresh while any deployment is pending/starting
  useEffect(() => {
    const hasTransient = deployments.some(d => d.status === 'pending' || d.status === 'starting')
    if (!hasTransient) return
    const id = setInterval(load, 3000)
    return () => clearInterval(id)
  }, [deployments, load])

  const handleStop = async (dep: Deployment) => {
    if (!confirm(`Stop deployment "${dep.name}"?`)) return
    setActionError('')
    try {
      const updated = await deploymentsApi.stop(dep.id)
      setDeployments(prev => prev.map(d => d.id === updated.id ? updated : d))
    } catch {
      setActionError('Failed to stop deployment.')
    }
  }

  const handleRollback = async (dep: Deployment) => {
    if (!confirm(`Roll back "${dep.name}" to the previous model version?`)) return
    setActionError('')
    try {
      const newDep = await deploymentsApi.rollback(dep.id)
      setDeployments(prev => [newDep, ...prev.map(d => d.id === dep.id ? { ...d, status: 'stopped' as DeploymentStatus } : d)])
    } catch (e: unknown) {
      const msg = typeof e === 'object' && e !== null && 'response' in e
        ? (e as { response?: { data?: { detail?: string } } }).response?.data?.detail
        : 'Rollback failed'
      setActionError(String(msg ?? 'Rollback failed'))
    }
  }

  const handleRecover = async (dep: Deployment) => {
    setActionError('')
    try {
      const updated = await deploymentsApi.recover(dep.id)
      setDeployments(prev => prev.map(d => d.id === updated.id ? updated : d))
    } catch (e: unknown) {
      const msg = typeof e === 'object' && e !== null && 'response' in e
        ? (e as { response?: { data?: { detail?: string } } }).response?.data?.detail
        : 'Recovery failed — container may not be healthy yet'
      setActionError(String(msg ?? 'Recovery failed'))
    }
  }

  const running = deployments.filter(d => d.status === 'running').length
  const starting = deployments.filter(d => d.status === 'pending' || d.status === 'starting').length
  const failed = deployments.filter(d => d.status === 'failed').length

  return (
    <Layout activePage="deployments">
      <div className="p-8">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-2xl font-bold" style={{ color: 'var(--color-text-primary)' }}>Deployments</h1>
            <p className="text-sm mt-1" style={{ color: 'var(--color-text-secondary)' }}>
              {running} running · {starting} starting · {failed} failed
            </p>
          </div>
          <button
            onClick={load}
            className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-all"
            style={{ background: 'var(--color-bg-card)', color: 'var(--color-text-secondary)', border: '1px solid var(--color-border)' }}
            onMouseEnter={e => (e.currentTarget.style.borderColor = 'var(--color-accent)')}
            onMouseLeave={e => (e.currentTarget.style.borderColor = 'var(--color-border)')}>
            <RefreshCw size={14} /> Refresh
          </button>
        </div>

        {actionError && (
          <div className="flex items-center gap-2 p-3 rounded-lg mb-6 text-sm"
            style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)', color: 'var(--color-error)' }}>
            <AlertCircle size={14} />{actionError}
          </div>
        )}

        {/* Stats row */}
        <div className="grid grid-cols-4 gap-4 mb-8">
          {[
            { label: 'Total', value: deployments.length, color: 'var(--color-text-primary)' },
            { label: 'Running', value: running, color: '#10b981' },
            { label: 'Starting', value: starting, color: '#6366f1' },
            { label: 'Failed', value: failed, color: '#ef4444' },
          ].map(stat => (
            <div key={stat.label} className="rounded-xl p-4 border"
              style={{ background: 'var(--color-bg-card)', borderColor: 'var(--color-border)' }}>
              <div className="text-2xl font-bold mb-1" style={{ color: stat.color }}>{stat.value}</div>
              <div className="text-xs" style={{ color: 'var(--color-text-muted)' }}>{stat.label}</div>
            </div>
          ))}
        </div>

        {/* Loading skeletons */}
        {loading && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {[1, 2, 3].map(i => (
              <div key={i} className="h-48 rounded-xl animate-pulse" style={{ background: 'var(--color-bg-card)' }} />
            ))}
          </div>
        )}

        {/* Empty state */}
        {!loading && deployments.length === 0 && (
          <div className="flex flex-col items-center justify-center py-24 text-center">
            <div className="w-16 h-16 rounded-2xl flex items-center justify-center mb-4"
              style={{ background: 'var(--color-bg-card)', border: '1px solid var(--color-border)' }}>
              <Rocket size={28} style={{ color: 'var(--color-text-muted)' }} />
            </div>
            <p className="text-base font-medium mb-1" style={{ color: 'var(--color-text-secondary)' }}>No deployments yet</p>
            <p className="text-sm" style={{ color: 'var(--color-text-muted)' }}>
              Go to a project, select a model version, and click Deploy
            </p>
          </div>
        )}

        {/* Deployment grid */}
        {!loading && deployments.length > 0 && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {deployments.map(dep => (
              <DeploymentCard
                key={dep.id}
                deployment={dep}
                onStop={() => handleStop(dep)}
                onRollback={() => handleRollback(dep)}
                onPredict={() => setPredictTarget(dep)}
                onLogs={() => setLogsTarget(dep)}
                onRecover={() => handleRecover(dep)}
                onAsyncQueue={() => setAsyncQueueTarget(dep)}
              />
            ))}
          </div>
        )}
      </div>

      {predictTarget && (
        <PredictModal deployment={predictTarget} onClose={() => setPredictTarget(null)} />
      )}
      {logsTarget && (
        <LogsModal deployment={logsTarget} onClose={() => setLogsTarget(null)} />
      )}
      {asyncQueueTarget && (
        <AsyncJobsModal deployment={asyncQueueTarget} onClose={() => setAsyncQueueTarget(null)} />
      )}
    </Layout>
  )
}
