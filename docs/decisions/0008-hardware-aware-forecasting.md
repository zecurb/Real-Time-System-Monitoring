# ADR 0008: Hardware-aware resource forecasting

## Decision

Forecast memory and disk threshold crossings with explainable least-squares
trends, a minimum of six samples over five minutes, an R² quality gate, and a
seven-day maximum horizon. Record slope, crossing time, confidence, risk,
sample count, one-step backtest error, actual execution provider, and fallback
reason. Always select the newest bounded sample window so long-running nodes do
not train on stale history.

CPU is always available. `RTMONITOR_EXECUTION_PROVIDER=auto|cpu|gpu` controls
provider selection. A compatible optional CuPy installation and usable CUDA
device enable GPU regression; otherwise the system reports its fallback reason
and continues on CPU. CuPy remains an operator-selected optional dependency
because its package must match the host CUDA runtime.

## Consequences

- The two non-GPU hosts remain fully functional.
- Lightweight regression stays efficient on CPU while compatible hosts can run
  the same array operations on a GPU.
- Future heavier models can share the provider contract.
- Weak, declining, noisy, or under-sampled trends produce no forecast.
