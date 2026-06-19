import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import Layout from '../components/Layout'
import { projectsApi } from '../api'
import type { Project } from '../types'
import {
  Plus, FolderOpen, Trash2, ChevronRight, Brain, X, AlertCircle
} from 'lucide-react'

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

function formatSize(count: number) {
  return `${count} model${count !== 1 ? 's' : ''}`
}

export default function Dashboard() {
  const navigate = useNavigate()
  const [projects, setProjects] = useState<Project[]>([])
  const [loading, setLoading] = useState(true)
  const [showModal, setShowModal] = useState(false)
  const [form, setForm] = useState({ name: '', description: '' })
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    loadProjects()
  }, [])

  const loadProjects = async () => {
    try {
      const data = await projectsApi.list()
      setProjects(data)
    } catch {
      // handled by interceptor
    } finally {
      setLoading(false)
    }
  }

  const handleCreate = async () => {
    if (!form.name.trim()) return
    setCreating(true)
    setError('')
    try {
      const project = await projectsApi.create({ name: form.name, description: form.description || undefined })
      setProjects([project, ...projects])
      setShowModal(false)
      setForm({ name: '', description: '' })
    } catch {
      setError('Failed to create project. Please try again.')
    } finally {
      setCreating(false)
    }
  }

  const handleDelete = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation()
    if (!confirm('Delete this project and all its models?')) return
    try {
      await projectsApi.delete(id)
      setProjects(projects.filter(p => p.id !== id))
    } catch {
      alert('Failed to delete project.')
    }
  }

  return (
    <Layout activePage="dashboard">
      <div className="p-8">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-2xl font-bold" style={{ color: 'var(--color-text-primary)' }}>
              Projects
            </h1>
            <p className="text-sm mt-1" style={{ color: 'var(--color-text-secondary)' }}>
              {projects.length} project{projects.length !== 1 ? 's' : ''} in your workspace
            </p>
          </div>
          <button
            id="create-project-btn"
            onClick={() => setShowModal(true)}
            className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200"
            style={{
              background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
              color: 'white',
              boxShadow: '0 0 20px rgba(99,102,241,0.25)',
            }}
          >
            <Plus size={16} />
            New Project
          </button>
        </div>

        {/* Loading */}
        {loading && (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {[1, 2, 3].map(i => (
              <div key={i} className="h-40 rounded-xl animate-pulse" style={{ background: 'var(--color-bg-card)' }} />
            ))}
          </div>
        )}

        {/* Empty state */}
        {!loading && projects.length === 0 && (
          <div className="flex flex-col items-center justify-center py-24 text-center">
            <div className="w-16 h-16 rounded-2xl flex items-center justify-center mb-4" style={{
              background: 'var(--color-bg-card)',
              border: '1px solid var(--color-border)',
            }}>
              <Brain size={28} style={{ color: 'var(--color-text-muted)' }} />
            </div>
            <p className="text-base font-medium mb-1" style={{ color: 'var(--color-text-secondary)' }}>
              No projects yet
            </p>
            <p className="text-sm mb-4" style={{ color: 'var(--color-text-muted)' }}>
              Create your first project to start uploading models
            </p>
            <button
              onClick={() => setShowModal(true)}
              className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium"
              style={{ background: 'var(--color-bg-card)', color: 'var(--color-accent-hover)', border: '1px solid var(--color-border)' }}
            >
              <Plus size={16} /> Create project
            </button>
          </div>
        )}

        {/* Project grid */}
        {!loading && projects.length > 0 && (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {projects.map((project) => (
              <div
                key={project.id}
                id={`project-card-${project.id}`}
                onClick={() => navigate(`/projects/${project.id}`)}
                className="group p-5 rounded-xl border cursor-pointer transition-all duration-200"
                style={{
                  background: 'var(--color-bg-card)',
                  borderColor: 'var(--color-border)',
                }}
                onMouseEnter={(e) => {
                  (e.currentTarget as HTMLElement).style.borderColor = 'var(--color-accent)'
                  ;(e.currentTarget as HTMLElement).style.transform = 'translateY(-2px)'
                  ;(e.currentTarget as HTMLElement).style.boxShadow = '0 8px 30px rgba(99,102,241,0.15)'
                }}
                onMouseLeave={(e) => {
                  (e.currentTarget as HTMLElement).style.borderColor = 'var(--color-border)'
                  ;(e.currentTarget as HTMLElement).style.transform = 'translateY(0)'
                  ;(e.currentTarget as HTMLElement).style.boxShadow = 'none'
                }}
              >
                <div className="flex items-start justify-between mb-3">
                  <div className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-lg flex items-center justify-center" style={{
                      background: 'rgba(99,102,241,0.15)',
                    }}>
                      <FolderOpen size={18} style={{ color: 'var(--color-accent-hover)' }} />
                    </div>
                    <div>
                      <h3 className="font-semibold text-sm leading-tight" style={{ color: 'var(--color-text-primary)' }}>
                        {project.name}
                      </h3>
                      <p className="text-xs mt-0.5" style={{ color: 'var(--color-text-muted)' }}>
                        {formatDate(project.created_at)}
                      </p>
                    </div>
                  </div>
                  <button
                    id={`delete-project-${project.id}`}
                    onClick={(e) => handleDelete(project.id, e)}
                    className="opacity-0 group-hover:opacity-100 p-1.5 rounded-lg transition-all"
                    style={{ color: 'var(--color-text-muted)' }}
                    onMouseEnter={(e) => {
                      (e.currentTarget as HTMLElement).style.color = 'var(--color-error)'
                      ;(e.currentTarget as HTMLElement).style.background = 'rgba(239,68,68,0.1)'
                    }}
                    onMouseLeave={(e) => {
                      (e.currentTarget as HTMLElement).style.color = 'var(--color-text-muted)'
                      ;(e.currentTarget as HTMLElement).style.background = 'transparent'
                    }}
                  >
                    <Trash2 size={14} />
                  </button>
                </div>

                {project.description && (
                  <p className="text-xs mb-3 line-clamp-2" style={{ color: 'var(--color-text-secondary)' }}>
                    {project.description}
                  </p>
                )}

                <div className="flex items-center justify-between">
                  <span className="px-2 py-0.5 rounded-full text-xs font-medium" style={{
                    background: 'rgba(16,185,129,0.1)',
                    color: 'var(--color-success)',
                  }}>
                    {formatSize(project.model_count)}
                  </span>
                  <ChevronRight size={14} className="opacity-0 group-hover:opacity-100 transition-opacity" style={{ color: 'var(--color-accent)' }} />
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Create project modal */}
      {showModal && (
        <div
          className="fixed inset-0 flex items-center justify-center z-50"
          style={{ background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(4px)' }}
          onClick={(e) => { if (e.target === e.currentTarget) setShowModal(false) }}
        >
          <div className="w-full max-w-md mx-4 rounded-2xl p-6 border" style={{
            background: 'var(--color-bg-card)',
            borderColor: 'var(--color-border)',
            boxShadow: '0 25px 60px rgba(0,0,0,0.5)',
          }}>
            <div className="flex items-center justify-between mb-5">
              <h2 className="text-base font-semibold" style={{ color: 'var(--color-text-primary)' }}>
                Create new project
              </h2>
              <button onClick={() => setShowModal(false)} style={{ color: 'var(--color-text-muted)' }}>
                <X size={18} />
              </button>
            </div>

            {error && (
              <div className="flex items-center gap-2 p-3 rounded-lg mb-4 text-sm" style={{
                background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)', color: 'var(--color-error)',
              }}>
                <AlertCircle size={14} />{error}
              </div>
            )}

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-1.5" style={{ color: 'var(--color-text-secondary)' }}>
                  Project name *
                </label>
                <input
                  id="project-name-input"
                  type="text"
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  placeholder="e.g. Fraud Detection"
                  className="w-full px-3 py-2.5 rounded-lg text-sm outline-none"
                  style={{
                    background: 'var(--color-bg-secondary)',
                    border: '1px solid var(--color-border)',
                    color: 'var(--color-text-primary)',
                  }}
                  onKeyDown={(e) => e.key === 'Enter' && handleCreate()}
                  autoFocus
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1.5" style={{ color: 'var(--color-text-secondary)' }}>
                  Description
                </label>
                <textarea
                  id="project-description-input"
                  value={form.description}
                  onChange={(e) => setForm({ ...form, description: e.target.value })}
                  placeholder="What is this project for?"
                  rows={3}
                  className="w-full px-3 py-2.5 rounded-lg text-sm outline-none resize-none"
                  style={{
                    background: 'var(--color-bg-secondary)',
                    border: '1px solid var(--color-border)',
                    color: 'var(--color-text-primary)',
                  }}
                />
              </div>
            </div>

            <div className="flex gap-3 mt-6">
              <button
                onClick={() => setShowModal(false)}
                className="flex-1 py-2.5 rounded-lg text-sm font-medium transition-all"
                style={{ background: 'var(--color-bg-secondary)', color: 'var(--color-text-secondary)', border: '1px solid var(--color-border)' }}
              >
                Cancel
              </button>
              <button
                id="create-project-confirm-btn"
                onClick={handleCreate}
                disabled={creating || !form.name.trim()}
                className="flex-1 py-2.5 rounded-lg text-sm font-semibold transition-all"
                style={{
                  background: creating || !form.name.trim() ? 'var(--color-border)' : 'linear-gradient(135deg, #6366f1, #8b5cf6)',
                  color: 'white',
                  cursor: creating || !form.name.trim() ? 'not-allowed' : 'pointer',
                }}
              >
                {creating ? 'Creating...' : 'Create project'}
              </button>
            </div>
          </div>
        </div>
      )}
    </Layout>
  )
}
