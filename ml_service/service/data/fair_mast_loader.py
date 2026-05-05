from __future__ import annotations

import pickle
from pathlib import Path

import numpy as np
import structlog

logger = structlog.get_logger()

FAIR_MAST_ENDPOINT = "https://s3.echo.stfc.ac.uk"
FAIR_MAST_BUCKET = "mast"
CACHE_DIR = Path("/tmp/fair_mast_cache")


def _get_filesystem():
    """Create an anonymous S3 filesystem for FAIR-MAST."""
    import s3fs

    return s3fs.S3FileSystem(
        anon=True,
        client_kwargs={"endpoint_url": FAIR_MAST_ENDPOINT},
    )


def _cache_path(shot_id: int) -> Path:
    """Return the local cache file path for a given shot."""
    return CACHE_DIR / f"shot_{shot_id}.pkl"


def _load_from_cache(shot_id: int) -> dict[str, dict] | None:
    """Load shot data from local cache if available."""
    path = _cache_path(shot_id)
    if path.exists():
        logger.debug("cache_hit", shot_id=shot_id)
        with open(path, "rb") as f:
            return pickle.load(f)  # noqa: S301
    return None


def _save_to_cache(shot_id: int, data: dict[str, dict]) -> None:
    """Persist shot data to local cache."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = _cache_path(shot_id)
    with open(path, "wb") as f:
        pickle.dump(data, f)
    logger.debug("cache_saved", shot_id=shot_id, path=str(path))


def _parse_signal(zarr_group, signal_name: str) -> dict:
    """Extract timestamps, values, and units from a zarr signal group."""
    signal = zarr_group[signal_name]
    values = np.array(signal["data"])
    timestamps = np.array(signal["time"]) if "time" in signal else np.arange(len(values), dtype=float)
    units = str(signal.attrs.get("units", "unknown")) if hasattr(signal, "attrs") else "unknown"

    # Flatten multi-dimensional signals by taking the first channel
    if values.ndim > 1:
        values = values[:, 0]

    # Ensure timestamps and values have matching lengths
    min_len = min(len(timestamps), len(values))
    timestamps = timestamps[:min_len]
    values = values[:min_len]

    return {
        "timestamps": timestamps.tolist(),
        "values": values.tolist(),
        "units": units,
    }


def load_shot(shot_id: int) -> dict[str, dict]:
    """Load all time-series signals for a single MAST shot.

    Args:
        shot_id: The MAST shot number.

    Returns:
        Dictionary mapping signal_name to dict with keys
        ``timestamps``, ``values``, ``units``.

    Raises:
        FileNotFoundError: If the shot does not exist in the archive.
        ConnectionError: If the S3 endpoint is unreachable.
    """
    # Check cache first
    cached = _load_from_cache(shot_id)
    if cached is not None:
        return cached

    try:
        import s3fs as _s3fs
        import zarr

        fs = _get_filesystem()
        shot_path = f"{FAIR_MAST_BUCKET}/{shot_id}"

        if not fs.exists(shot_path):
            raise FileNotFoundError(f"Shot {shot_id} not found in FAIR-MAST archive")

        store = _s3fs.S3Map(root=shot_path, s3=fs)
        root = zarr.open(store, mode="r")

        signals: dict[str, dict] = {}
        for signal_name in root.keys():
            try:
                parsed = _parse_signal(root, signal_name)
                if len(parsed["values"]) > 0:
                    signals[signal_name] = parsed
            except Exception as exc:
                logger.warning(
                    "signal_parse_failed",
                    shot_id=shot_id,
                    signal=signal_name,
                    error=str(exc),
                )
                continue

        if not signals:
            raise FileNotFoundError(
                f"Shot {shot_id} exists but contains no readable signals"
            )

        _save_to_cache(shot_id, signals)
        logger.info("shot_loaded", shot_id=shot_id, n_signals=len(signals))
        return signals

    except FileNotFoundError:
        raise
    except Exception as exc:
        raise ConnectionError(
            f"Failed to load shot {shot_id} from FAIR-MAST: {exc}"
        ) from exc


def load_disruption_labels(shot_ids: list[int]) -> dict[int, float | None]:
    """Load disruption times for a list of shots from FAIR-MAST.

    Reads ``cpf/disruption_time`` from each shot's Zarr store.

    Args:
        shot_ids: List of MAST shot numbers.

    Returns:
        Dictionary mapping shot_id to disruption_time (float in seconds),
        or ``None`` if the shot did not disrupt or the field is missing.
    """
    result: dict[int, float | None] = {}
    try:
        import s3fs as _s3fs
        import zarr

        fs = _get_filesystem()
        for sid in shot_ids:
            try:
                shot_path = f"{FAIR_MAST_BUCKET}/{sid}"
                if not fs.exists(shot_path):
                    logger.warning("shot_not_found_for_label", shot_id=sid)
                    result[sid] = None
                    continue

                store = _s3fs.S3Map(root=shot_path, s3=fs)
                root = zarr.open(store, mode="r")

                if "cpf" in root and "disruption_time" in root["cpf"]:
                    dt_val = float(np.array(root["cpf"]["disruption_time"]).flat[0])
                    # Negative or NaN disruption_time means no disruption
                    if np.isfinite(dt_val) and dt_val >= 0:
                        result[sid] = dt_val
                    else:
                        result[sid] = None
                else:
                    result[sid] = None

                logger.debug("disruption_label_loaded", shot_id=sid, disruption_time=result[sid])
            except Exception as exc:
                logger.warning("disruption_label_failed", shot_id=sid, error=str(exc))
                result[sid] = None
    except Exception as exc:
        logger.error("disruption_labels_connection_failed", error=str(exc))
        # Fill remaining shot_ids with None
        for sid in shot_ids:
            if sid not in result:
                result[sid] = None

    return result


def make_disruption_labels(
    shot_ids: list[int],
    disruption_times: dict[int, float | None],
) -> np.ndarray:
    """Convert disruption times to binary labels.

    Args:
        shot_ids: Ordered list of shot IDs matching the feature array order.
        disruption_times: Mapping from shot_id to disruption_time (or None).

    Returns:
        1-D float32 array: 1.0 for disrupted shots, 0.0 for stable shots.
    """
    labels = np.zeros(len(shot_ids), dtype=np.float32)
    for i, sid in enumerate(shot_ids):
        dt = disruption_times.get(sid)
        if dt is not None:
            labels[i] = 1.0
    return labels


def load_shots(shot_ids: list[int]) -> tuple[list[dict[str, dict]], list[int]]:
    """Load multiple shots, skipping any that fail.

    Returns:
        Tuple of (signal dictionaries, successfully loaded shot IDs).
    """
    results: list[dict[str, dict]] = []
    loaded_ids: list[int] = []
    for sid in shot_ids:
        try:
            data = load_shot(sid)
            results.append(data)
            loaded_ids.append(sid)
        except (FileNotFoundError, ConnectionError) as exc:
            logger.warning("shot_skipped", shot_id=sid, reason=str(exc))
    return results, loaded_ids
