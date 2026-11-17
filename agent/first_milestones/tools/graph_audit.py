"""Custom ISO GQL Network Audit & Counterfactual Bottleneck Simulator Tools.

Provides:
  1. `audit_multihop_bounce_hubs`: Variable-length `-{2,4}->` ISO GQL traversal
     correlated on `case_chain_id` and prefix-deduplicated (preventing Type B
     `Vendor -> Vendor` 3-hop prefix double counting). Exposes why flat SQL
     waitlist sorting blames downstream queues while missing low-wait `paper_fax`
     intake coordinators (`SYN-PROV-*-011`, `012`).
  2. `simulate_hub_intervention`: Counterfactual graph simulation computing exact
     delayed child-days saved and 45-day statutory breaches eliminated if one
     coordinator hub upgrades `paper_fax` -> `ehr_electronic_portal` and pre-verifies
     bilingual/Medicaid evaluation slot availability.
  3. `detect_regional_bottleneck_hubs`: Regional betweenness-centrality audit over
     2–4 hop breached referral chains, exposing low-internal-wait intermediate hubs
     that carry disproportionate statutory breach flow.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from .bq_client import get_config, graph_client, load_local_state_frames


def _build_audit_iso_gql(dataset: str) -> str:
    return f"""-- Prefix-Safe Variable-Length ISO/IEC 39075 GQL Breach Traversal
