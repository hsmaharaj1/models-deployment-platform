import { useState, useEffect, useCallback } from 'react'
import Layout from '../components/Layout'
import { metricsApi } from '../api'
import type { MetricsSummary, DeploymentMetrics } from '../types'
import {
  Activity, AlertTriangle, Zap, TrendingUp, RefreshCw,
  ExternalLink, Circle
} from 'lucide-react'

// ── Helpers ───────────────────────────────────────────────────────────────────
function fmt(n: number, decimals = 1) {
  return n.toLocaleString('en-US', { maximumFractionDigits: decimals })
}

function LatencyBar({ value, max, color }: { value: number; max: number; color: string }) {
  const pct = max > 0 ? Math.min((value / max) * 100, 100) : 0
  return (
    <div style={{ background: 'rgba(255,255,255,0.05)', borderRadius: 4, height: 6, width: '100%' }}>
      <div style={{ width: `${pct}%`, height: '100%', background: color, borderRadius: 4, transition: 'width 0.4s ease' }} />
    </div>
  )
}

// ── Platform stat card ────────────────────────────────────────────────────────
function StatCard({ icon, label, value, sub, color }: {
  icon: React.ReactNode; label: string; value: string; sub?: string; color: string
}) {
  return (
    <div style={{
      background: 'var(--color-surface)',
      border: '1px solid var(--color-border)',
      borderRadius: 16,
      padding: '1.5rem',
      display: 'flex',
      flexDirection: 'column',
      gap: '0.5rem',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--color-text-muted)', fontSize: 13 }}>
        <span style={{ color }}>{icon}</span>
        {label}
      </div>
      <div style={{ fontSize: '2rem', fontWeight: 700, color: 'var(--color-text)', lineHeight: 1 }}>{value}</div>
      {sub && <div style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>{sub}</div>}
    </div>
  )
}

// ── Per-deployment row ────────────────────────────────────────────────────────
function DeploymentRow({ dep, maxLatency }: { dep: DeploymentMetrics; maxLatency: number }) {
  const isRunning = dep.status === 'running'
  const errorPct = dep.error_rate * 100
  const statusColor = isRunning ? '#22c55e' : dep.status === 'starting' ? '#a855f7' : '#6b7280'

  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: '16px 1fr 80px 80px 80px 80px 100px 90px',
      gap: '1rem',
      alignItems: 'center',
      padding: '0.875rem 1.25rem',
      borderBottom: '1px solid var(--color-border)',
      transition: 'background 0.15s',
    }}
      onMouseEnter={e => ((e.currentTarget as HTMLElement).style.background = 'rgba(255,255,255,0.03)')}
      onMouseLeave={e => ((e.currentTarget as HTMLElement).style.background = 'transparent')}
    >
      {/* Status dot */}
      <Circle size={8} fill={statusColor} color={statusColor} style={{ flexShrink: 0 }} />

      {/* Name + port */}
      <div>
        <div style={{ fontWeight: 600, fontSize: 14, color: 'var(--color-text)' }}>{dep.deployment_name}</div>
        <div style={{ fontSize: 11, color: 'var(--color-text-muted)' }}>:{dep.port}</div>
      </div>

      {/* Requests */}
      <div style={{ textAlign: 'right' }}>
        <div style={{ fontWeight: 600, fontSize: 14, color: 'var(--color-text)' }}>{fmt(dep.requests_total, 0)}</div>
        <div style={{ fontSize: 11, color: 'var(--color-text-muted)' }}>reqs</div>
      </div>

      {/* Errors */}
      <div style={{ textAlign: 'right' }}>
        <div style={{
          fontWeight: 600, fontSize: 14,
          color: dep.errors_total > 0 ? '#f87171' : 'var(--color-text-muted)'
        }}>{dep.errors_total}</div>
        <div style={{ fontSize: 11, color: 'var(--color-text-muted)' }}>errors</div>
      </div>

      {/* p50 */}
      <div style={{ textAlign: 'right' }}>
        <div style={{ fontWeight: 600, fontSize: 14, color: 'var(--color-text)' }}>{fmt(dep.latency_p50_ms)}ms</div>
        <div style={{ fontSize: 11, color: 'var(--color-text-muted)' }}>p50</div>
      </div>

      {/* p95 */}
      <div style={{ textAlign: 'right' }}>
        <div style={{ fontWeight: 600, fontSize: 14, color: 'var(--color-text)' }}>{fmt(dep.latency_p95_ms)}ms</div>
        <div style={{ fontSize: 11, color: 'var(--color-text-muted)' }}>p95</div>
      </div>

      {/* Latency bar */}
      <div style={{ paddingTop: 4 }}>
        <LatencyBar value={dep.latency_avg_ms} max={maxLatency} color="var(--color-accent)" />
        <div style={{ fontSize: 10, color: 'var(--color-text-muted)', marginTop: 3 }}>
          avg {fmt(dep.latency_avg_ms)}ms
        </div>
      </div>

      {/* Error rate pill */}
      <div style={{ textAlign: 'right' }}>
        <span style={{
          display: 'inline-block',
          padding: '2px 8px',
          borderRadius: 20,
          fontSize: 11,
          fontWeight: 600,
          background: errorPct > 5 ? 'rgba(239,68,68,0.15)' : errorPct > 0 ? 'rgba(245,158,11,0.15)' : 'rgba(34,197,94,0.1)',
          color: errorPct > 5 ? '#f87171' : errorPct > 0 ? '#fbbf24' : '#86efac',
        }}>
          {fmt(errorPct, 1)}% err
        </span>
      </div>
    </div>
  )
}

