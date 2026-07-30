import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { formatValue, MetricChart } from "./MetricChart";

describe("MetricChart", () => {
  it("shows an explicit empty state", () => {
    render(<MetricChart points={[]} unit="percent" />);
    expect(screen.getByRole("status")).toHaveTextContent("No samples");
  });

  it("renders an accessible chart for one sample", () => {
    render(
      <MetricChart
        unit="percent"
        points={[
          {
            event_id: "14d6a69e-e40a-42a1-9b45-549d8a949d59",
            observed_at: "2026-07-30T07:30:30Z",
            value: 26.9,
            labels: {}
          }
        ]}
      />
    );
    expect(
      screen.getByRole("img", { name: "Historical metric chart with 1 samples" })
    ).toBeInTheDocument();
  });

  it("formats operational units", () => {
    expect(formatValue(26.94, "percent")).toBe("26.9%");
    expect(formatValue(1_073_741_824, "bytes")).toBe("1.0 GB");
  });
});
