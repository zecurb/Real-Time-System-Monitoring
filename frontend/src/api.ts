import type {
  Anomaly,
  Forecast,
  Health,
  MetricDefinition,
  MetricHistory,
  NodeSummary,
  PipelineStatus,
  Runtime
} from "./types";

async function request<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(path, {
    headers: { Accept: "application/json" },
    signal
  });
  if (!response.ok) {
    throw new Error(`Request failed with HTTP ${response.status}`);
  }
  return (await response.json()) as T;
}

export const api = {
  health: (signal?: AbortSignal) => request<Health>("/health/ready", signal),
  pipeline: (signal?: AbortSignal) =>
    request<PipelineStatus>("/v1/pipeline/status", signal),
  nodes: async (signal?: AbortSignal) =>
    (await request<{ nodes: NodeSummary[] }>("/v1/nodes", signal)).nodes,
  metrics: async (signal?: AbortSignal) =>
    (await request<{ metrics: MetricDefinition[] }>("/v1/metrics", signal)).metrics,
  history: (
    nodeId: string,
    metric: string,
    start: Date,
    end: Date,
    signal?: AbortSignal
  ) => {
    const params = new URLSearchParams({
      metric,
      start: start.toISOString(),
      end: end.toISOString(),
      limit: "5000"
    });
    return request<MetricHistory>(
      `/v1/metrics/${encodeURIComponent(nodeId)}?${params}`,
      signal
    );
  },
  anomalies: async (start: Date, end: Date, signal?: AbortSignal) => {
    const params = new URLSearchParams({
      start: start.toISOString(),
      end: end.toISOString(),
      limit: "100"
    });
    return (
      await request<{ anomalies: Anomaly[] }>(`/v1/anomalies?${params}`, signal)
    ).anomalies;
  },
  forecasts: async (signal?: AbortSignal) =>
    (await request<{ forecasts: Forecast[] }>("/v1/forecasts", signal)).forecasts,
  runtime: (signal?: AbortSignal) => request<Runtime>("/v1/runtime", signal)
};
