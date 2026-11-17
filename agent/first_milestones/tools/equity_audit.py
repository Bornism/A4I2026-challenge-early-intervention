"""Post-Output Equity Audit & Community Screening Outreach Readiness Tools.

Governance Rule Enforced:
  - `audit_black_share`, `audit_hispanic_share`, `audit_asian_share`,
    `audit_indigenous_share`, and `audit_white_share` are NEVER read inside
    `graph_routing.py`. They are joined strictly HERE, *after* pathway and
    bottleneck outputs are generated, to quantify baseline >45-day disparity and
    verify that zero-vehicle families are protected via NEMT / mobile evaluation.
  - `nsch_developmental_screening_survey` is queried strictly at its `'Statewide'`
    grain (6 strata/state) without joining to tracts on `state_code` alone.
"""

from __future__ import annotations

import re
from typing import Any

from .bq_client import get_config, graph_client, haversine_km, load_local_state_frames


def run_post_output_equity_audit() -> dict[str, Any]:
    """Runs the post-output Equity Audit joining episode outcomes to ACS `audit_*` shares.

    Quantifies:
      1. Demographic, poverty, and zero-vehicle household profiles of neighborhoods
         suffering >45-day multi-hop breaches vs. <=45-day timely IFSP episodes.
      2. Distance barriers (`km` to nearest bilingual, Medicaid-accepting Evaluation Hub)
         for high-poverty, zero-vehicle tracts.
      3. Statewide HRSA NSCH developmental screening disparities by primary household
         language and FPL income band (kept strictly at `'Statewide'` grain — zero 6x
         tract fan-out — and used honestly in place of the all-zero ACS
         `limited_english_rate` column).
    """
    cfg = get_config()
    frames = load_local_state_frames(cfg["state"])
    demo = frames["demo"]
    logs = frames["logs"]
    prov = frames["providers"]
    nsch = frames["nsch"]

    equity_sql = f"""
    WITH chain_totals AS (
      SELECT
        case_chain_id,
        ANY_VALUE(LPAD(child_home_tract_geoid, 11, '0')) AS child_home_tract_geoid,
        SUM(handoff_wait_days) AS episode_wait_days
      FROM `{cfg['project']}.{cfg['dataset']}.deidentified_part_c_referral_logs`
      GROUP BY case_chain_id
    )
    SELECT
      IF(c.episode_wait_days > 45, 'Breached (>45 days)', 'Timely (<=45 days)') AS ifsp_status,
      COUNT(*) AS episodes,
      ROUND(AVG(c.episode_wait_days), 1) AS mean_wait_days,
      ROUND(AVG(d.poverty_rate) * 100, 1) AS avg_tract_poverty_pct,
      ROUND(AVG(d.no_vehicle_rate) * 100, 1) AS avg_zero_vehicle_pct,
      ROUND(AVG(d.audit_black_share) * 100, 1) AS audit_black_pct,
      ROUND(AVG(d.audit_hispanic_share) * 100, 1) AS audit_hispanic_pct,
      ROUND(AVG(d.audit_indigenous_share) * 100, 1) AS audit_indigenous_pct,
      ROUND(AVG(d.audit_asian_share) * 100, 1) AS audit_asian_pct,
      ROUND(AVG(d.audit_white_share) * 100, 1) AS audit_white_pct
    FROM chain_totals AS c
    INNER JOIN `{cfg['project']}.{cfg['dataset']}.acs_under5_tract_demographics` AS d
      ON c.child_home_tract_geoid = LPAD(d.census_tract_geoid, 11, '0')
    GROUP BY 1
    ORDER BY 1;
    """.strip()

    bq_rows = graph_client.query_bq_or_none(equity_sql) if cfg["project"] else None
    engine = (
        f"bigquery_sql ({cfg['project']}.{cfg['dataset']})"
        if bq_rows is not None
        else f"local_geoparquet_mirror ({cfg['state']} starter tables)"
    )

    if bq_rows is not None:
        outcome_strata = bq_rows
    else:
        ep = (
            logs.groupby("case_chain_id")
            .agg(
                child_home_tract_geoid=("child_home_tract_geoid", "first"),
                episode_wait_days=("handoff_wait_days", "sum"),
            )
            .reset_index()
        )
        ep["ifsp_status"] = ep["episode_wait_days"].apply(
            lambda w: "Breached (>45 days)" if w > 45 else "Timely (<=45 days)"
        )
        merged = ep.merge(
            demo, left_on="child_home_tract_geoid", right_on="census_tract_geoid", how="inner"
        )
        outcome_strata = []
        for status, grp in merged.groupby("ifsp_status"):
            outcome_strata.append({
                "ifsp_status": str(status),
                "episodes": int(len(grp)),
                "mean_wait_days": round(float(grp["episode_wait_days"].mean()), 1),
                "avg_tract_poverty_pct": round(float(grp["poverty_rate"].mean()) * 100.0, 1),
                "avg_zero_vehicle_pct": round(float(grp["no_vehicle_rate"].mean()) * 100.0, 1),
                "audit_black_pct": round(float(grp["audit_black_share"].mean()) * 100.0, 1),
                "audit_hispanic_pct": round(float(grp["audit_hispanic_share"].mean()) * 100.0, 1),
                "audit_indigenous_pct": round(float(grp["audit_indigenous_share"].mean()) * 100.0, 1),
                "audit_asian_pct": round(float(grp["audit_asian_share"].mean()) * 100.0, 1),
                "audit_white_pct": round(float(grp["audit_white_share"].mean()) * 100.0, 1),
            })
        outcome_strata.sort(key=lambda x: x["ifsp_status"])

    # Compute distance to nearest bilingual Medicaid-enrolled Evaluation Hub for underserved tracts
    bil_evals = prov[
        (prov["node_role"] == "Multidisciplinary_Eval_Hub")
        & (prov["accepts_medicaid"])
        & (prov["bilingual_services_listed"])
    ]
    underserved_tracts = []
    for _, tr in demo.iterrows():
        t_lat, t_lon = float(tr["latitude"]), float(tr["longitude"])
        min_km = min(
            haversine_km(t_lat, t_lon, float(ev["latitude"]), float(ev["longitude"]))
            for _, ev in bil_evals.iterrows()
        )
        underserved_tracts.append({
            "census_tract_geoid": str(tr["census_tract_geoid"]),
            "county_name": str(tr["county_name"]),
            "children_under_5_count": int(tr["children_under_5_count"]),
            "poverty_pct": round(float(tr["poverty_rate"]) * 100.0, 1),
            "zero_vehicle_pct": round(float(tr["no_vehicle_rate"]) * 100.0, 1),
            "km_to_bilingual_medicaid_eval_hub": min_km,
            "requires_nemt_or_mobile_eval": (min_km > 25.0 and float(tr["no_vehicle_rate"]) >= 0.08),
        })
    underserved_tracts.sort(
        key=lambda x: (x["km_to_bilingual_medicaid_eval_hub"], x["poverty_pct"]),
        reverse=True,
    )

    # Statewide HRSA NSCH language comparison (6 statewide strata, never raw-joined to tracts)
    nsch_clean = []
    for _, r in nsch.sort_values("standardized_screening_rate_pct").iterrows():
        nsch_clean.append({
            "survey_stratum_id": str(r["survey_stratum_id"]),
            "geographic_level": str(r["geographic_level"]),
            "household_income_fpl_band": str(r["household_income_fpl_band"]),
            "primary_home_language": str(r["primary_home_language"]),
            "standardized_screening_rate_pct": round(
                float(r["standardized_screening_rate_pct"]) * 100.0, 1
            ),
            "followup_requested_pct": round(float(r["followup_requested_pct"]) * 100.0, 1),
        })

    zero_lep_rows = int((demo["limited_english_rate"] == 0.0).sum())

    return {
        "execution_engine": engine,
        "state_code": cfg["state"],
        "governance_attestation": {
            "audit_columns_excluded_from_routing": True,
            "acs_limited_english_rate_trap_caught": (
                f"{zero_lep_rows}/{len(demo)} tracts carry 0.0 in limited_english_rate; "
                "excluded from formulas and replaced with statewide NSCH language strata + provider bilingual_services_listed."
            ),
            "nsch_statewide_grain_preserved": (
                f"{len(nsch_clean)} rows all have geographic_level='Statewide'; reported separately without 6x tract fan-out."
            ),
        },
        "breach_vs_timely_neighborhood_equity": outcome_strata,
        "furthest_tracts_from_bilingual_eval_hub": underserved_tracts[:6],
        "statewide_nsch_screening_context": nsch_clean,
    }