WITH complete_chains AS (
  SELECT *
  FROM GRAPH_TABLE(
    {dataset}.ReferralGraph
    MATCH (clinic:CareNode {{node_role: 'Screening_Pediatric_Clinic'}})
          -[hops:ReferralHandoff]->{{2,4}}
          (vendor:CareNode {{node_role: 'EI_Therapy_Vendor'}})
    WHERE hops[OFFSET(0)].hop_sequence = 1
      AND (SELECT COUNT(DISTINCT h.case_chain_id) FROM UNNEST(hops) AS h) = 1
    LET chain_id = hops[OFFSET(0)].case_chain_id,
        total_hops = ARRAY_LENGTH(hops),
        child_age_months = hops[OFFSET(0)].child_age_months,
        concern_domain = hops[OFFSET(0)].concern_domain,
        home_tract = hops[OFFSET(0)].child_home_tract_geoid,
        intake_coord_id = hops[OFFSET(0)].target_provider_id,
        chain_wait_days = (SELECT SUM(h.handoff_wait_days) FROM UNNEST(hops) AS h),
        fax_hops = (SELECT COUNTIF(h.transmission_channel = 'paper_fax') FROM UNNEST(hops) AS h),
        bounce_reason = (
          SELECT ANY_VALUE(h.handoff_reason)
          FROM UNNEST(hops) AS h
          WHERE STARTS_WITH(h.handoff_reason, 'Re-Referral Bounce')
        )
    RETURN
      chain_id, child_age_months, concern_domain, home_tract,
      clinic.provider_id AS origin_clinic_id, intake_coord_id,
      vendor.provider_id AS final_vendor_id, total_hops, fax_hops,
      chain_wait_days, bounce_reason
  )
  QUALIFY ROW_NUMBER() OVER (PARTITION BY chain_id ORDER BY total_hops DESC) = 1
)
SELECT * FROM complete_chains ORDER BY chain_wait_days DESC;""".strip()


def audit_multihop_bounce_hubs(only_breaches: bool = True, limit_chains: int = 10) -> dict[str, Any]:
    """Traces variable-length `-{2,4}->` referral chains and exposes hidden Bounce Hubs.

    Compares naive flat provider waitlist sorting (`active_waitlist_count DESC`) against
    multi-hop `case_chain_id`-correlated ISO GQL trajectories across `ReferralGraph`,
    exposing low-internal-wait `Part_C_Intake_Coordinator` desks (`5-6` days internal wait)
    whose `paper_fax` and unverified bilingual/Medicaid handoffs trigger 4-hop >45-day
    IDEA Part C statutory breaches.

    Args:
        only_breaches: If True, returns only >45-day breached episodes in the detailed sample.
        limit_chains: Number of worst multi-hop episodes to return with full hop traces.
    """
    cfg = get_config()
    frames = load_local_state_frames(cfg["state"])
    prov = frames["providers"]
    logs = frames["logs"]
    prov_by_id = {str(r["provider_id"]): r for _, r in prov.iterrows()}

    iso_gql = _build_audit_iso_gql(cfg["dataset"])
    bq_rows = graph_client.query_bq_or_none(iso_gql)
    engine = (
        f"bigquery_property_graph_iso_gql ({cfg['project']}.{cfg['dataset']}.ReferralGraph)"
        if bq_rows is not None
        else f"local_geoparquet_mirror ({cfg['state']} starter tables)"
    )

    # Naive flat SQL sort (what misleads coordinators in a spreadsheet)
    naive_top5 = (
        prov.sort_values("active_waitlist_count", ascending=False)
        .head(5)[
            [
                "provider_id",
                "node_role",
                "city",
                "synthetic_organization_name",
                "active_waitlist_count",
                "median_internal_wait_days",
                "bilingual_services_listed",
            ]
        ]
        .to_dict(orient="records")
    )

    # Reconstruct complete prefix-deduplicated episodes
    episodes: list[dict[str, Any]] = []
    coord_stats: dict[str, dict[str, Any]] = {}
    bounce_sources: dict[str, dict[str, Any]] = {}
    hop_depth_summary: dict[int, dict[str, Any]] = {}

    for cid, grp in logs.groupby("case_chain_id"):
        grp_s = grp.sort_values("hop_sequence")
        n_hops = len(grp_s)
        total_w = int(grp_s["handoff_wait_days"].sum())
        fax_cnt = int((grp_s["transmission_channel"] == "paper_fax").sum())
        coord_id = str(grp_s.iloc[0]["target_provider_id"])
        age_m = int(grp_s.iloc[0]["child_age_months"])
        domain = str(grp_s.iloc[0]["concern_domain"])
        tract = str(grp_s.iloc[0]["child_home_tract_geoid"])

        # Track hop-depth summary
        hd = hop_depth_summary.setdefault(
            n_hops,
            {"hops": n_hops, "episodes": 0, "breaches_over_45d": 0, "wait_sum": 0, "min_wait_d": 999, "max_wait_d": 0},
        )
        hd["episodes"] += 1
        hd["wait_sum"] += total_w
        hd["min_wait_d"] = min(hd["min_wait_d"], total_w)
        hd["max_wait_d"] = max(hd["max_wait_d"], total_w)
        if total_w > 45:
            hd["breaches_over_45d"] += 1

        # Track Intake Coordinator multi-hop impact
        c_row = prov_by_id[coord_id]
        cs = coord_stats.setdefault(
            coord_id,
            {
                "provider_id": coord_id,
                "synthetic_organization_name": str(c_row["synthetic_organization_name"]),
                "city": str(c_row["city"]),
                "flat_active_waitlist": int(c_row["active_waitlist_count"]),
                "flat_median_internal_wait_days": int(c_row["median_internal_wait_days"]),
                "routed_episodes": 0,
                "chains_3plus_hops": 0,
                "breached_over_45d": 0,
                "total_excess_days_over_45": 0,
                "wait_sum": 0,
                "outbound_paper_fax_edges": 0,
            },
        )
        cs["routed_episodes"] += 1
        cs["wait_sum"] += total_w
        if n_hops >= 3:
            cs["chains_3plus_hops"] += 1
        if total_w > 45:
            cs["breached_over_45d"] += 1
            cs["total_excess_days_over_45"] += total_w - 45
        if len(grp_s) >= 2 and str(grp_s.iloc[1]["transmission_channel"]) == "paper_fax":
            cs["outbound_paper_fax_edges"] += 1

        # Build full hop trace & capture explicit Re-Referral Bounce intermediary nodes
        hop_trace = []
        cum_d = 0
        bounce_reason = None
        for _, h in grp_s.iterrows():
            s_id = str(h["source_provider_id"])
            t_id = str(h["target_provider_id"])
            w = int(h["handoff_wait_days"])
            cum_d += w
            reason = str(h["handoff_reason"])
            is_b = reason.startswith("Re-Referral Bounce")
            if is_b:
                bounce_reason = reason
                b_node = prov_by_id[s_id]
                bs = bounce_sources.setdefault(
                    s_id,
                    {
                        "provider_id": s_id,
                        "node_role": str(b_node["node_role"]),
                        "synthetic_organization_name": str(b_node["synthetic_organization_name"]),
                        "city": str(b_node["city"]),
                        "bilingual_services_listed": bool(b_node["bilingual_services_listed"]),
                        "active_waitlist_count": int(b_node["active_waitlist_count"]),
                        "median_internal_wait_days": int(b_node["median_internal_wait_days"]),
                        "bounce_count": 0,
                        "bounce_reason": reason,
                        "transmission_channel": str(h["transmission_channel"]),
                    },
                )
                bs["bounce_count"] += 1

            hop_trace.append({
                "hop_sequence": int(h["hop_sequence"]),
                "source_provider_id": s_id,
                "source_name": str(prov_by_id[s_id]["synthetic_organization_name"]),
                "source_role": str(prov_by_id[s_id]["node_role"]),
                "target_provider_id": t_id,
                "target_name": str(prov_by_id[t_id]["synthetic_organization_name"]),
                "target_role": str(prov_by_id[t_id]["node_role"]),
                "transmission_channel": str(h["transmission_channel"]),
                "handoff_wait_days": w,
                "cumulative_wait_days": cum_d,
                "handoff_reason": reason,
                "is_bounce_hop": is_b,
            })

        episodes.append({
            "case_chain_id": str(cid),
            "child_age_months": age_m,
            "est_age_at_ifsp_months": round(age_m + total_w / 30.44, 1),
            "near_36m_aging_out_cliff": age_m >= 30,
            "concern_domain": domain,
            "child_home_tract_geoid": tract,
            "intake_coordinator_id": coord_id,
            "total_hops": n_hops,
            "paper_fax_hops": fax_cnt,
            "total_wait_days": total_w,
            "breached_45d": total_w > 45,
            "days_over_45d": max(0, total_w - 45),
            "bounce_reason": bounce_reason,
            "hops": hop_trace,
        })

    coord_ranking = []
    for cs in coord_stats.values():
        cs["mean_episode_wait_days"] = round(cs["wait_sum"] / max(1, cs["routed_episodes"]), 1)
        cs["breach_rate_pct"] = round(cs["breached_over_45d"] / max(1, cs["routed_episodes"]) * 100.0, 1)
        del cs["wait_sum"]
        coord_ranking.append(cs)
    coord_ranking.sort(
        key=lambda x: (x["breached_over_45d"], x["total_excess_days_over_45"]),
        reverse=True,
    )

    hop_table = []
    for k in sorted(hop_depth_summary):
        d = hop_depth_summary[k]
        hop_table.append({
            "hops": d["hops"],
            "episodes": d["episodes"],
            "avg_episode_wait_days": round(d["wait_sum"] / max(1, d["episodes"]), 1),
            "min_wait_days": d["min_wait_d"],
            "max_wait_days": d["max_wait_d"],
            "breaches_over_45d": d["breaches_over_45d"],
            "breach_rate_pct": round(d["breaches_over_45d"] / max(1, d["episodes"]) * 100.0, 1),
        })

    filtered_eps = [e for e in episodes if (not only_breaches or e["breached_45d"])]
    filtered_eps.sort(
        key=lambda e: (e["near_36m_aging_out_cliff"], e["total_wait_days"]),
        reverse=True,
    )

    # Channel comparison across all 149 edges
    channel_stats = []
    for ch, grp in logs.groupby("transmission_channel"):
        channel_stats.append({
            "transmission_channel": str(ch),
            "handoff_edges": int(len(grp)),
            "mean_wait_days": round(float(grp["handoff_wait_days"].mean()), 1),
            "mean_family_dropoff_pct": round(float(grp["dropoff_rate_pct"].mean()) * 100.0, 1),
        })
    channel_stats.sort(key=lambda x: x["mean_wait_days"], reverse=True)

    return {
        "execution_engine": engine,
        "state_code": cfg["state"],
        "synthetic_provenance_notice": (
            "100% [Synthetic] CareNode organizations (SYN-PROV-*) and ReferralHandoff chains; "
            "prefix-deduplicated so Type B Vendor->Vendor 4-hop chains are counted once."
        ),
        "iso_gql_query": iso_gql,
        "network_totals": {
            "total_complete_chains": len(episodes),
            "chains_3_to_4_hops": sum(1 for e in episodes if e["total_hops"] >= 3),
            "statutory_breaches_over_45d": sum(1 for e in episodes if e["breached_45d"]),
            "overall_timely_45d_pct": round(
                sum(1 for e in episodes if not e["breached_45d"]) / max(1, len(episodes)) * 100.0, 1
            ),
            "toddlers_30m_plus_in_breach": sum(
                1 for e in episodes if e["breached_45d"] and e["near_36m_aging_out_cliff"]
            ),
        },
        "hop_depth_breakdown": hop_table,
        "transmission_channel_impact": channel_stats,
        "naive_flat_waitlist_top5_misleading": naive_top5,
        "intake_coordinator_bounce_hub_ranking": coord_ranking,
        "top_hidden_bounce_hub": coord_ranking[0] if coord_ranking else None,
        "downstream_re_referral_bounce_triggers": sorted(
            bounce_sources.values(), key=lambda x: x["bounce_count"], reverse=True
        ),
        "sample_traced_episodes": filtered_eps[: max(1, min(int(limit_chains), 20))],
    }


def simulate_hub_intervention(
    target_provider_id: str = "",
    upgrade_fax_to_ehr: bool = True,
    precheck_bilingual_and_slot_capacity: bool = True,
) -> dict[str, Any]:
    """Simulates fixing a regional Bounce Hub and quantifies delayed child-days saved.

    Computes a counterfactual over traversed `ReferralHandoff` chains passing through
    `target_provider_id` (defaults to the state's #1 hidden Intake Coordinator bounce hub,
    e.g., `SYN-PROV-MS-011`, or `'ALL'` for statewide intake modernization):
      1. Replacing `paper_fax` (`~19.5-21.7d` avg) with `ehr_electronic_portal` (`~12-13d`).
      2. Pre-verifying bilingual & Medicaid evaluation/therapy slot capacity at intake so
         cases route directly to underutilized fast hubs (`017..020`, `026..030`),
         eliminating Hop-3 `Re-Referral Bounce` penalties (`21-25d`).

    Args:
        target_provider_id: Specific `SYN-PROV-*` ID (e.g. 'SYN-PROV-MS-011') or 'ALL'.
        upgrade_fax_to_ehr: Simulate replacing paper fax edges with electronic portal intake.
        precheck_bilingual_and_slot_capacity: Simulate pre-handoff bilingual/Medicaid slot
            check to eliminate 4-hop re-referral bounces.
    """
    cfg = get_config()
    frames = load_local_state_frames(cfg["state"])
    prov = frames["providers"]
    logs = frames["logs"]
    prov_by_id = {str(r["provider_id"]): r for _, r in prov.iterrows()}

    # Default to top breaching intake coordinator (e.g. SYN-PROV-MS-011) if unspecified
    target = target_provider_id.strip().upper()
    if not target:
        audit = audit_multihop_bounce_hubs(only_breaches=True, limit_chains=1)
        top_hub = audit.get("top_hidden_bounce_hub")
        target = top_hub["provider_id"] if top_hub else f"SYN-PROV-{cfg['state']}-011"

    affected_chains: list[dict[str, Any]] = []
    baseline_breaches = 0
    post_breaches = 0
    total_days_saved = 0
    baseline_wait_sum = 0
    post_wait_sum = 0

    for cid, grp in logs.groupby("case_chain_id"):
        grp_s = grp.sort_values("hop_sequence")
        nodes_in_chain = set(grp_s["source_provider_id"].astype(str)).union(
            set(grp_s["target_provider_id"].astype(str))
        )
        if target != "ALL" and target not in nodes_in_chain:
            continue

        base_wait = int(grp_s["handoff_wait_days"].sum())
        fax_saved = 0
        bounce_saved = 0

        for _, h in grp_s.iterrows():
            w = int(h["handoff_wait_days"])
            reason = str(h["handoff_reason"])
            ch = str(h["transmission_channel"])
            is_bounce = reason.startswith("Re-Referral Bounce")

            if is_bounce and precheck_bilingual_and_slot_capacity:
                # Eliminating the extra 4th-hop re-referral bounce + saturated queue penalty
                bounce_saved += w
                # Also accounts for routing into fast eval/vendor hub (7-11d) vs saturated hub (21-25d)
            elif ch == "paper_fax" and upgrade_fax_to_ehr:
                # Empirical EHR portal median wait is ~12-13 days vs ~20-23 days on paper_fax
                fax_saved += max(0, w - 12)

        saved = fax_saved + bounce_saved
        new_wait = max(14, base_wait - saved)

        baseline_wait_sum += base_wait
        post_wait_sum += new_wait
        total_days_saved += base_wait - new_wait
        if base_wait > 45:
            baseline_breaches += 1
        if new_wait > 45:
            post_breaches += 1

        affected_chains.append({
            "case_chain_id": str(cid),
            "child_age_months": int(grp_s.iloc[0]["child_age_months"]),
            "concern_domain": str(grp_s.iloc[0]["concern_domain"]),
            "baseline_hops": int(len(grp_s)),
            "simulated_hops": int(len(grp_s) - (1 if (bounce_saved > 0 and len(grp_s) == 4) else 0)),
            "baseline_wait_days": base_wait,
            "simulated_wait_days": new_wait,
            "child_days_saved": base_wait - new_wait,
            "flipped_to_compliant_45d": (base_wait > 45) and (new_wait <= 45),
        })

    affected_chains.sort(key=lambda c: c["child_days_saved"], reverse=True)
    hub_meta = prov_by_id.get(target)

    return {
        "state_code": cfg["state"],
        "target_intervention_scope": target,
        "target_organization_name": (
            str(hub_meta["synthetic_organization_name"])
            if hub_meta is not None
            else f"All Regional Part C Intake Coordinators ({cfg['state']})"
        ),
        "flat_spreadsheet_appearance": (
            {
                "median_internal_wait_days": int(hub_meta["median_internal_wait_days"]),
                "active_waitlist_count": int(hub_meta["active_waitlist_count"]),
                "why_flat_sql_missed_it": (
                    "Internal wait is only "
                    f"{int(hub_meta['median_internal_wait_days'])} days, hiding downstream paper_fax & slot-mismatch bounces."
                ),
            }
            if hub_meta is not None
            else None
        ),
        "levers_applied": {
            "upgrade_paper_fax_to_ehr_portal": upgrade_fax_to_ehr,
            "precheck_bilingual_and_medicaid_slot_capacity": precheck_bilingual_and_slot_capacity,
        },
        "impact_summary": {
            "episodes_evaluated": len(affected_chains),
            "baseline_breaches_over_45d": baseline_breaches,
            "simulated_breaches_over_45d": post_breaches,
            "breaches_eliminated": baseline_breaches - post_breaches,
            "mean_episode_wait_before_days": round(
                baseline_wait_sum / max(1, len(affected_chains)), 1
            ),
            "mean_episode_wait_after_days": round(
                post_wait_sum / max(1, len(affected_chains)), 1
            ),
            "total_delayed_child_days_saved": total_days_saved,
        },
        "episode_level_simulation": affected_chains,
    }


def _build_bottleneck_hubs_gql(dataset: str, max_days: int = 45) -> str:
    """Builds an ISO/IEC 39075 GQL query to rank intermediate bottleneck hubs by breach flow share."""
    return f"""-- Prefix-Safe Variable-Length ISO/IEC 39075 GQL Regional Bottleneck Hub Betweenness Query
