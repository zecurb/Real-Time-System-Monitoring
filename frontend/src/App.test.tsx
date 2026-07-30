import { render, screen, waitFor } from "@testing-library/react";
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
    expect(screen.getAllByText("node-001")).toHaveLength(3);
    await waitFor(() =>
      expect(screen.getAllByText("26.9%").length).toBeGreaterThan(0)
    );
    expect(screen.getByText("12")).toBeInTheDocument();
    expect(screen.getByText("Recent anomalies")).toBeInTheDocument();
    expect(screen.getByText("Score 8.1 · baseline 26.9")).toBeInTheDocument();
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
