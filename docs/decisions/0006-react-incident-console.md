# ADR 0006: React incident console

- Status: accepted
- Date: 2026-07-30

## Context

Engineers need one operational view for pipeline health, monitored nodes, and
historical signals. The interface must remain legible during partial API
failures and must not require a GPU.

## Decision

Build a React 19 and TypeScript single-page application with Vite. Discover
nodes and metric presentation metadata from API endpoints instead of embedding
machine IDs or an independent metric catalog in the frontend.

Refresh overview and historical data every five seconds. Abort stale requests
when selections change or the component unmounts. Preserve last-known values
and show an explicit alert when a refresh fails.

Render historical data with a small native SVG component instead of adding a
charting dependency. Lock all npm dependencies and run TypeScript checks,
component tests, production builds, and Python checks in CI.

## Consequences

- The console is CPU-only and works on the user's non-GPU machines.
- The production JavaScript bundle remains small and dependency exposure is
  limited.
- Node, metric, and time-window selection are accessible native controls.
- The development proxy avoids permissive CORS configuration.
- Production requires serving `frontend/dist` behind a reverse proxy that also
  routes `/health` and `/v1` to the API.