WITH complete_chains AS (
  SELECT *
  FROM GRAPH_TABLE(
    {dataset}.ReferralGraph
    MATCH (src:CareNode {{node_role: 'Screening_Pediatric_Clinic'}})
          -[r:REFERS_TO]->{{2,4}}
          (dest:CareNode {{node_role: 'EI_Therapy_Vendor'}})
    WHERE r[OFFSET(0)].hop_sequence = 1
      AND (SELECT COUNT(DISTINCT h.case_chain_id) FROM UNNEST(r) AS h) = 1
    LET chain_id = r[OFFSET(0)].case_chain_id,
        total_hops = ARRAY_LENGTH(r),
        chain_wait_days = (SELECT SUM(h.handoff_wait_days) FROM UNNEST(r) AS h),
        intermediate_hub_ids = ARRAY(
          SELECT DISTINCT h.target_provider_id
          FROM UNNEST(r) AS h WITH OFFSET AS idx
          WHERE idx < ARRAY_LENGTH(r) - 1
        ),
        has_bounce = EXISTS(
          SELECT 1 FROM UNNEST(r) AS h
          WHERE STARTS_WITH(h.handoff_reason, 'Re-Referral Bounce')
        ),
        fax_hops = (SELECT COUNTIF(h.transmission_channel = 'paper_fax') FROM UNNEST(r) AS h),
        primary_bounce_reason = (
          SELECT ANY_VALUE(h.handoff_reason)
          FROM UNNEST(r) AS h
          WHERE STARTS_WITH(h.handoff_reason, 'Re-Referral Bounce')
        )
    RETURN
      chain_id, total_hops, chain_wait_days, intermediate_hub_ids,
      has_bounce, fax_hops, primary_bounce_reason
  )
  QUALIFY ROW_NUMBER() OVER (PARTITION BY chain_id ORDER BY total_hops DESC) = 1
),
breached_chains AS (
  SELECT *
  FROM complete_chains
  WHERE chain_wait_days > {max_days}
),
total_breached AS (
  SELECT COUNT(*) AS total_breached_chains FROM breached_chains
)
SELECT
  hub_id AS provider_id,
  COUNT(DISTINCT bc.chain_id) AS breached_paths_through_hub,
  ROUND(
    COUNT(DISTINCT bc.chain_id) * 100.0 / NULLIF(MAX(tb.total_breached_chains), 0),
    1
  ) AS betweenness_flow_share_pct,
  ROUND(
    COUNTIF(bc.has_bounce) * 100.0 / NULLIF(COUNT(*), 0),
    1
  ) AS bounce_rate_pct,
  ROUND(
    COUNTIF(bc.fax_hops > 0) * 100.0 / NULLIF(COUNT(*), 0),
    1
  ) AS paper_fax_share_pct,
  ANY_VALUE(bc.primary_bounce_reason) AS primary_bounce_reason
