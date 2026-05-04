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


def load_shots(shot_ids: list[int]) -> list[dict[str, dict]]:
    """Load multiple shots, skipping any that fail.

    Returns:
        List of signal dictionaries, one per successfully loaded shot.
    """
    results: list[dict[str, dict]] = []
    for sid in shot_ids:
        try:
            data = load_shot(sid)
            results.append(data)
        except (FileNotFoundError, ConnectionError) as exc:
            logger.warning("shot_skipped", shot_id=sid, reason=str(exc))
    return results