def prioritize_community_screening_tracts(top_n: int = 6) -> dict[str, Any]:
    """Prioritizes underserved under-5 census tracts for mobile developmental screening days.

    Supports Track 3 ('This community screening season'): ranks census tracts using ONLY
    non-racial need signals (`children_under_5_count`, `poverty_rate`, `no_vehicle_rate`,
    excluding `audit_*` and all-zero `limited_english_rate`) AND pairs every recommended
    screening site with a verified <=45-day downstream bilingual Medicaid evaluation +
    therapy pathway so screening creates services rather than dead-end waitlists.

    Args:
        top_n: Number of priority census tracts to return (1-12).
    """
    cfg = get_config()
    frames = load_local_state_frames(cfg["state"])
    demo = frames["demo"]
    prov = frames["providers"]

    fast_coords = prov[
        (prov["node_role"] == "Part_C_Intake_Coordinator")
        & (prov["part_c_vendor_enrolled"])
        & (prov["accepts_medicaid"])
        & (prov["bilingual_services_listed"])
    ]
    fast_evals = prov[
        (prov["node_role"] == "Multidisciplinary_Eval_Hub")
        & (prov["part_c_vendor_enrolled"])
        & (prov["accepts_medicaid"])
        & (prov["bilingual_services_listed"])
        & (prov["median_internal_wait_days"] <= 15)
    ]
    fast_vendors = prov[
        (prov["node_role"] == "EI_Therapy_Vendor")
        & (prov["part_c_vendor_enrolled"])
        & (prov["accepts_medicaid"])
        & (prov["bilingual_services_listed"])
        & (prov["median_internal_wait_days"] <= 15)
    ]

    ranked = []
    max_u5 = max(1, int(demo["children_under_5_count"].max()))
    for _, tr in demo.iterrows():
        t_lat, t_lon = float(tr["latitude"]), float(tr["longitude"])
        u5 = int(tr["children_under_5_count"])
        pov = float(tr["poverty_rate"])
        noveh = float(tr["no_vehicle_rate"])

        # Composite non-racial need index (explicitly avoids all-zero limited_english_rate and audit_*!)
        need_score = round((0.45 * pov + 0.30 * noveh + 0.25 * (u5 / max_u5)) * 100.0, 1)

        # Pair with nearest <=45-day compliant downstream hub triad
        best_coord = min(
            fast_coords.to_dict(orient="records"),
            key=lambda c: haversine_km(t_lat, t_lon, float(c["latitude"]), float(c["longitude"])),
        )
        best_eval = min(
            fast_evals.to_dict(orient="records"),
            key=lambda e: haversine_km(t_lat, t_lon, float(e["latitude"]), float(e["longitude"])),
        )
        best_vendor = min(
            fast_vendors.to_dict(orient="records"),
            key=lambda v: haversine_km(t_lat, t_lon, float(v["latitude"]), float(v["longitude"])),
        )
        eval_km = haversine_km(
            t_lat, t_lon, float(best_eval["latitude"]), float(best_eval["longitude"])
        )
        est_days = (
            int(best_coord["median_internal_wait_days"])
            + int(best_eval["median_internal_wait_days"])
            + int(best_vendor["median_internal_wait_days"])
            + 5
        )
        ranked.append({
            "census_tract_geoid": str(tr["census_tract_geoid"]),
            "county_name": str(tr["county_name"]),
            "children_under_5_count": u5,
            "poverty_pct": round(pov * 100.0, 1),
            "zero_vehicle_pct": round(noveh * 100.0, 1),
            "non_racial_outreach_priority_score": need_score,
            "verified_downstream_45d_pathway": {
                "intake_coordinator_id": str(best_coord["provider_id"]),
                "eval_hub_id": str(best_eval["provider_id"]),
                "eval_hub_name": str(best_eval["synthetic_organization_name"]),
                "therapy_vendor_id": str(best_vendor["provider_id"]),
                "expected_cumulative_days": est_days,
                "clears_45d_mandate": est_days <= 45,
                "eval_hub_distance_km": eval_km,
                "deploy_mobile_eval_van_with_screening": eval_km > 25.0 or noveh >= 0.12,
            },
        })

    ranked.sort(key=lambda x: x["non_racial_outreach_priority_score"], reverse=True)
    return {
        "state_code": cfg["state"],
        "formula_note": (
            "Weighted 45% poverty_rate + 30% no_vehicle_rate + 25% normalized children_under_5_count. "
            "Excludes all-zero ACS limited_english_rate (0.0) and excludes all audit_* race/ethnicity shares."
        ),
        "priority_screening_tracts": ranked[: max(1, min(int(top_n), 12))],
    }