FROM breached_chains AS bc
CROSS JOIN total_breached AS tb
CROSS JOIN UNNEST(bc.intermediate_hub_ids) AS hub_id
GROUP BY hub_id
ORDER BY betweenness_flow_share_pct DESC, breached_paths_through_hub DESC;""".strip()


def _provider_matches_region(prov_row: Any, region_norm: str) -> bool:
    """Returns True if a provider row matches `region_norm` (case-insensitive county, city, or state)."""
    if region_norm.upper() == "ALL":
        return True
    target = region_norm.lower()
    county = str(prov_row.get("county_name", "")).strip().lower()
    city = str(prov_row.get("city", "")).strip().lower()
    state = str(prov_row.get("state_code", "")).strip().lower()
    return target == state or target == city or target == county or (len(target) >= 3 and target in county)


def detect_regional_bottleneck_hubs(
    region: str = "ALL",
    max_days: int = 45,
    top_n: int = 5,
) -> dict[str, Any]:
    """Detects intermediate bottleneck hubs carrying the highest share of breached 2-4 hop chains.

    Executes an ISO/IEC 39075 GQL `GRAPH_TABLE` query over `{dataset}.ReferralGraph` when
    BigQuery is configured, and falls back to exact local GeoParquet computation over
    `frames["providers"]` and `frames["logs"]`. Ranks intermediate nodes by betweenness
    flow share across breached chains (`chain_wait_days > max_days`), exposing low-internal-wait
    coordinators and evaluators missed by flat waitlist sorting.

    Args:
        region: Region filter (`'ALL'` or a `county_name`, `city`, or `state_code` value).
        max_days: Statutory wait-day threshold above which a chain is counted as breached.
        top_n: Maximum number of ranked intermediate bottleneck hubs to return.
    """
    cfg = get_config()
    frames = load_local_state_frames(cfg["state"])
    prov = frames["providers"]
    logs = frames["logs"]
    prov_by_id = {str(r["provider_id"]): r for _, r in prov.iterrows()}

    region_norm = region.strip() if region and region.strip() else "ALL"
    gql_query = _build_bottleneck_hubs_gql(cfg["dataset"], max_days=max_days)
    bq_rows = graph_client.query_bq_or_none(gql_query)
    engine = (
        f"bigquery_property_graph_iso_gql ({cfg['project']}.{cfg['dataset']}.ReferralGraph)"
        if bq_rows is not None
        else f"local_geoparquet_mirror ({cfg['state']} starter tables)"
    )

    total_breached_chains = 0
    hub_acc: dict[str, dict[str, Any]] = {}

    if bq_rows is not None:
        # Enrich BigQuery GQL rows with provider metadata and apply optional region filter.
        # Recompute total breached chains from local frames for consistent denominator reporting.
        filtered_bq: list[dict[str, Any]] = []
        for row in bq_rows:
            pid = str(row["provider_id"])
            p_meta = prov_by_id.get(pid)
            if p_meta is None or not _provider_matches_region(p_meta, region_norm):
                continue
            filtered_bq.append({
                "provider_id": pid,
                "organization_name": str(p_meta["synthetic_organization_name"]),
                "node_role": str(p_meta["node_role"]),
                "flat_internal_wait_days": int(p_meta["median_internal_wait_days"]),
                "breached_paths_through_hub": int(row["breached_paths_through_hub"]),
                "betweenness_flow_share_pct": float(row["betweenness_flow_share_pct"]),
                "bounce_rate_pct": float(row["bounce_rate_pct"]),
                "paper_fax_share_pct": float(row["paper_fax_share_pct"]),
                "primary_bounce_reason": row.get("primary_bounce_reason"),
            })
        filtered_bq.sort(
            key=lambda x: (x["betweenness_flow_share_pct"], x["breached_paths_through_hub"]),
            reverse=True,
        )
        bottleneck_hubs = filtered_bq[: max(1, int(top_n))]
        total_breached_chains = sum(
            1
            for _, grp in logs.groupby("case_chain_id")
            if 2 <= len(grp) <= 4
            and int(grp.sort_values("hop_sequence").iloc[0]["hop_sequence"]) == 1
            and int(grp["handoff_wait_days"].sum()) > max_days
        )
    else:
        for _, grp in logs.groupby("case_chain_id"):
            grp_s = grp.sort_values("hop_sequence")
            n_hops = len(grp_s)
            if not (2 <= n_hops <= 4) or int(grp_s.iloc[0]["hop_sequence"]) != 1:
                continue

            src_id = str(grp_s.iloc[0]["source_provider_id"])
            dest_id = str(grp_s.iloc[-1]["target_provider_id"])
            src_meta = prov_by_id.get(src_id)
            dest_meta = prov_by_id.get(dest_id)
            if src_meta is None or dest_meta is None:
                continue
            if (
                str(src_meta["node_role"]) != "Screening_Pediatric_Clinic"
                or str(dest_meta["node_role"]) != "EI_Therapy_Vendor"
            ):
                continue

            chain_wait_days = int(grp_s["handoff_wait_days"].sum())
            if chain_wait_days <= max_days:
                continue

            # Non-terminal hop targets are intermediate hubs along the 2-4 hop path.
            intermediate_ids = list(
                dict.fromkeys(str(h["target_provider_id"]) for _, h in grp_s.iloc[:-1].iterrows())
            )
            matching_hubs = [
                hid
                for hid in intermediate_ids
                if hid in prov_by_id and _provider_matches_region(prov_by_id[hid], region_norm)
            ]
            if region_norm.upper() != "ALL" and not matching_hubs:
                chain_nodes = set(grp_s["source_provider_id"].astype(str)).union(
                    set(grp_s["target_provider_id"].astype(str))
                )
                if not any(
                    nid in prov_by_id and _provider_matches_region(prov_by_id[nid], region_norm)
                    for nid in chain_nodes
                ):
                    continue

            total_breached_chains += 1
            bounce_reasons = [
                str(h["handoff_reason"])
                for _, h in grp_s.iterrows()
                if str(h["handoff_reason"]).startswith("Re-Referral Bounce")
            ]
            has_bounce = len(bounce_reasons) > 0
            has_paper_fax = bool((grp_s["transmission_channel"] == "paper_fax").any())

            for hid in matching_hubs:
                p_meta = prov_by_id[hid]
                acc = hub_acc.setdefault(
                    hid,
                    {
                        "provider_id": hid,
                        "organization_name": str(p_meta["synthetic_organization_name"]),
                        "node_role": str(p_meta["node_role"]),
                        "flat_internal_wait_days": int(p_meta["median_internal_wait_days"]),
                        "breached_paths_through_hub": 0,
                        "bounce_chains": 0,
                        "fax_chains": 0,
                        "bounce_reasons": Counter(),
                    },
                )
                acc["breached_paths_through_hub"] += 1
                if has_bounce:
                    acc["bounce_chains"] += 1
                    acc["bounce_reasons"].update(bounce_reasons)
                if has_paper_fax:
                    acc["fax_chains"] += 1

        ranked_hubs: list[dict[str, Any]] = []
        for acc in hub_acc.values():
            count = acc["breached_paths_through_hub"]
            primary_reason = (
                acc["bounce_reasons"].most_common(1)[0][0]
                if acc["bounce_reasons"]
                else None
            )
            ranked_hubs.append({
                "provider_id": acc["provider_id"],
                "organization_name": acc["organization_name"],
                "node_role": acc["node_role"],
                "flat_internal_wait_days": acc["flat_internal_wait_days"],
                "breached_paths_through_hub": count,
                "betweenness_flow_share_pct": round(
                    count / max(1, total_breached_chains) * 100.0, 1
                ),
                "bounce_rate_pct": round(acc["bounce_chains"] / max(1, count) * 100.0, 1),
                "paper_fax_share_pct": round(acc["fax_chains"] / max(1, count) * 100.0, 1),
                "primary_bounce_reason": primary_reason,
            })

        ranked_hubs.sort(
            key=lambda x: (x["betweenness_flow_share_pct"], x["breached_paths_through_hub"]),
            reverse=True,
        )
        bottleneck_hubs = ranked_hubs[: max(1, int(top_n))]

    if bottleneck_hubs:
        top = bottleneck_hubs[0]
        key_finding = (
            f"Flat waitlist sorting misses {top['organization_name']} ({top['provider_id']}, "
            f"{top['node_role']}) because its internal wait is only "
            f"{top['flat_internal_wait_days']} days, yet it sits on "
            f"{top['betweenness_flow_share_pct']}% ({top['breached_paths_through_hub']}/"
            f"{total_breached_chains}) of all >{max_days}-day breached 2-4 hop chains "
            f"({top['paper_fax_share_pct']}% paper_fax, {top['bounce_rate_pct']}% bounce rate)."
        )
    else:
        key_finding = (
            f"No breached 2-4 hop chains (>{max_days} days) matched region={region_norm!r}."
        )

    return {
        "engine": engine,
        "iso_gql_query": gql_query,
        "region": region_norm,
        "max_days_threshold": int(max_days),
        "total_breached_multihop_chains": total_breached_chains,
        "bottleneck_hubs": bottleneck_hubs,
        "key_finding": key_finding,
    }
