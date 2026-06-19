export interface User {
  id: string
  email: string
  is_active: boolean
}

export interface TokenResponse {
  access_token: string
  token_type: string
}

export interface Project {
  id: string
  name: string
  description: string | null
  created_at: string
  updated_at: string
  model_count: number
}

export interface ProjectCreate {
  name: string
  description?: string
}

export type ModelFramework = 'sklearn' | 'pytorch'
export type ModelStatus = 'uploaded' | 'ready' | 'deprecated'

export interface ModelVersion {
  id: string
  project_id: string
  version_tag: string
  framework: ModelFramework
  original_filename: string
  file_size_bytes: number | null
  description: string | null
  metadata_json: Record<string, unknown> | null
  status: ModelStatus
  created_at: string
  updated_at: string
}

export type DeploymentStatus = 'pending' | 'starting' | 'running' | 'stopped' | 'failed'

export interface ModelVersionSummary {
  id: string
  version_tag: string
  framework: ModelFramework
  original_filename: string
  status: ModelStatus
  project_id: string
}

export interface Deployment {
  id: string
  model_version_id: string
  name: string
  container_id: string | null
  endpoint_url: string | null
  port: number | null
  status: DeploymentStatus
  created_at: string
  stopped_at: string | null
  model_version?: ModelVersionSummary | null
}

export type JobStatus = 'queued' | 'processing' | 'completed' | 'failed'

export interface InferenceJob {
  id: string
  deployment_id: string
  celery_task_id: string | null
  status: JobStatus
  input_payload: Record<string, unknown> | null
  output_payload: Record<string, unknown> | null
  latency_ms: number | null
  error_message: string | null
  created_at: string
  completed_at: string | null
}

export interface DeploymentMetrics {
  deployment_id: string
  deployment_name: string
  status: DeploymentStatus
  port: number | null
  requests_total: number
  errors_total: number
  error_rate: number
  latency_p50_ms: number
  latency_p95_ms: number
  latency_p99_ms: number
  latency_avg_ms: number
}

export interface JobResult {
  job_id: string
  deployment_id: string
  celery_task_id: string | null
  status: JobStatus
  input_payload: { inputs: number[][] } | null
  output_payload: { predictions: unknown[]; latency_ms?: number } | null
  latency_ms: number | null
  error_message: string | null
  created_at: string | null
  completed_at: string | null
}

export interface MetricsSummary {
  platform: {
    requests_total: number
    errors_total: number
    error_rate: number
    latency_p50_ms: number
    latency_p95_ms: number
    latency_p99_ms: number
  }
  deployments: DeploymentMetrics[]
}
