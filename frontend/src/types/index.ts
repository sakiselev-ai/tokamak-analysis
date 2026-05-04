export interface User {
  id: number;
  email: string;
  full_name: string;
  role: 'researcher' | 'engineer' | 'admin';
  is_active: boolean;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface TimeSeries {
  parameter_name: string;
  timestamps: number[];
  values: number[];
  units: string | null;
  description: string | null;
}

export interface Experiment {
  id: number;
  shot_id: number;
  source: string;
  status: string;
  metadata_json: Record<string, unknown> | null;
  loaded_at: string;
  timeseries: TimeSeries[];
}

export interface ClassifyResult {
  experiment_id: number;
  label: string;
  confidence: number;
  inference_time_ms: number;
  model_id: number;
}

export interface DisruptionResult {
  experiment_id: number;
  timestamps: number[];
  probabilities: number[];
  warning_issued: boolean;
  warning_time_ms: number | null;
  inference_time_ms: number;
  model_id: number;
}

export interface ModelRun {
  id: number;
  model_id: number;
  status: string;
  hyperparams_json: Record<string, unknown> | null;
  metrics_json: Record<string, unknown> | null;
  progress: number | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
}

export interface Recommendation {
  action: string;
  priority: 'high' | 'medium' | 'low';
  parameter: string;
  description: string;
  suggested_action: string;
  timeframe_ms: number;
}

export interface BatchLoadResult {
  experiments: Experiment[];
  failed: { shot_id: number; error: string }[];
  total_loaded: number;
}

export interface UserSettings {
  disruption_threshold: number;
  notification_enabled: boolean;
}
