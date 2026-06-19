import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import Layout from '../components/Layout'
import { projectsApi, registryApi, deploymentsApi } from '../api'
import type { Project, ModelVersion } from '../types'
import {
  ArrowLeft, Upload, Trash2, CheckCircle, AlertCircle,
  Brain, X, ChevronDown, FileCode, Rocket, Loader
} from 'lucide-react'

function formatBytes(bytes: number | null): string {
  if (!bytes) return '—'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit' })
}

const STATUS_STYLES: Record<string, { bg: string; color: string; label: string }> = {
  ready:      { bg: 'rgba(16,185,129,0.1)',  color: '#10b981', label: 'Ready' },
  uploaded:   { bg: 'rgba(245,158,11,0.1)',  color: '#f59e0b', label: 'Uploaded' },
  deprecated: { bg: 'rgba(100,116,139,0.1)', color: '#64748b', label: 'Deprecated' },
}

const FRAMEWORK_STYLES: Record<string, { bg: string; color: string }> = {
  sklearn: { bg: 'rgba(59,130,246,0.1)', color: '#60a5fa' },
  pytorch: { bg: 'rgba(239,68,68,0.1)',  color: '#f87171' },
}

// ── Deploy Modal ──────────────────────────────────────────────────────
function DeployModal({
  model,
  onClose,
  onDeployed,
}: {
  model: ModelVersion
  onClose: () => void
  onDeployed: () => void
}) {
  const navigate = useNavigate()
  const [deployName, setDeployName] = useState(`${model.version_tag}-deploy`)
  const [deploying, setDeploying] = useState(false)
  const [error, setError] = useState('')

  const handleDeploy = async () => {
    if (!deployName.trim()) return
    setDeploying(true)
    setError('')
    try {
      await deploymentsApi.deploy(model.id, deployName.trim())
      onDeployed()
      navigate('/deployments')
    } catch (e: unknown) {
      const msg = typeof e === 'object' && e !== null && 'response' in e
        ? (e as { response?: { data?: { detail?: string } } }).response?.data?.detail
        : 'Deployment failed'
      setError(String(msg ?? 'Deployment failed'))
      setDeploying(false)
    }
  }

  return (
    <div
      className="fixed inset-0 flex items-center justify-center z-50"
      style={{ background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(4px)' }}
      onClick={e => { if (e.target === e.currentTarget) onClose() }}
    >
      <div className="w-full max-w-sm mx-4 rounded-2xl p-6 border" style={{
        background: 'var(--color-bg-card)',
        borderColor: 'var(--color-border)',
        boxShadow: '0 25px 60px rgba(0,0,0,0.5)',
      }}>
        <div className="flex items-center justify-between mb-5">
          <div>
            <h2 className="text-base font-semibold" style={{ color: 'var(--color-text-primary)' }}>Deploy Model</h2>
            <p className="text-xs mt-0.5" style={{ color: 'var(--color-text-muted)' }}>
              {model.version_tag} · {model.framework}
            </p>
          </div>
          <button onClick={onClose} style={{ color: 'var(--color-text-muted)' }}><X size={18} /></button>
        </div>

        {error && (
          <div className="flex items-start gap-2 p-3 rounded-lg mb-4 text-sm"
            style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)', color: 'var(--color-error)' }}>
            <AlertCircle size={14} className="mt-0.5 shrink-0" />{error}
          </div>
        )}

        {/* Info box */}
        <div className="rounded-lg p-3 mb-4 text-xs" style={{ background: 'rgba(99,102,241,0.08)', border: '1px solid rgba(99,102,241,0.2)', color: 'var(--color-text-secondary)' }}>
          A Docker container will start in the background. You can monitor progress in the{' '}
          <strong style={{ color: 'var(--color-accent-hover)' }}>Deployments</strong> tab.
        </div>

        <div className="mb-5">
          <label className="block text-sm font-medium mb-1.5" style={{ color: 'var(--color-text-secondary)' }}>
            Deployment name
          </label>
          <input
            id="deploy-name-input"
            type="text"
            value={deployName}
            onChange={e => setDeployName(e.target.value)}
            className="w-full px-3 py-2.5 rounded-lg text-sm outline-none"
            style={{
              background: 'var(--color-bg-secondary)',
              border: '1px solid var(--color-border)',
              color: 'var(--color-text-primary)',
            }}
            onFocus={e => (e.target.style.borderColor = 'var(--color-accent)')}
            onBlur={e => (e.target.style.borderColor = 'var(--color-border)')}
          />
        </div>

        <div className="flex gap-3">
          <button
            onClick={onClose}
            disabled={deploying}
            className="flex-1 py-2.5 rounded-lg text-sm font-medium"
            style={{ background: 'var(--color-bg-secondary)', color: 'var(--color-text-secondary)', border: '1px solid var(--color-border)' }}
          >
            Cancel
          </button>
          <button
            id="confirm-deploy-btn"
            onClick={handleDeploy}
            disabled={deploying || !deployName.trim()}
            className="flex-1 py-2.5 rounded-lg text-sm font-semibold flex items-center justify-center gap-2"
            style={{
              background: (deploying || !deployName.trim()) ? 'var(--color-border)' : 'linear-gradient(135deg, #10b981, #059669)',
              color: 'white',
              cursor: (deploying || !deployName.trim()) ? 'not-allowed' : 'pointer',
              boxShadow: deploying ? 'none' : '0 0 20px rgba(16,185,129,0.2)',
            }}
          >
            {deploying ? <><Loader size={14} className="animate-spin" /> Deploying...</> : <><Rocket size={14} /> Deploy</>}
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────
export default function ProjectDetail() {
  const { projectId } = useParams<{ projectId: string }>()
  const navigate = useNavigate()
  const [project, setProject] = useState<Project | null>(null)
  const [models, setModels] = useState<ModelVersion[]>([])
  const [loading, setLoading] = useState(true)
  const [showUpload, setShowUpload] = useState(false)
  const [deployTarget, setDeployTarget] = useState<ModelVersion | null>(null)

  // Upload form state
  const [uploadFile, setUploadFile] = useState<File | null>(null)
  const [uploadForm, setUploadForm] = useState({ version_tag: '', framework: 'sklearn', description: '' })
  const [uploading, setUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [uploadError, setUploadError] = useState('')
  const fileInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (projectId) loadData()
  }, [projectId])

  const loadData = async () => {
    try {
      const [proj, mods] = await Promise.all([
        projectsApi.get(projectId!),
        registryApi.listModels(projectId!),
      ])
      setProject(proj)
      setModels(mods)
    } catch {
      navigate('/dashboard')
    } finally {
      setLoading(false)
    }
  }

  const handleUpload = async () => {
    if (!uploadFile || !uploadForm.version_tag) return
    setUploading(true)
    setUploadError('')
    setUploadProgress(0)
    const formData = new FormData()
    formData.append('file', uploadFile)
    formData.append('version_tag', uploadForm.version_tag)
    formData.append('framework', uploadForm.framework)
    if (uploadForm.description) formData.append('description', uploadForm.description)
    try {
      const model = await registryApi.uploadModel(projectId!, formData, setUploadProgress)
      setModels([model, ...models])
      setShowUpload(false)
      setUploadFile(null)
      setUploadForm({ version_tag: '', framework: 'sklearn', description: '' })
    } catch (err: unknown) {
      const detail = typeof err === 'object' && err !== null && 'response' in err
        ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
        : 'Upload failed'
      setUploadError(String(detail ?? 'Upload failed. Please try again.'))
    } finally {
      setUploading(false)
    }
  }

  const handleDelete = async (modelId: string) => {
    if (!confirm('Delete this model version and its artifact?')) return
    try {
      await registryApi.deleteModel(modelId)
      setModels(models.filter(m => m.id !== modelId))
    } catch {
      alert('Failed to delete model.')
    }
  }

  if (loading) {
    return (
      <Layout activePage="projects">
        <div className="flex items-center justify-center h-full">
          <div className="text-sm" style={{ color: 'var(--color-text-muted)' }}>Loading...</div>
        </div>
      </Layout>
    )
  }

  return (
    <Layout activePage="projects">
      <div className="p-8">
        {/* Breadcrumb */}
        <button
          onClick={() => navigate('/dashboard')}
          className="flex items-center gap-2 text-sm mb-6 transition-colors"
          style={{ color: 'var(--color-text-muted)' }}
          onMouseEnter={e => ((e.currentTarget as HTMLElement).style.color = 'var(--color-text-primary)')}
          onMouseLeave={e => ((e.currentTarget as HTMLElement).style.color = 'var(--color-text-muted)')}
        >
          <ArrowLeft size={14} />
          Back to projects
        </button>

        {/* Header */}
        <div className="flex items-start justify-between mb-8">
          <div>
            <h1 className="text-2xl font-bold" style={{ color: 'var(--color-text-primary)' }}>{project?.name}</h1>
            {project?.description && (
              <p className="text-sm mt-1" style={{ color: 'var(--color-text-secondary)' }}>{project.description}</p>
            )}
            <p className="text-xs mt-2" style={{ color: 'var(--color-text-muted)' }}>
              {models.length} model version{models.length !== 1 ? 's' : ''}
            </p>
          </div>
          <button
            id="upload-model-btn"
            onClick={() => setShowUpload(true)}
            className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium"
            style={{
              background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
              color: 'white',
              boxShadow: '0 0 20px rgba(99,102,241,0.25)',
            }}
          >
            <Upload size={15} />
            Upload Model
          </button>
        </div>

        {/* Model table */}
        {models.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-24 text-center">
            <Brain size={32} className="mb-3" style={{ color: 'var(--color-text-muted)' }} />
            <p className="text-sm font-medium mb-1" style={{ color: 'var(--color-text-secondary)' }}>No models uploaded yet</p>
            <p className="text-xs" style={{ color: 'var(--color-text-muted)' }}>Upload a .pkl, .joblib, .pt, or .pth file to get started</p>
          </div>
        ) : (
          <div className="rounded-xl border overflow-hidden" style={{ background: 'var(--color-bg-card)', borderColor: 'var(--color-border)' }}>
            {/* Table header */}
            <div className="grid px-5 py-3 text-xs font-semibold uppercase tracking-wider border-b" style={{
              gridTemplateColumns: '1fr 100px 80px 100px 160px 130px',
              color: 'var(--color-text-muted)',
              borderColor: 'var(--color-border)',
            }}>
              <span>Version</span>
              <span>Framework</span>
              <span>Size</span>
              <span>Status</span>
              <span>Uploaded</span>
              <span>Actions</span>
            </div>

            {/* Table rows */}
            {models.map((model, idx) => {
              const statusStyle = STATUS_STYLES[model.status] || STATUS_STYLES.ready
              const frameworkStyle = FRAMEWORK_STYLES[model.framework] || FRAMEWORK_STYLES.sklearn
              return (
                <div
                  key={model.id}
                  id={`model-row-${model.id}`}
                  className="group grid px-5 py-4 items-center border-b last:border-0 transition-colors"
                  style={{
                    gridTemplateColumns: '1fr 100px 80px 100px 160px 130px',
                    borderColor: 'var(--color-border)',
                  }}
                  onMouseEnter={e => ((e.currentTarget as HTMLElement).style.background = 'rgba(255,255,255,0.02)')}
                  onMouseLeave={e => ((e.currentTarget as HTMLElement).style.background = 'transparent')}
                >
                  <div>
                    <div className="flex items-center gap-2">
                      <FileCode size={14} style={{ color: 'var(--color-text-muted)' }} />
                      <span className="text-sm font-medium" style={{ color: 'var(--color-text-primary)' }}>{model.version_tag}</span>
                      {idx === 0 && (
                        <span className="px-1.5 py-0.5 rounded text-xs" style={{ background: 'rgba(99,102,241,0.2)', color: 'var(--color-accent-hover)' }}>
                          latest
                        </span>
                      )}
                    </div>
                    <div className="text-xs mt-0.5 truncate" style={{ color: 'var(--color-text-muted)', maxWidth: '200px' }}>
                      {model.original_filename}
                    </div>
                  </div>

                  <span className="px-2 py-1 rounded-md text-xs font-medium w-fit" style={frameworkStyle}>{model.framework}</span>
                  <span className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>{formatBytes(model.file_size_bytes)}</span>
                  <span className="px-2 py-1 rounded-full text-xs font-medium w-fit" style={{ background: statusStyle.bg, color: statusStyle.color }}>{statusStyle.label}</span>
                  <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>{formatDate(model.created_at)}</span>

                  {/* Actions */}
                  <div className="flex items-center gap-1.5">
                    <button
                      id={`deploy-model-${model.id}`}
                      onClick={() => setDeployTarget(model)}
                      className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-medium transition-all opacity-0 group-hover:opacity-100"
                      style={{ background: 'rgba(16,185,129,0.12)', color: '#10b981', border: '1px solid rgba(16,185,129,0.25)' }}
                      onMouseEnter={e => ((e.currentTarget as HTMLElement).style.background = 'rgba(16,185,129,0.22)')}
                      onMouseLeave={e => ((e.currentTarget as HTMLElement).style.background = 'rgba(16,185,129,0.12)')}
                    >
                      <Rocket size={11} /> Deploy
                    </button>
                    <button
                      id={`delete-model-${model.id}`}
                      onClick={() => handleDelete(model.id)}
                      className="opacity-0 group-hover:opacity-100 p-1.5 rounded-lg transition-all"
                      style={{ color: 'var(--color-text-muted)' }}
                      onMouseEnter={e => {
                        (e.currentTarget as HTMLElement).style.color = 'var(--color-error)'
                        ;(e.currentTarget as HTMLElement).style.background = 'rgba(239,68,68,0.1)'
                      }}
                      onMouseLeave={e => {
                        (e.currentTarget as HTMLElement).style.color = 'var(--color-text-muted)'
                        ;(e.currentTarget as HTMLElement).style.background = 'transparent'
                      }}
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* Upload modal */}
      {showUpload && (
        <div
          className="fixed inset-0 flex items-center justify-center z-50"
          style={{ background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(4px)' }}
          onClick={e => { if (e.target === e.currentTarget) setShowUpload(false) }}
        >
          <div className="w-full max-w-md mx-4 rounded-2xl p-6 border" style={{
            background: 'var(--color-bg-card)',
            borderColor: 'var(--color-border)',
            boxShadow: '0 25px 60px rgba(0,0,0,0.5)',
          }}>
            <div className="flex items-center justify-between mb-5">
              <h2 className="text-base font-semibold" style={{ color: 'var(--color-text-primary)' }}>Upload model version</h2>
              <button onClick={() => setShowUpload(false)} style={{ color: 'var(--color-text-muted)' }}><X size={18} /></button>
            </div>

            {uploadError && (
              <div className="flex items-center gap-2 p-3 rounded-lg mb-4 text-sm" style={{
                background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)', color: 'var(--color-error)',
              }}>
                <AlertCircle size={14} />{uploadError}
              </div>
            )}

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-1.5" style={{ color: 'var(--color-text-secondary)' }}>Model file *</label>
                <div
                  onClick={() => fileInputRef.current?.click()}
                  className="flex flex-col items-center justify-center p-6 rounded-xl border-2 border-dashed cursor-pointer transition-all"
                  style={{ background: uploadFile ? 'rgba(99,102,241,0.05)' : 'var(--color-bg-secondary)', borderColor: uploadFile ? 'var(--color-accent)' : 'var(--color-border)' }}
                >
                  {uploadFile ? (
                    <>
                      <CheckCircle size={24} style={{ color: 'var(--color-success)' }} className="mb-2" />
                      <p className="text-sm font-medium" style={{ color: 'var(--color-text-primary)' }}>{uploadFile.name}</p>
                      <p className="text-xs mt-0.5" style={{ color: 'var(--color-text-muted)' }}>{formatBytes(uploadFile.size)}</p>
                    </>
                  ) : (
                    <>
                      <Upload size={24} className="mb-2" style={{ color: 'var(--color-text-muted)' }} />
                      <p className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>Click to select file</p>
                      <p className="text-xs mt-0.5" style={{ color: 'var(--color-text-muted)' }}>.pkl .joblib .pt .pth</p>
                    </>
                  )}
                  <input ref={fileInputRef} type="file" accept=".pkl,.joblib,.pt,.pth" className="hidden" onChange={e => setUploadFile(e.target.files?.[0] || null)} />
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium mb-1.5" style={{ color: 'var(--color-text-secondary)' }}>Version tag *</label>
                <input
                  id="version-tag-input"
                  type="text"
                  value={uploadForm.version_tag}
                  onChange={e => setUploadForm({ ...uploadForm, version_tag: e.target.value })}
                  placeholder="e.g. v1.0, v2.1-hotfix"
                  className="w-full px-3 py-2.5 rounded-lg text-sm outline-none"
                  style={{ background: 'var(--color-bg-secondary)', border: '1px solid var(--color-border)', color: 'var(--color-text-primary)' }}
                />
              </div>

              <div>
                <label className="block text-sm font-medium mb-1.5" style={{ color: 'var(--color-text-secondary)' }}>Framework *</label>
                <div className="relative">
                  <select
                    id="framework-select"
                    value={uploadForm.framework}
                    onChange={e => setUploadForm({ ...uploadForm, framework: e.target.value })}
                    className="w-full px-3 py-2.5 rounded-lg text-sm outline-none appearance-none"
                    style={{ background: 'var(--color-bg-secondary)', border: '1px solid var(--color-border)', color: 'var(--color-text-primary)' }}
                  >
                    <option value="sklearn">scikit-learn (.pkl, .joblib)</option>
                    <option value="pytorch">PyTorch (.pt, .pth)</option>
                  </select>
                  <ChevronDown size={14} className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none" style={{ color: 'var(--color-text-muted)' }} />
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium mb-1.5" style={{ color: 'var(--color-text-secondary)' }}>Description</label>
                <textarea
                  id="model-description-input"
                  value={uploadForm.description}
                  onChange={e => setUploadForm({ ...uploadForm, description: e.target.value })}
                  placeholder="Accuracy, training dataset, hyperparameters..."
                  rows={2}
                  className="w-full px-3 py-2.5 rounded-lg text-sm outline-none resize-none"
                  style={{ background: 'var(--color-bg-secondary)', border: '1px solid var(--color-border)', color: 'var(--color-text-primary)' }}
                />
              </div>
            </div>

            {uploading && (
              <div className="mt-4">
                <div className="flex justify-between text-xs mb-1" style={{ color: 'var(--color-text-muted)' }}>
                  <span>Uploading...</span><span>{uploadProgress}%</span>
                </div>
                <div className="w-full h-1.5 rounded-full overflow-hidden" style={{ background: 'var(--color-border)' }}>
                  <div className="h-full rounded-full transition-all duration-300" style={{ width: `${uploadProgress}%`, background: 'linear-gradient(90deg, #6366f1, #8b5cf6)' }} />
                </div>
              </div>
            )}

            <div className="flex gap-3 mt-6">
              <button
                onClick={() => setShowUpload(false)}
                disabled={uploading}
                className="flex-1 py-2.5 rounded-lg text-sm font-medium"
                style={{ background: 'var(--color-bg-secondary)', color: 'var(--color-text-secondary)', border: '1px solid var(--color-border)' }}
              >
                Cancel
              </button>
              <button
                id="upload-confirm-btn"
                onClick={handleUpload}
                disabled={uploading || !uploadFile || !uploadForm.version_tag}
                className="flex-1 py-2.5 rounded-lg text-sm font-semibold transition-all"
                style={{
                  background: (uploading || !uploadFile || !uploadForm.version_tag) ? 'var(--color-border)' : 'linear-gradient(135deg, #6366f1, #8b5cf6)',
                  color: 'white',
                  cursor: (uploading || !uploadFile || !uploadForm.version_tag) ? 'not-allowed' : 'pointer',
                }}
              >
                {uploading ? `Uploading ${uploadProgress}%` : 'Upload'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Deploy modal */}
      {deployTarget && (
        <DeployModal
          model={deployTarget}
          onClose={() => setDeployTarget(null)}
          onDeployed={() => setDeployTarget(null)}
        />
      )}
    </Layout>
  )
}
