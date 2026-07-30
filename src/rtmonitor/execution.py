"""Hardware execution-provider selection with safe CPU fallback."""

from __future__ import annotations

import importlib
import importlib.util
import os
from dataclasses import dataclass
from typing import Literal

ProviderName = Literal["cpu", "gpu"]
ProviderRequest = Literal["auto", "cpu", "gpu"]


@dataclass(frozen=True, slots=True)
class ExecutionProvider:
    requested: ProviderRequest
    active: ProviderName
    accelerator: str | None
    fallback_reason: str | None


def resolve_execution_provider(requested: str | None = None) -> ExecutionProvider:
    raw = (requested or os.getenv("RTMONITOR_EXECUTION_PROVIDER") or "auto").strip().lower()
    if raw not in {"auto", "cpu", "gpu"}:
        raise ValueError("execution provider must be auto, cpu, or gpu")
    request = raw  # narrowed below for strict typing
    if request == "cpu":
        return ExecutionProvider("cpu", "cpu", None, None)

    if importlib.util.find_spec("cupy") is None:
        reason = "CuPy is not installed"
        return ExecutionProvider(
            "gpu" if request == "gpu" else "auto",
            "cpu",
            None,
            reason,
        )

    try:
        cupy = importlib.import_module("cupy")
        device_count = int(cupy.cuda.runtime.getDeviceCount())
        if device_count < 1:
            raise RuntimeError("no CUDA devices were detected")
    except Exception as exc:
        reason = f"CuPy cannot use a compatible CUDA device: {exc}"
        return ExecutionProvider(
            "gpu" if request == "gpu" else "auto",
            "cpu",
            None,
            reason,
        )

    return ExecutionProvider(
        "gpu" if request == "gpu" else "auto",
        "gpu",
        "cupy",
        None,
    )
