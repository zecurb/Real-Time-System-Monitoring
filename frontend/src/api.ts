import type {
  Anomaly,
  Forecast,
  Health,
  Incident,
  MetricDefinition,
  MetricHistory,
  NodeSummary,
  PipelineStatus,
  Runtime
} from "./types";

async function request<T>(
  path: string,
  signal?: AbortSignal,
  init?: RequestInit
): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: {
      Accept: "application/json",
      ...init?.headers
    },
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
  incidents: async (signal?: AbortSignal) =>
    (await request<{ incidents: Incident[] }>("/v1/incidents", signal)).incidents,
  acknowledgeIncident: (
    incidentId: string,
    actor: string,
    expectedRevision: number
  ) =>
    request<Incident>(`/v1/incidents/${incidentId}/acknowledge`, undefined, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        actor,
        note: "Acknowledged from incident console",
        expected_revision: expectedRevision
      })
    }),
  resolveIncident: (
    incidentId: string,
    actor: string,
    note: string,
    expectedRevision: number
  ) =>
    request<Incident>(`/v1/incidents/${incidentId}/resolve`, undefined, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        actor,
        note,
        expected_revision: expectedRevision
      })
    }),
  runtime: (signal?: AbortSignal) => request<Runtime>("/v1/runtime", signal)
};