// ── Main Page ─────────────────────────────────────────────────────────────────
export default function MonitoringPage() {
  const [summary, setSummary] = useState<MetricsSummary | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [lastRefresh, setLastRefresh] = useState<Date>(new Date())
  const [autoRefresh, setAutoRefresh] = useState(true)

  const load = useCallback(async () => {
    try {
      const data = await metricsApi.getSummary()
      setSummary(data)
      setLastRefresh(new Date())
      setError('')
    } catch {
      setError('Failed to load metrics — is the backend running?')
    } finally {
      setLoading(false)
    }
  }, [])

  // Initial load
  useEffect(() => { load() }, [load])

  // Auto-refresh every 10s
  useEffect(() => {
    if (!autoRefresh) return
    const id = setInterval(load, 10_000)
    return () => clearInterval(id)
  }, [autoRefresh, load])

  const p = summary?.platform
  const maxLatency = summary
    ? Math.max(...summary.deployments.map(d => d.latency_avg_ms), 1)
    : 1

  return (
    <Layout>
      <div style={{ padding: '2rem', maxWidth: 1400, margin: '0 auto' }}>

        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '2rem' }}>
          <div>
            <h1 style={{ fontSize: '1.75rem', fontWeight: 700, color: 'var(--color-text)', margin: 0 }}>
              Monitoring
            </h1>
            <p style={{ color: 'var(--color-text-muted)', marginTop: 4, fontSize: 14 }}>
              Live inference metrics · refreshes every 10s
              {lastRefresh && (
                <span style={{ marginLeft: 12, opacity: 0.6 }}>
                  Last: {lastRefresh.toLocaleTimeString()}
                </span>
              )}
            </p>
          </div>

          <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
            {/* Auto-refresh toggle */}
            <button
              id="toggle-auto-refresh"
              onClick={() => setAutoRefresh(a => !a)}
              style={{
                display: 'flex', alignItems: 'center', gap: 6,
                padding: '0.5rem 1rem', borderRadius: 8, fontSize: 13, fontWeight: 500,
                background: autoRefresh ? 'rgba(99,102,241,0.15)' : 'var(--color-surface)',
                color: autoRefresh ? 'var(--color-accent)' : 'var(--color-text-muted)',
                border: `1px solid ${autoRefresh ? 'rgba(99,102,241,0.3)' : 'var(--color-border)'}`,
                cursor: 'pointer',
              }}>
              <Activity size={13} />
              {autoRefresh ? 'Live' : 'Paused'}
            </button>

            {/* Manual refresh */}
            <button
              id="manual-refresh-btn"
              onClick={load}
              style={{
                display: 'flex', alignItems: 'center', gap: 6,
                padding: '0.5rem 1rem', borderRadius: 8, fontSize: 13, fontWeight: 500,
                background: 'var(--color-surface)', color: 'var(--color-text-muted)',
                border: '1px solid var(--color-border)', cursor: 'pointer',
              }}>
              <RefreshCw size={13} /> Refresh
            </button>

            {/* Grafana link */}
            <a
              href="http://localhost:3001"
              target="_blank"
              rel="noopener noreferrer"
              id="grafana-link"
              style={{
                display: 'flex', alignItems: 'center', gap: 6,
                padding: '0.5rem 1rem', borderRadius: 8, fontSize: 13, fontWeight: 500,
                background: 'rgba(245,158,11,0.1)', color: '#f59e0b',
                border: '1px solid rgba(245,158,11,0.25)', textDecoration: 'none',
              }}>
              <ExternalLink size={13} /> Grafana
            </a>
          </div>
        </div>

        {error && (
          <div style={{
            display: 'flex', gap: '0.75rem', alignItems: 'center',
            padding: '1rem 1.25rem', borderRadius: 10, marginBottom: '1.5rem',
            background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)',
            color: '#f87171', fontSize: 14,
          }}>
            <AlertTriangle size={16} /> {error}
          </div>
        )}

        {loading && !summary ? (
          <div style={{ color: 'var(--color-text-muted)', textAlign: 'center', padding: '4rem' }}>
            Loading metrics…
          </div>
        ) : (
          <>
            {/* Platform stat cards */}
            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
              gap: '1rem',
              marginBottom: '2rem',
            }}>
              <StatCard
                icon={<TrendingUp size={16} />}
                label="Total Requests"
                value={fmt(p?.requests_total ?? 0, 0)}
                sub="all deployments"
                color="#818cf8"
              />
              <StatCard
                icon={<AlertTriangle size={16} />}
                label="Total Errors"
                value={fmt(p?.errors_total ?? 0, 0)}
                sub={`${fmt((p?.error_rate ?? 0) * 100, 2)}% rate`}
                color={p?.errors_total ? '#f87171' : '#6b7280'}
              />
              <StatCard
                icon={<Zap size={16} />}
                label="p50 Latency"
                value={`${fmt(p?.latency_p50_ms ?? 0)}ms`}
                sub="platform-side"
                color="#34d399"
              />
              <StatCard
                icon={<Zap size={16} />}
                label="p95 Latency"
                value={`${fmt(p?.latency_p95_ms ?? 0)}ms`}
                sub="platform-side"
                color="#fbbf24"
              />
              <StatCard
                icon={<Zap size={16} />}
                label="p99 Latency"
                value={`${fmt(p?.latency_p99_ms ?? 0)}ms`}
                sub="platform-side"
                color="#f87171"
              />
            </div>

            {/* Per-deployment table */}
            <div style={{
              background: 'var(--color-surface)',
              border: '1px solid var(--color-border)',
              borderRadius: 16,
              overflow: 'hidden',
            }}>
              {/* Table header */}
              <div style={{
                display: 'grid',
                gridTemplateColumns: '16px 1fr 80px 80px 80px 80px 100px 90px',
                gap: '1rem',
                padding: '0.75rem 1.25rem',
                borderBottom: '1px solid var(--color-border)',
                fontSize: 11,
                fontWeight: 600,
                textTransform: 'uppercase',
                letterSpacing: '0.05em',
                color: 'var(--color-text-muted)',
              }}>
                <div />
                <div>Deployment</div>
                <div style={{ textAlign: 'right' }}>Requests</div>
                <div style={{ textAlign: 'right' }}>Errors</div>
                <div style={{ textAlign: 'right' }}>p50</div>
                <div style={{ textAlign: 'right' }}>p95</div>
                <div>Avg latency</div>
                <div style={{ textAlign: 'right' }}>Error rate</div>
              </div>

              {summary?.deployments.length === 0 ? (
                <div style={{
                  padding: '3rem', textAlign: 'center',
                  color: 'var(--color-text-muted)', fontSize: 14,
                }}>
                  No active deployments · deploy a model to see metrics here
                </div>
              ) : (
                summary?.deployments.map(dep => (
                  <DeploymentRow key={dep.deployment_id} dep={dep} maxLatency={maxLatency} />
                ))
              )}
            </div>

            {/* Grafana CTA */}
            <div style={{
              marginTop: '1.5rem',
              padding: '1rem 1.25rem',
              borderRadius: 10,
              background: 'rgba(245,158,11,0.05)',
              border: '1px solid rgba(245,158,11,0.15)',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
            }}>
              <div>
                <div style={{ fontWeight: 600, color: 'var(--color-text)', fontSize: 14 }}>
                  Grafana dashboards available
                </div>
                <div style={{ color: 'var(--color-text-muted)', fontSize: 12, marginTop: 2 }}>
                  Full time-series histograms, request rate by endpoint, latency percentiles
                </div>
              </div>
              <a
                href="http://localhost:3001"
                target="_blank"
                rel="noopener noreferrer"
                style={{
                  display: 'flex', alignItems: 'center', gap: 6,
                  padding: '0.5rem 1.25rem', borderRadius: 8, fontSize: 13, fontWeight: 600,
                  background: 'rgba(245,158,11,0.15)', color: '#f59e0b',
                  border: '1px solid rgba(245,158,11,0.3)', textDecoration: 'none',
                  whiteSpace: 'nowrap',
                }}>
                Open Grafana <ExternalLink size={12} />
              </a>
            </div>
          </>
        )}
      </div>
    </Layout>
  )
}
