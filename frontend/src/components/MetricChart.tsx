import type { MetricPoint } from "../types";

interface MetricChartProps {
  points: MetricPoint[];
  unit: string;
}

const WIDTH = 900;
const HEIGHT = 300;
const PADDING = 34;

export function formatValue(value: number, unit: string): string {
  if (unit === "percent") return `${value.toFixed(1)}%`;
  if (unit === "bytes") {
    const units = ["B", "KB", "MB", "GB", "TB"];
    let scaled = value;
    let index = 0;
    while (scaled >= 1024 && index < units.length - 1) {
      scaled /= 1024;
      index += 1;
    }
    return `${scaled.toFixed(index === 0 ? 0 : 1)} ${units[index]}`;
  }
  if (unit === "seconds") {
    const hours = value / 3600;
    return hours >= 24 ? `${(hours / 24).toFixed(1)}d` : `${hours.toFixed(1)}h`;
  }
  return value.toLocaleString(undefined, { maximumFractionDigits: 2 });
}

export function MetricChart({ points, unit }: MetricChartProps) {
  if (points.length === 0) {
    return (
      <div className="chart-empty" role="status">
        No samples in this time window
      </div>
    );
  }

  const values = points.map((point) => point.value);
  const minimum = Math.min(...values);
  const maximum = Math.max(...values);
  const rawSpan = maximum - minimum;
  const span = rawSpan || 1;
  const plotWidth = WIDTH - PADDING * 2;
  const plotHeight = HEIGHT - PADDING * 2;
  const coordinates = points.map((point, index) => {
    const x =
      points.length === 1
        ? WIDTH / 2
        : PADDING + (index / (points.length - 1)) * plotWidth;
    const y =
      rawSpan === 0 ? HEIGHT / 2 : PADDING + ((maximum - point.value) / span) * plotHeight;
    return { x, y, point };
  });
  const polyline = coordinates.map(({ x, y }) => `${x},${y}`).join(" ");

  return (
    <div className="chart-shell">
      <svg
        className="metric-chart"
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        role="img"
        aria-label={`Historical metric chart with ${points.length} samples`}
      >
        <defs>
          <linearGradient id="chart-fill" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor="#49dcb1" stopOpacity="0.35" />
            <stop offset="100%" stopColor="#49dcb1" stopOpacity="0" />
          </linearGradient>
        </defs>
        <line x1={PADDING} y1={PADDING} x2={PADDING} y2={HEIGHT - PADDING} />
        <line
          x1={PADDING}
          y1={HEIGHT - PADDING}
          x2={WIDTH - PADDING}
          y2={HEIGHT - PADDING}
        />
        {points.length > 1 && (
          <polygon
            className="chart-area"
            points={`${PADDING},${HEIGHT - PADDING} ${polyline} ${
              WIDTH - PADDING
            },${HEIGHT - PADDING}`}
          />
        )}
        <polyline className="chart-line" points={polyline} />
        {coordinates.map(({ x, y, point }) => (
          <circle key={point.event_id} cx={x} cy={y} r="4">
            <title>
              {new Date(point.observed_at).toLocaleString()}:{" "}
              {formatValue(point.value, unit)}
            </title>
          </circle>
        ))}
      </svg>
      <div className="chart-scale" aria-hidden="true">
        <span>{formatValue(maximum, unit)}</span>
        <span>{formatValue(minimum, unit)}</span>
      </div>
    </div>
  );
}
