"""BigQuery Property Graph (ISO GQL) & Spatial Client with GeoParquet Local Mirror.

In Google Cloud (Cloud Run, Agent Engine, Cloud Shell, Colab Enterprise), executes
live ISO/IEC 39075 GQL queries (`GRAPH_TABLE` over `ReferralGraph`) and native
`ST_DISTANCE` spatial queries against `<PROJECT>.a4i_early_intervention`.

When running locally without GCP credentials (or with `A4I_FORCE_LOCAL_PARQUET=1`),
transparently executes the exact equivalent graph & Haversine spatial logic over
the repository's `data/*.parquet` starter files so developers and judges can also
preview and run automated tests locally in milliseconds.
"""

from __future__ import annotations

import functools
import logging
import math
import os
from pathlib import Path
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

VALID_STATES = ("MS", "AL", "GA", "TX", "CA", "NY")
STATE_LABELS = {
    "MS": "Mississippi",
    "AL": "Alabama",
    "GA": "Georgia",
    "TX": "Texas",
    "CA": "California",
    "NY": "New York",
}


def get_config() -> dict[str, str]:
    """Returns normalized runtime configuration."""
    state = os.environ.get("A4I_STATE", "MS").strip().upper()
    if state not in VALID_STATES:
        state = "MS"
    return {
        "project": os.environ.get("GOOGLE_CLOUD_PROJECT", "").strip(),
        "dataset": os.environ.get("A4I_DATASET", "a4i_early_intervention").strip(),
        "location": os.environ.get("A4I_LOCATION", "US").strip(),
        "state": state,
        "state_name": STATE_LABELS[state],
    }


def _find_data_dir() -> Path:
    """Locates `data/*.parquet` across repo root or container working dirs."""
    override = os.environ.get("A4I_DATA_DIR", "").strip()
    candidates = []
    if override:
        candidates.append(Path(override))
    here = Path(__file__).resolve()
    candidates.extend([
        here.parents[3] / "data",  # repo_root/data when running from repo
        here.parents[2] / "data",  # /app/data inside Docker container
        Path.cwd() / "data",
        Path.cwd().parent / "data",
    ])
    for cand in candidates:
        if (cand / "pediatric_and_ei_provider_directory.parquet").is_file():
            return cand
    raise FileNotFoundError(
        "Could not locate starter `data/*.parquet` files. Set A4I_DATA_DIR or configure BigQuery."
    )


@functools.lru_cache(maxsize=6)
def load_local_state_frames(state_code: str) -> dict[str, pd.DataFrame]:
    """Loads and normalizes the 5 starter tables for `state_code` from GeoParquet."""
    st = state_code.strip().upper()
    if st not in VALID_STATES:
        raise ValueError(f"Unsupported state_code={state_code!r}. Expected one of {VALID_STATES}.")
    data_dir = _find_data_dir()

    demo = pd.read_parquet(data_dir / "acs_under5_tract_demographics.parquet")
    demo = demo[demo["state_code"] == st].copy()
    demo["census_tract_geoid"] = demo["census_tract_geoid"].astype(str).str.strip().str.zfill(11)
    demo["county_fips"] = demo["county_fips"].astype(str).str.strip().str.zfill(5)

    nsch = pd.read_parquet(data_dir / "nsch_developmental_screening_survey.parquet")
    nsch = nsch[nsch["state_code"] == st].copy()

    agencies = pd.read_parquet(data_dir / "idea_part_c_agency_performance.parquet")
    agencies = agencies[agencies["state_code"] == st].copy()

    providers = pd.read_parquet(data_dir / "pediatric_and_ei_provider_directory.parquet")
    providers = providers[providers["state_code"] == st].copy()
    providers["census_tract_geoid"] = (
        providers["census_tract_geoid"].astype(str).str.strip().str.zfill(11)
    )
    providers["county_fips"] = providers["county_fips"].astype(str).str.strip().str.zfill(5)

    logs = pd.read_parquet(data_dir / "deidentified_part_c_referral_logs.parquet")
    logs = logs[logs["state_code"] == st].copy()
    logs["child_home_tract_geoid"] = (
        logs["child_home_tract_geoid"].astype(str).str.strip().str.zfill(11)
    )
    logs = logs.sort_values(["case_chain_id", "hop_sequence"]).reset_index(drop=True)

    return {
        "demo": demo,
        "nsch": nsch,
        "agencies": agencies,
        "providers": providers,
        "logs": logs,
    }


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Spherical distance in kilometers (matches BigQuery ST_DISTANCE / 1000)."""
    r_earth_km = 6371.0088
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    return round(2.0 * r_earth_km * math.atan2(math.sqrt(a), math.sqrt(1.0 - a)), 1)


class DualBackendGraphClient:
    """Executes BigQuery ISO GQL + GIS queries when GCP is active, with local fallback."""

    def __init__(self) -> None:
        self._bq_client: Any = None
        self._bq_checked = False
        self._graph_ensured = False

    def _get_bq(self) -> Any | None:
        if os.environ.get("A4I_FORCE_LOCAL_PARQUET") == "1":
            return None
        if self._bq_checked:
            return self._bq_client
        self._bq_checked = True
        cfg = get_config()
        if not cfg["project"]:
            return None
        try:
            from google.cloud import bigquery

            client = bigquery.Client(project=cfg["project"], location=cfg["location"])
            # Lightweight dataset existence probe
            client.get_dataset(f"{cfg['project']}.{cfg['dataset']}")
            self._bq_client = client
            return self._bq_client
        except Exception as exc:  # noqa: BLE001
            logger.info("BigQuery client unavailable (%s); using local GeoParquet mirror.", exc)
            self._bq_client = None
            return None

    def ensure_property_graph(self) -> bool:
        """Idempotently declares `ReferralGraph` in BigQuery if not already created."""
        bq = self._get_bq()
        if bq is None:
            return False
        if self._graph_ensured:
            return True
        cfg = get_config()
        ds = cfg["dataset"]
        ddl = f"""
        CREATE OR REPLACE PROPERTY GRAPH {ds}.ReferralGraph
          NODE TABLES (
            {ds}.pediatric_and_ei_provider_directory AS CareNode
              KEY (provider_id)
              LABEL CareNode
              PROPERTIES ALL COLUMNS EXCEPT (provider_geom)
          )
          EDGE TABLES (
            {ds}.deidentified_part_c_referral_logs AS ReferralHandoff
              KEY (referral_event_id)
              SOURCE KEY (source_provider_id) REFERENCES CareNode (provider_id)
              DESTINATION KEY (target_provider_id) REFERENCES CareNode (provider_id)
              LABEL ReferralHandoff
              PROPERTIES ALL COLUMNS
          );
        """
        try:
            bq.query(ddl).result()
            self._graph_ensured = True
            return True
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not ensure ReferralGraph DDL (%s)", exc)
            return False

    def query_bq_or_none(self, sql: str, job_config: Any = None) -> list[dict[str, Any]] | None:
        """Runs `sql` on BigQuery and returns list of dicts, or `None` if offline."""
        bq = self._get_bq()
        if bq is None:
            return None
        try:
            self.ensure_property_graph()
            rows = bq.query(sql, job_config=job_config).result()
            return [dict(row.items()) for row in rows]
        except Exception as exc:  # noqa: BLE001
            logger.warning("BigQuery query failed (%s); falling back to local mirror.", exc)
            return None


graph_client = DualBackendGraphClient()
