import api from './client'
import type { User, TokenResponse, Project, ProjectCreate, ModelVersion, Deployment, MetricsSummary, JobResult } from '../types'

// ── Auth ────────────────────────────────────────────────────
export const authApi = {
  login: async (email: string, password: string): Promise<TokenResponse> => {
    const { data } = await api.post('/auth/login', { email, password })
    return data
  },
  register: async (email: string, password: string): Promise<User> => {
    const { data } = await api.post('/auth/register', { email, password })
    return data
  },
  me: async (): Promise<User> => {
    const { data } = await api.get('/auth/me')
    return data
  },
}

// ── Projects ─────────────────────────────────────────────────
export const projectsApi = {
  list: async (): Promise<Project[]> => {
    const { data } = await api.get('/projects')
    return data
  },
  get: async (id: string): Promise<Project> => {
    const { data } = await api.get(`/projects/${id}`)
    return data
  },
  create: async (payload: ProjectCreate): Promise<Project> => {
    const { data } = await api.post('/projects', payload)
    return data
  },
  delete: async (id: string): Promise<void> => {
    await api.delete(`/projects/${id}`)
  },
}

// ── Model Registry ───────────────────────────────────────────
export const registryApi = {
  listModels: async (projectId: string): Promise<ModelVersion[]> => {
    const { data } = await api.get(`/projects/${projectId}/models`)
    return data
  },
  getModel: async (modelId: string): Promise<ModelVersion> => {
    const { data } = await api.get(`/models/${modelId}`)
    return data
  },
  uploadModel: async (
    projectId: string,
    formData: FormData,
    onProgress?: (pct: number) => void
  ): Promise<ModelVersion> => {
    const { data } = await api.post(`/projects/${projectId}/models`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (evt) => {
        if (evt.total && onProgress) {
          onProgress(Math.round((evt.loaded * 100) / evt.total))
        }
      },
    })
    return data
  },
  deleteModel: async (modelId: string): Promise<void> => {
    await api.delete(`/models/${modelId}`)
  },
}

// ── Deployments ──────────────────────────────────────────────
export const deploymentsApi = {
  deploy: async (modelId: string, name: string): Promise<Deployment> => {
    const { data } = await api.post(`/deployments/models/${modelId}/deploy`, { name })
    return data
  },
  list: async (): Promise<Deployment[]> => {
    const { data } = await api.get('/deployments')
    return data
  },
  get: async (id: string): Promise<Deployment> => {
    const { data } = await api.get(`/deployments/${id}`)
    return data
  },
  stop: async (id: string): Promise<Deployment> => {
    const { data } = await api.post(`/deployments/${id}/stop`)
    return data
  },
  rollback: async (id: string): Promise<Deployment> => {
    const { data } = await api.post(`/deployments/${id}/rollback`)
    return data
  },
  getLogs: async (id: string): Promise<{ logs: string }> => {
    const { data } = await api.get(`/deployments/${id}/logs`)
    return data
  },
  predict: async (
    id: string,
    inputs: number[][]
  ): Promise<{ predictions: unknown[]; latency_ms: number }> => {
    const { data } = await api.post(`/deployments/${id}/predict`, { inputs })
    return data
  },
  recover: async (id: string): Promise<Deployment> => {
    const { data } = await api.post(`/deployments/${id}/recover`)
    return data
  },
}

// ── Metrics ──────────────────────────────────────────────────
export const metricsApi = {
  getSummary: async (): Promise<MetricsSummary> => {
    const { data } = await api.get('/metrics/summary')
    return data
  },
}

// ── Async Jobs ───────────────────────────────────────────────
export const jobsApi = {
  submit: async (deploymentId: string, inputs: number[][]): Promise<{ job_id: string; status: string }> => {
    const { data } = await api.post(`/deployments/${deploymentId}/predict/async`, { inputs })
    return data
  },
  get: async (jobId: string): Promise<JobResult> => {
    const { data } = await api.get(`/jobs/${jobId}`)
    return data
  },
  list: async (deploymentId: string): Promise<JobResult[]> => {
    const { data } = await api.get(`/deployments/${deploymentId}/jobs`)
    return data
  },
}
