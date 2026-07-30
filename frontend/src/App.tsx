import { useEffect, useMemo, useState } from "react";

import { api } from "./api";
import { formatValue, MetricChart } from "./components/MetricChart";
import type {
  Anomaly,
  Health,
  MetricDefinition,
  MetricHistory,
  NodeSummary,
  PipelineStatus
} from "./types";
import "./styles.css";

const REFRESH_INTERVAL_MS = 5000;
const EMPTY_PIPELINE: PipelineStatus = {
  pending: 0,
  processing: 0,
  retry: 0,
  processed: 0,
  dead_letter: 0,
  active_depth: 0
};

function freshness(lastSeen: string): string {
  const seconds = Math.max(0, (Date.now() - new Date(lastSeen).getTime()) / 1000);
  if (seconds < 60) return `${Math.round(seconds)}s ago`;
  if (seconds < 3600) return `${Math.round(seconds / 60)}m ago`;
  return `${Math.round(seconds / 3600)}h ago`;
}

export default function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [pipeline, setPipeline] = useState(EMPTY_PIPELINE);
  const [nodes, setNodes] = useState<NodeSummary[]>([]);
  const [metrics, setMetrics] = useState<MetricDefinition[]>([]);
  const [selectedNode, setSelectedNode] = useState("");
  const [selectedMetric, setSelectedMetric] = useState("memory.used.percent");
  const [windowHours, setWindowHours] = useState(1);
  const [history, setHistory] = useState<MetricHistory | null>(null);
  const [anomalies, setAnomalies] = useState<Anomaly[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    const refreshOverview = async () => {
      try {
        const anomalyEnd = new Date();
        const anomalyStart = new Date(anomalyEnd.getTime() - 24 * 60 * 60 * 1000);
        const [nextHealth, nextPipeline, nextNodes, nextMetrics, nextAnomalies] =
          await Promise.all([
          api.health(controller.signal),
          api.pipeline(controller.signal),
          api.nodes(controller.signal),
          api.metrics(controller.signal),
          api.anomalies(anomalyStart, anomalyEnd, controller.signal)
        ]);
        setHealth(nextHealth);
        setPipeline(nextPipeline);
        setNodes(nextNodes);
        setMetrics(nextMetrics);
        setAnomalies(nextAnomalies);
        setSelectedNode((current) => current || nextNodes[0]?.node_id || "");
        setError(null);
        setLastUpdated(new Date());
      } catch (caught) {
        if (!controller.signal.aborted) {
          setError(caught instanceof Error ? caught.message : "Dashboard refresh failed");
        }
      }
    };
    void refreshOverview();
    const timer = window.setInterval(() => void refreshOverview(), REFRESH_INTERVAL_MS);
    return () => {
      controller.abort();
      window.clearInterval(timer);
    };
  }, []);

  useEffect(() => {
    if (!selectedNode || !selectedMetric) return;
    const controller = new AbortController();
    const end = new Date();
    const start = new Date(end.getTime() - windowHours * 60 * 60 * 1000);
    api
      .history(selectedNode, selectedMetric, start, end, controller.signal)
      .then((result) => {
        setHistory(result);
        setError(null);
      })
      .catch((caught: unknown) => {
        if (!controller.signal.aborted) {
          setError(caught instanceof Error ? caught.message : "Metric query failed");
        }
      });
    return () => controller.abort();
  }, [selectedNode, selectedMetric, windowHours, lastUpdated]);

  const selectedDefinition = useMemo(
    () => metrics.find((metric) => metric.name === selectedMetric),
    [metrics, selectedMetric]
  );
  const latest = history?.points.at(-1);

  return (
    <main>
      <header className="topbar">
        <div>
          <p className="eyebrow">Predictive observability</p>
          <h1>Incident Console</h1>
        </div>
        <div className="refresh-status" aria-live="polite">
          <span
            className={`status-dot ${
              health?.status === "ready" ? "healthy" : "unhealthy"
            }`}
          />
          {health?.status === "ready" ? "Systems ready" : "Checking systems"}
          <small>
            {lastUpdated ? `Updated ${lastUpdated.toLocaleTimeString()}` : "Connecting"}
          </small>
        </div>
      </header>

      {error && (
        <div className="alert" role="alert">
          <strong>Live data interrupted.</strong> {error}. Last known values remain
          visible while the console retries.
        </div>
      )}

      <section className="stat-grid" aria-label="System summary">
        <article className="stat-card">
          <span>Active queue</span>
          <strong>{pipeline.active_depth.toLocaleString()}</strong>
          <small>{pipeline.processing} currently processing</small>
        </article>
        <article className="stat-card">
          <span>Processed</span>
          <strong>{pipeline.processed.toLocaleString()}</strong>
          <small>Durably completed events</small>
        </article>
        <article className={`stat-card ${pipeline.retry > 0 ? "warning" : ""}`}>
          <span>Retrying</span>
          <strong>{pipeline.retry.toLocaleString()}</strong>
          <small>Recoverable processor failures</small>
        </article>
        <article className={`stat-card ${pipeline.dead_letter > 0 ? "danger" : ""}`}>
          <span>Dead letters</span>
          <strong>{pipeline.dead_letter.toLocaleString()}</strong>
          <small>Requires engineering review</small>
        </article>
        <article className={`stat-card ${anomalies.length > 0 ? "warning" : ""}`}>
          <span>Anomalies (24h)</span>
          <strong>{anomalies.length.toLocaleString()}</strong>
          <small>Explainable statistical findings</small>
        </article>
      </section>

      <section className="workspace">
        <div className="panel chart-panel">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">Historical signal</p>
              <h2>{selectedDefinition?.display_name ?? "Metric history"}</h2>
            </div>
            <div className="current-value">
              <span>Latest</span>
              <strong>
                {latest
                  ? formatValue(latest.value, selectedDefinition?.unit ?? "")
                  : "—"}
              </strong>
            </div>
          </div>

          <div className="controls">
            <label>
              Node
              <select
                value={selectedNode}
                onChange={(event) => setSelectedNode(event.target.value)}
              >
                {nodes.length === 0 && <option value="">No nodes discovered</option>}
                {nodes.map((node) => (
                  <option key={node.node_id} value={node.node_id}>
                    {node.node_id}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Metric
              <select
                value={selectedMetric}
                onChange={(event) => setSelectedMetric(event.target.value)}
              >
                {metrics.map((metric) => (
                  <option key={metric.name} value={metric.name}>
                    {metric.display_name}
                  </option>
                ))}
              </select>
            </label>
            <div className="window-picker" aria-label="Time window">
              {[1, 6, 24].map((hours) => (
                <button
                  key={hours}
                  className={windowHours === hours ? "active" : ""}
                  onClick={() => setWindowHours(hours)}
                  type="button"
                >
                  {hours}h
                </button>
              ))}
            </div>
          </div>

          <MetricChart
            points={history?.points ?? []}
            unit={selectedDefinition?.unit ?? ""}
          />
          <div className="chart-footer">
            <span>{history?.points.length ?? 0} samples</span>
            <span>Auto-refresh every 5 seconds</span>
          </div>
        </div>

        <aside className="panel node-panel">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">Fleet</p>
              <h2>Monitored nodes</h2>
            </div>
            <span className="count-badge">{nodes.length}</span>
          </div>
          <div className="node-list">
            {nodes.length === 0 && (
              <p className="empty-copy">Waiting for the first telemetry event.</p>
            )}
            {nodes.map((node) => (
              <button
                key={node.node_id}
                className={`node-row ${selectedNode === node.node_id ? "selected" : ""}`}
                onClick={() => setSelectedNode(node.node_id)}
                type="button"
              >
                <span className="node-icon">N</span>
                <span>
                  <strong>{node.node_id}</strong>
                  <small>{freshness(node.last_seen)}</small>
                </span>
                <span className="event-count">{node.event_count} events</span>
              </button>
            ))}
          </div>
          <div className="anomaly-section">
            <div className="panel-heading">
              <div>
                <p className="eyebrow">Detection</p>
                <h2>Recent anomalies</h2>
              </div>
              <span className="count-badge">{anomalies.length}</span>
            </div>
            <div className="anomaly-list">
              {anomalies.length === 0 && (
                <p className="empty-copy">No anomalies detected in the last 24 hours.</p>
              )}
              {anomalies.slice(0, 8).map((anomaly) => (
                <article
                  className={`anomaly-row ${anomaly.severity}`}
                  key={`${anomaly.event_id}-${anomaly.metric_name}`}
                >
                  <div>
                    <strong>{anomaly.metric_name}</strong>
                    <small>{anomaly.node_id}</small>
                  </div>
                  <span>{anomaly.severity}</span>
                  <small>
                    Score {anomaly.score.toFixed(1)} · baseline{" "}
                    {anomaly.baseline.toFixed(1)}
                  </small>
                </article>
              ))}
            </div>
          </div>
        </aside>
      </section>

      <footer>
        <span>RT Monitor v0.7</span>
        <span>CPU-first · Explainable anomalies · Historical telemetry</span>
      </footer>
    </main>
  );
}
