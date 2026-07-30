import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import App from "./App";

function response(body: object): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" }
  });
}

describe("Incident Console", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders live operational data from the API", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const path = String(input);
        if (path === "/health/ready") {
          return response({ status: "ready", storage: "available" });
        }
        if (path === "/v1/pipeline/status") {
          return response({
            pending: 0,
            processing: 0,
            retry: 0,
            processed: 12,
            dead_letter: 0,
            active_depth: 0
          });
        }
        if (path === "/v1/nodes") {
          return response({
            nodes: [
              {
                node_id: "node-001",
                last_seen: new Date().toISOString(),
                event_count: 12
              }
            ]
          });
        }
        if (path === "/v1/metrics") {
          return response({
            metrics: [
              {
                name: "memory.used.percent",
                display_name: "Memory used",
                unit: "percent",
                category: "Memory"
              }
            ]
          });
        }
        if (path.startsWith("/v1/anomalies?")) {
          return response({
            anomalies: [
              {
                event_id: "14d6a69e-e40a-42a1-9b45-549d8a949d59",
                node_id: "node-001",
                metric_name: "memory.used.percent",
                observed_at: "2026-07-30T06:30:00Z",
                value: 90,
                baseline: 26.9,
                dispersion: 1.2,
                score: 8.1,
                severity: "critical",
                sample_count: 20
              }
            ]
          });
        }
        if (path === "/v1/forecasts") {
          return response({
            forecasts: [
              {
                event_id: "24d6a69e-e40a-42a1-9b45-549d8a949d59",
                node_id: "node-001",
                metric_name: "memory.used.percent",
                current_value: 85,
                threshold: 90,
                slope_per_hour: 5,
                hours_to_threshold: 1,
                predicted_at: "2026-07-30T07:30:00Z",
                r_squared: 100,
                confidence: "high",
                risk: "critical",
                sample_count: 7,
                backtest_error: 0,
                provider: "cpu",
                fallback_reason: "CuPy is not installed"
              }
            ]
          });
        }
        if (path === "/v1/incidents") {
          return response({
            incidents: [
              {
                incident_id: "34d6a69e-e40a-42a1-9b45-549d8a949d59",
                node_id: "node-001",
                metric_name: "memory.used.percent",
                status: "open",
                severity: "critical",
                title: "Memory exhaustion risk",
                summary: "Memory is forecast to cross its threshold",
                occurrence_count: 3,
                first_seen: new Date().toISOString(),
                last_seen: new Date().toISOString(),
                owner: null,
                acknowledged_at: null,
                resolved_at: null,
                resolution_note: null,
                revision: 4,
                updated_at: new Date().toISOString()
              }
            ]
          });
        }
        if (path === "/v1/incidents/34d6a69e-e40a-42a1-9b45-549d8a949d59/acknowledge") {
          return response({
            incident_id: "34d6a69e-e40a-42a1-9b45-549d8a949d59",
            node_id: "node-001",
            metric_name: "memory.used.percent",
            status: "acknowledged",
            severity: "critical",
            title: "Memory exhaustion risk",
            summary: "Memory is forecast to cross its threshold",
            occurrence_count: 3,
            first_seen: new Date().toISOString(),
            last_seen: new Date().toISOString(),
            owner: "on-call",
            acknowledged_at: new Date().toISOString(),
            resolved_at: null,
            resolution_note: null,
            revision: 5,
            updated_at: new Date().toISOString()
          });
        }
        if (path === "/v1/runtime") {
          return response({
            requested: "auto",
            active: "cpu",
            accelerator: null,
            fallback_reason: "GPU unavailable"
          });
        }
        if (path.startsWith("/v1/metrics/node-001?")) {
          return response({
            node_id: "node-001",
            metric_name: "memory.used.percent",
            start: "2026-07-30T06:00:00Z",
            end: "2026-07-30T07:00:00Z",
            points: [
              {
                event_id: "14d6a69e-e40a-42a1-9b45-549d8a949d59",
                observed_at: "2026-07-30T06:30:00Z",
                value: 26.9,
                labels: {}
              }
            ],
            next_cursor: null
          });
        }
        return new Response(null, { status: 404 });
      })
    );

    render(<App />);

    expect(await screen.findByText("Systems ready")).toBeInTheDocument();
    expect(screen.getAllByText("node-001").length).toBeGreaterThanOrEqual(4);
    await waitFor(() =>
      expect(screen.getAllByText("26.9%").length).toBeGreaterThan(0)
    );
    expect(screen.getByText("12")).toBeInTheDocument();
    expect(screen.getByText("Recent anomalies")).toBeInTheDocument();
    expect(screen.getByText("Score 8.1 · baseline 26.9")).toBeInTheDocument();
    expect(
      screen.getByText("Threshold in 1.0h · high confidence · CPU · backtest ±0.00")
    ).toBeInTheDocument();
    expect(screen.getByText("CPU fallback active")).toBeInTheDocument();
    expect(screen.getByText("Incident response queue")).toBeInTheDocument();
    expect(screen.getByText("Memory exhaustion risk")).toBeInTheDocument();
    expect(screen.getByText(/3 occurrences · last seen/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Acknowledge" }));
    await waitFor(() =>
      expect(
        vi.mocked(fetch).mock.calls.some(
          ([path, init]) =>
            path ===
              "/v1/incidents/34d6a69e-e40a-42a1-9b45-549d8a949d59/acknowledge" &&
            init?.method === "POST"
        )
      ).toBe(true)
    );
    expect(await screen.findByText(/owner on-call/)).toBeInTheDocument();
  });

  it("shows an explicit degraded state when refresh fails", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => Promise.reject(new Error("offline"))));

    render(<App />);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Live data interrupted"
    );
    expect(screen.getByRole("alert")).toHaveTextContent("offline");
  });
});
