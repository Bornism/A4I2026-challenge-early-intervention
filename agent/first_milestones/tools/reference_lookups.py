"""Reference lookup tools mirroring `agent/tools.yaml` when previewing offline."""

from __future__ import annotations

from typing import Any

from .bq_client import get_config, load_local_state_frames


def lookup_regional_agency_kpis() -> dict[str, Any]:
    """Fetches regional IDEA Part C lead agency 45-day IFSP compliance KPIs.

    Returns 100% [Synthetic] regional lead agencies (`SYN-PARTC-*`) calibrated to
    US Department of Education OSEP Indicator C7 reports.
    """
    cfg = get_config()
    ag = load_local_state_frames(cfg["state"])["agencies"].copy()
    ag["timely_45d_ifsp_pct"] = (
        ag["initial_ifsp_within_45_days_count"]
        / ag["evaluations_completed_count"].clip(lower=1)
        * 100.0
    ).round(1)
    ag = ag.sort_values("timely_45d_ifsp_pct", ascending=True)
    cols = [
        "agency_id",
        "state_code",
        "served_counties",
        "synthetic_agency_name",
        "reporting_fiscal_year",
        "annual_referrals_received",
        "evaluations_completed_count",
        "initial_ifsp_within_45_days_count",
        "timely_45d_ifsp_pct",
        "ifsp_delayed_capacity_count",
        "ifsp_delayed_family_count",
    ]
    return {
        "state_code": cfg["state"],
        "provenance": "100% [Synthetic] regional IDEA Part C hubs calibrated to OSEP Indicator C7",
        "agencies": ag[cols].to_dict(orient="records"),
    }


def lookup_statewide_nsch_strata() -> dict[str, Any]:
    """Retrieves statewide-only HRSA NSCH developmental screening strata (6 rows/state).

    Grain guardrail: `geographic_level = 'Statewide'` across all 6 rows. Never join
    directly to census tracts on `state_code` alone (prevents 6x tract fan-out).
    """
    cfg = get_config()
    nsch = load_local_state_frames(cfg["state"])["nsch"].copy()
    nsch["standardized_screening_rate_pct"] = (nsch["standardized_screening_rate_pct"] * 100.0).round(1)
    nsch["followup_requested_pct"] = (nsch["followup_requested_pct"] * 100.0).round(1)
    nsch["margin_of_error_pct"] = (nsch["margin_of_error_pct"] * 100.0).round(1)
    nsch = nsch.sort_values("standardized_screening_rate_pct", ascending=True)
    cols = [
        "survey_stratum_id",
        "geographic_level",
        "household_income_fpl_band",
        "primary_home_language",
        "standardized_screening_rate_pct",
        "followup_requested_pct",
        "margin_of_error_pct",
    ]
    return {
        "state_code": cfg["state"],
        "grain_guardrail": "Strictly Statewide (6 strata/state). Never raw-join to census tracts on state_code.",
        "acs_lep_trap_note": "Used instead of acs_under5_tract_demographics.limited_english_rate (which is 0.0 across all tracts in this extract).",
        "strata": nsch[cols].to_dict(orient="records"),
    }


def lookup_tract_routing_context(tract_geoid: str = "ALL") -> dict[str, Any]:
    """Looks up non-racial Census ACS under-5 tract context (`audit_*` excluded).

    Args:
        tract_geoid: 11-character census_tract_geoid (preserving leading zeros),
            or 'ALL' for the top 10 highest-poverty under-5 tracts.
    """
    cfg = get_config()
    demo = load_local_state_frames(cfg["state"])["demo"].copy()
    if tract_geoid and tract_geoid.strip().upper() != "ALL":
        padded = tract_geoid.strip().zfill(11)
        demo = demo[demo["census_tract_geoid"] == padded]
    demo = demo.sort_values(["poverty_rate", "children_under_5_count"], ascending=False).head(10)
    rows = []
    for _, r in demo.iterrows():
        rows.append({
            "census_tract_geoid": str(r["census_tract_geoid"]),
            "county_name": str(r["county_name"]),
            "children_under_5_count": int(r["children_under_5_count"]),
            "poverty_pct": round(float(r["poverty_rate"]) * 100.0, 1),
            "zero_vehicle_pct": round(float(r["no_vehicle_rate"]) * 100.0, 1),
            "public_assistance_pct": round(float(r["assistance_rate"]) * 100.0, 1),
            "median_household_income": round(float(r["median_household_income"]), 0),
            "acs_limited_english_rate_trap_all_zero": float(r["limited_english_rate"]),
        })
    return {
        "state_code": cfg["state"],
        "provenance": "Real public US Census ACS 5-Year under-5 demographics (audit_* excluded from routing)",
        "tracts": rows,
    }


def lookup_carenode_directory(role_filter: str = "ALL") -> dict[str, Any]:
    """Lists 100% [Synthetic] CareNode providers sorted by flat active_waitlist_count.

    Args:
        role_filter: One of 'Screening_Pediatric_Clinic', 'Part_C_Intake_Coordinator',
            'Multidisciplinary_Eval_Hub', 'EI_Therapy_Vendor', or 'ALL'.
    """
    cfg = get_config()
    prov = load_local_state_frames(cfg["state"])["providers"].copy()
    if role_filter and role_filter.strip().upper() != "ALL":
        prov = prov[prov["node_role"] == role_filter.strip()]
    prov = prov.sort_values("active_waitlist_count", ascending=False)
    cols = [
        "provider_id",
        "node_role",
        "city",
        "county_name",
        "synthetic_organization_name",
        "part_c_vendor_enrolled",
        "accepts_medicaid",
        "bilingual_services_listed",
        "monthly_slot_capacity",
        "active_waitlist_count",
        "median_internal_wait_days",
    ]
    return {
        "state_code": cfg["state"],
        "provenance": "100% [Synthetic] CareNode vertices (SYN-PROV-*, zero real clinicians)",
        "providers": prov[cols].to_dict(orient="records"),
    }