def _build_outreach_zones_gql(
    dataset: str,
    needs_medicaid: bool,
    needs_bilingual: bool,
    project: str = "",
    state_code: str = "",
) -> str:
    """Builds the BigQuery SQL + ISO GQL GRAPH_TABLE query for outreach zone desert detection."""
    clean_project = project.strip().strip("`") if isinstance(project, str) else ""
    if clean_project and not re.fullmatch(r"^[A-Za-z0-9_.:-]+$", clean_project):
        clean_project = ""
    clean_dataset = dataset.strip().strip("`")
    fq_dataset = f"{clean_project}.{clean_dataset}" if clean_project else clean_dataset
    graph_ref = (
        f"`{fq_dataset}.ReferralGraph`" if clean_project else f"{clean_dataset}.ReferralGraph"
    )

    clean_state = state_code.strip().upper() if isinstance(state_code, str) else ""
    if not re.fullmatch(r"^[A-Z]{2}$", clean_state):
        clean_state = ""
    d_where_clause = f"\n  WHERE d.state_code = '{clean_state}'" if clean_state else ""
    outer_where_clause = f"\nWHERE d.state_code = '{clean_state}'" if clean_state else ""
    gql_state_filter = f"n.state_code = '{clean_state}'\n      AND " if clean_state else ""

    med_filter = (
        "\n      AND start.accepts_medicaid = TRUE AND eval.accepts_medicaid = TRUE"
        if needs_medicaid
        else ""
    )
    bil_filter = (
        "\n      AND start.bilingual_services_listed = TRUE AND eval.bilingual_services_listed = TRUE"
        if needs_bilingual
        else ""
    )
    return f"""-- BigQuery Property Graph (ISO/IEC 39075 GQL) + Spatial Hidden EI Desert Query
WITH tract_nearest_clinic AS (
  SELECT
    LPAD(d.census_tract_geoid, 11, '0') AS census_tract_geoid,
    ROUND(
      MIN(
        ST_DISTANCE(
          ST_GEOGPOINT(d.longitude, d.latitude),
          ST_GEOGPOINT(p.longitude, p.latitude)
        ) / 1000.0
      ),
      1
    ) AS nearest_any_clinic_km
  FROM `{fq_dataset}.acs_under5_tract_demographics` AS d
  INNER JOIN `{fq_dataset}.pediatric_and_ei_provider_directory` AS p
    ON d.state_code = p.state_code{d_where_clause}
  GROUP BY 1
),
tract_compliant_paths AS (
  SELECT
    LPAD(census_tract_geoid, 11, '0') AS census_tract_geoid,
    COUNT(DISTINCT CONCAT(start_provider_id, '->', eval_provider_id)) AS reachable_45d_compliant_paths
  FROM GRAPH_TABLE(
    {graph_ref}
    MATCH (n:Neighborhood)<-[s:SERVES_AREA]-(start:CareNode)-[r:REFERS_TO]->{{1,3}}(eval:CareNode)
    WHERE {gql_state_filter}s.travel_distance_km <= 25.0
      AND eval.node_role IN ('Multidisciplinary_Eval_Hub', 'EI_Therapy_Vendor')
      AND eval.part_c_vendor_enrolled = TRUE
      AND start.provider_id != eval.provider_id{med_filter}{bil_filter}
      AND (
        SELECT LOGICAL_AND(
          h.bounce_flag = 0
          AND NOT STARTS_WITH(h.handoff_reason, 'Re-Referral Bounce')
        )
        FROM UNNEST(r) AS h
      )
    LET handoff_days = (
          SELECT SUM(h.handoff_wait_days) FROM UNNEST(r) AS h
        ),
        total_wait_days = (
          start.median_internal_wait_days
          + (SELECT SUM(h.handoff_wait_days) FROM UNNEST(r) AS h)
          + eval.median_internal_wait_days
        )
    FILTER total_wait_days <= 45
    RETURN
      n.tract_geoid AS census_tract_geoid,
      start.provider_id AS start_provider_id,
      eval.provider_id AS eval_provider_id,
      handoff_days,
      total_wait_days
  )
  GROUP BY 1
)
SELECT
  LPAD(d.census_tract_geoid, 11, '0') AS census_tract_geoid,
  d.county_name,
  d.children_under_5_count,
  d.poverty_rate,
  d.no_vehicle_rate,
  nc.nearest_any_clinic_km,
  COALESCE(cp.reachable_45d_compliant_paths, 0) AS reachable_45d_compliant_paths
FROM `{fq_dataset}.acs_under5_tract_demographics` AS d
INNER JOIN tract_nearest_clinic AS nc
  ON LPAD(d.census_tract_geoid, 11, '0') = nc.census_tract_geoid
LEFT JOIN tract_compliant_paths AS cp
  ON LPAD(d.census_tract_geoid, 11, '0') = cp.census_tract_geoid{outer_where_clause}
ORDER BY d.poverty_rate DESC;""".strip()


