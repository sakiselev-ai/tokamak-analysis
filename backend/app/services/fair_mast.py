from __future__ import annotations

import s3fs
import xarray as xr
import zarr
import numpy as np
import structlog

from app.config import settings

logger = structlog.get_logger()

# Key diagnostic signals available in FAIR-MAST (subset of 39 signals)
MAST_SIGNALS = [
    "amc_plasma current",
    "efm_magnetic_axis_r",
    "efm_magnetic_axis_z",
    "efm_plasma_energy",
    "ane_density",
    "xsx_mid_plane_brightness",
    "efm_bvac_val",
    "efm_elongation",
    "efm_q_95",
    "efm_upper_triangularity",
    "efm_lower_triangularity",
    "efm_minor_radius",
    "efm_major_radius",
    "efm_li",
    "efm_beta_pol",
    "efm_beta_tor",
    "epm_output_power",
    "anb_tot_sum_power",
]


class FairMastClient:
    """Client for accessing FAIR-MAST data via S3/Zarr."""

    def __init__(self):
        self.s3 = s3fs.S3FileSystem(
            anon=True,
            client_kwargs={"endpoint_url": settings.fair_mast_s3_endpoint},
        )
        self.bucket = settings.fair_mast_bucket

    async def load_shot(self, shot_id: int) -> dict[str, dict]:
        """Load shot data from FAIR-MAST S3 bucket.

        Returns dict mapping signal_name -> {timestamps, values, units, description}.
        """
        signals = {}
        shot_path = f"{self.bucket}/level1/shots/{shot_id}.zarr"

        logger.info("loading_shot", shot_id=shot_id, path=shot_path)

        try:
            available = self.s3.ls(shot_path)
        except FileNotFoundError:
            raise ValueError(f"Shot {shot_id} not found in FAIR-MAST")

        for item_path in available:
            signal_name = item_path.split("/")[-1]

            try:
                store = s3fs.S3Map(root=item_path, s3=self.s3)
                ds = xr.open_zarr(store)

                for var_name in ds.data_vars:
                    var = ds[var_name]
                    if var.dims and "time" in str(var.dims[0]).lower():
                        time_dim = var.dims[0]
                        timestamps = ds[time_dim].values.astype(float).tolist()
                        values = var.values.astype(float).tolist()

                        # Replace NaN/inf
                        timestamps = [t if np.isfinite(t) else 0.0 for t in timestamps]
                        values = [v if np.isfinite(v) else 0.0 for v in values]

                        full_name = f"{signal_name}/{var_name}" if var_name != signal_name else signal_name
                        signals[full_name] = {
                            "timestamps": timestamps,
                            "values": values,
                            "units": str(var.attrs.get("units", "")),
                            "description": str(var.attrs.get("long_name", var_name)),
                        }
            except Exception as e:
                logger.warning("signal_load_failed", signal=signal_name, error=str(e))
                continue

        if not signals:
            raise ValueError(f"No valid signals found for shot {shot_id}")

        logger.info("shot_loaded", shot_id=shot_id, signal_count=len(signals))
        return signals

    async def list_shots(self, limit: int = 100) -> list[int]:
        """List available shot IDs."""
        try:
            shots_path = f"{self.bucket}/level1/shots"
            items = self.s3.ls(shots_path)
            shot_ids = []
            for item in items[:limit]:
                try:
                    shot_ids.append(int(item.split("/")[-1].replace(".zarr", "")))
                except ValueError:
                    continue
            return sorted(shot_ids)
        except Exception as e:
            logger.error("list_shots_failed", error=str(e))
            return []
