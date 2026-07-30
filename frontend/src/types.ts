export interface Health {
  status: "ok" | "ready" | "not_ready";
  storage: "unchecked" | "available" | "unavailable";
}

export interface PipelineStatus {
  pending: number;
  processing: number;
  retry: number;
  processed: number;
  dead_letter: number;
  active_depth: number;
}

export interface NodeSummary {
  node_id: string;
  last_seen: string;
  event_count: number;
}

export interface MetricDefinition {
  name: string;
  display_name: string;
  unit: string;
  category: string;
}

export interface MetricPoint {
  event_id: string;
  observed_at: string;
  value: number;
  labels: Record<string, string>;
}

export interface MetricHistory {
  node_id: string;
  metric_name: string;
  start: string;
  end: string;
  points: MetricPoint[];
  next_cursor: string | null;
}

export interface Anomaly {
  event_id: string;
  node_id: string;
  metric_name: string;
  observed_at: string;
  value: number;
  baseline: number;
  dispersion: number;
  score: number;
  severity: "warning" | "critical";
  sample_count: number;
}