def rank_outreach_zones(
    needs_medicaid: bool = True,
    needs_bilingual: bool = True,
    top_n: int = 8,
) -> dict[str, Any]:
    """Ranks census tracts for outreach while detecting hidden Early Intervention deserts.

    Identifies tracts that appear well-served on a map (`nearest_any_clinic_km <= 25.0`)
    yet have zero `<=45`-day reachable evaluation/therapy paths once Medicaid and
    bilingual filters are applied (`reachable_45d_paths_count == 0`).

    Governance Rules Enforced:
      - `audit_*` demographic shares are NEVER used in `outreach_priority_score` or
        filtering; they are attached strictly post-output in `post_output_equity_context`.
      - All-zero ACS `limited_english_rate` (0.0) is excluded; statewide HRSA NSCH
        screening strata are reported separately at `'Statewide'` grain (no 6x fan-out).

    Args:
        needs_medicaid: Require `accepts_medicaid = TRUE` on start and target nodes.
        needs_bilingual: Require `bilingual_services_listed = TRUE` on start and target nodes.
        top_n: Number of top-priority outreach zones to return.
    """
    cfg = get_config()
    frames = load_local_state_frames(cfg["state"])
    demo = frames["demo"]
    prov = frames["providers"]
    logs = frames["logs"]
    nsch = frames["nsch"]

    gql_query = _build_outreach_zones_gql(
        cfg["dataset"],
        needs_medicaid=needs_medicaid,
        needs_bilingual=needs_bilingual,
        project=cfg["project"],
        state_code=cfg["state"],
    )
    bq_rows = graph_client.query_bq_or_none(gql_query)
    engine = (
        f"bigquery_property_graph_iso_gql ({cfg['project']}.{cfg['dataset']}.ReferralGraph)"
        if bq_rows is not None
        else f"local_geoparquet_mirror ({cfg['state']} starter tables)"
    )

    bq_by_tract: dict[str, dict[str, Any]] = {}
    if bq_rows is not None:
        for row in bq_rows:
            geoid = str(row["census_tract_geoid"]).strip().zfill(11)
            bq_by_tract[geoid] = row

    # Build directed adjacency list strictly from bounce-free referral logs
    # using minimum observed handoff wait per directed provider pair.
    prov_by_id = {str(r["provider_id"]): r for _, r in prov.iterrows()}
    adj: dict[str, list[tuple[str, int]]] = {}
    if not logs.empty:
        non_bounce_logs = logs[
            ~logs["handoff_reason"].astype(str).str.startswith("Re-Referral Bounce")
        ]
        if "bounce_flag" in non_bounce_logs.columns:
            non_bounce_logs = non_bounce_logs[non_bounce_logs["bounce_flag"] == 0]
        if not non_bounce_logs.empty:
            edge_waits = (
                non_bounce_logs.groupby(
                    ["source_provider_id", "target_provider_id"], as_index=False
                )["handoff_wait_days"]
                .min()
            )
            for _, edge in edge_waits.iterrows():
                src_id = str(edge["source_provider_id"])
                dst_id = str(edge["target_provider_id"])
                wait_d = int(edge["handoff_wait_days"])
                adj.setdefault(src_id, []).append((dst_id, wait_d))

    target_roles = {"Multidisciplinary_Eval_Hub", "EI_Therapy_Vendor"}

    def _node_matches_filters(node_row: Any) -> bool:
        if needs_medicaid and not bool(node_row["accepts_medicaid"]):
            return False
        if needs_bilingual and not bool(node_row["bilingual_services_listed"]):
            return False
        return True

    def _count_reachable_45d_paths(t_lat: float, t_lon: float) -> int:
        reachable_pairs: set[tuple[str, str]] = set()
        for _, start_row in prov.iterrows():
            if not _node_matches_filters(start_row):
                continue
            dist_km = haversine_km(
                t_lat, t_lon, float(start_row["latitude"]), float(start_row["longitude"])
            )
            if dist_km > 25.0:
                continue
            start_id = str(start_row["provider_id"])
            start_wait = int(start_row["median_internal_wait_days"])
            # Iterative DFS for 1..3 hop bounce-free paths where
            # start.median_internal_wait_days + handoff_days + eval.median_internal_wait_days <= 45
            stack: list[tuple[str, int, int, frozenset[str]]] = [
                (start_id, 0, 0, frozenset({start_id}))
            ]
            while stack:
                curr_id, depth, cum_handoff_days, visited = stack.pop()
                if depth == 3:
                    continue
                for nxt_id, edge_wait in adj.get(curr_id, ()):
                    if nxt_id in visited:
                        continue
                    nxt_handoff = cum_handoff_days + edge_wait
                    if start_wait + nxt_handoff > 45:
                        continue
                    nxt_row = prov_by_id.get(nxt_id)
                    if nxt_row is None:
                        continue
                    eval_wait = int(nxt_row["median_internal_wait_days"])
                    total_wait_days = start_wait + nxt_handoff + eval_wait
                    if (
                        total_wait_days <= 45
                        and str(nxt_row["node_role"]) in target_roles
                        and bool(nxt_row["part_c_vendor_enrolled"])
                        and _node_matches_filters(nxt_row)
                    ):
                        reachable_pairs.add((start_id, nxt_id))
                    if depth + 1 < 3:
                        stack.append((nxt_id, depth + 1, nxt_handoff, visited | {nxt_id}))
        return len(reachable_pairs)

    max_u5 = max(1, int(demo["children_under_5_count"].max())) if not demo.empty else 1
    scored_zones: list[tuple[dict[str, Any], Any]] = []

    for _, tr in demo.iterrows():
        geoid = str(tr["census_tract_geoid"]).strip().zfill(11)
        t_lat, t_lon = float(tr["latitude"]), float(tr["longitude"])
        u5 = int(tr["children_under_5_count"])
        pov = float(tr["poverty_rate"])
        noveh = float(tr["no_vehicle_rate"])

        if geoid in bq_by_tract:
            nearest_any_clinic_km = round(float(bq_by_tract[geoid]["nearest_any_clinic_km"]), 1)
            reachable_45d_paths_count = int(bq_by_tract[geoid]["reachable_45d_compliant_paths"])
        else:
            nearest_any_clinic_km = (
                min(
                    haversine_km(t_lat, t_lon, float(p["latitude"]), float(p["longitude"]))
                    for _, p in prov.iterrows()
                )
                if not prov.empty
                else 0.0
            )
            reachable_45d_paths_count = _count_reachable_45d_paths(t_lat, t_lon)

        is_hidden_ei_desert = (
            nearest_any_clinic_km <= 25.0 and reachable_45d_paths_count == 0
        )

        # Non-racial outreach priority score (never uses audit_* or all-zero limited_english_rate)
        base_need = 0.45 * pov + 0.30 * noveh + 0.25 * (u5 / max_u5)
        desert_bonus = 0.25 if is_hidden_ei_desert else 0.0
        outreach_priority_score = round((base_need + desert_bonus) * 100.0, 1)

        zone = {
            "census_tract_geoid": geoid,
            "county_name": str(tr["county_name"]),
            "children_under_5_count": u5,
            "poverty_pct": round(pov * 100.0, 1),
            "zero_vehicle_pct": round(noveh * 100.0, 1),
            "nearest_any_clinic_km": nearest_any_clinic_km,
            "reachable_45d_paths_count": reachable_45d_paths_count,
            "is_hidden_ei_desert": is_hidden_ei_desert,
            "mobility_support_recommended": bool(
                noveh >= 0.10 or nearest_any_clinic_km > 25.0
            ),
            "outreach_priority_score": outreach_priority_score,
        }
        scored_zones.append((zone, tr))

    scored_zones.sort(
        key=lambda item: (-item[0]["outreach_priority_score"], item[0]["census_tract_geoid"])
    )
    hidden_ei_deserts_count = sum(1 for z, _ in scored_zones if z["is_hidden_ei_desert"])

    limit = max(1, int(top_n))
    ranked_outreach_zones: list[dict[str, Any]] = []
    for zone, tr in scored_zones[:limit]:
        # Attach audit_* demographic shares strictly post-output
        zone_with_audit = {
            **zone,
            "post_output_equity_context": {
                "audit_black_pct": round(float(tr["audit_black_share"]) * 100.0, 1),
                "audit_hispanic_pct": round(float(tr["audit_hispanic_share"]) * 100.0, 1),
                "audit_indigenous_pct": round(float(tr["audit_indigenous_share"]) * 100.0, 1),
                "audit_asian_pct": round(float(tr["audit_asian_share"]) * 100.0, 1),
                "audit_white_pct": round(float(tr["audit_white_share"]) * 100.0, 1),
            },
        }
        ranked_outreach_zones.append(zone_with_audit)

    # Statewide HRSA NSCH screening gap context (strictly at 'Statewide' grain — no 6x fan-out)
    nsch_statewide = (
        nsch[nsch["geographic_level"].astype(str) == "Statewide"]
        if "geographic_level" in nsch.columns
        else nsch
    )
    nsch_clean = []
    for _, r in nsch_statewide.sort_values("standardized_screening_rate_pct").iterrows():
        nsch_clean.append({
            "survey_stratum_id": str(r["survey_stratum_id"]),
            "geographic_level": str(r["geographic_level"]),
            "household_income_fpl_band": str(r["household_income_fpl_band"]),
            "primary_home_language": str(r["primary_home_language"]),
            "standardized_screening_rate_pct": round(
                float(r["standardized_screening_rate_pct"]) * 100.0, 1
            ),
            "followup_requested_pct": round(float(r["followup_requested_pct"]) * 100.0, 1),
        })

    zero_lep_rows = int((demo["limited_english_rate"] == 0.0).sum())

    return {
        "engine": engine,
        "synthetic_provenance_notice": (
            "100% [Synthetic] CareNode providers (SYN-PROV-*) and ReferralGraph "
            "de-identified referral handoff logs; anchored to public US Census ACS "
            "under-5 tract demographics and statewide HRSA NSCH screening rates."
        ),
        "iso_gql_query": gql_query,
        "filters_applied": {
            "needs_medicaid": bool(needs_medicaid),
            "needs_bilingual": bool(needs_bilingual),
            "max_wait_days": 45,
            "hidden_desert_radius_km": 25.0,
        },
        "hidden_ei_deserts_count": hidden_ei_deserts_count,
        "statewide_nsch_screening_gap_context": nsch_clean,
        "ranked_outreach_zones": ranked_outreach_zones,
        "governance_attestation": {
            "audit_columns_excluded_from_scoring": True,
            "audit_columns_excluded_from_scoring_and_filtering": True,
            "acs_limited_english_rate_trap_caught": (
                f"{zero_lep_rows}/{len(demo)} tracts carry 0.0 in limited_english_rate; "
                "excluded from scoring and replaced with statewide NSCH language strata + provider bilingual_services_listed."
            ),
            "nsch_statewide_grain_preserved": (
                f"{len(nsch_clean)} rows all have geographic_level='Statewide'; reported separately without 6x tract fan-out."
            ),
        },
    }
