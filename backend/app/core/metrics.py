from __future__ import annotations

from prometheus_client import Counter, Histogram
from prometheus_fastapi_instrumentator import Instrumentator

PREDICTIONS_TOTAL = Counter(
    "tokamak_predictions_total",
    "Total predictions",
    ["model_type", "task"],
)
INFERENCE_DURATION = Histogram(
    "tokamak_inference_duration_seconds",
    "Inference duration",
    ["model_type"],
)
EXPERIMENTS_LOADED = Counter(
    "tokamak_experiments_loaded_total",
    "Total experiments loaded",
)
TRAINING_RUNS = Counter(
    "tokamak_training_runs_total",
    "Total training runs",
    ["model_type", "status"],
)

instrumentator = Instrumentator(
    should_group_status_codes=False,
    should_ignore_untemplated=False,
    should_instrument_requests_inprogress=True,
    excluded_handlers=["/health", "/metrics"],
)
