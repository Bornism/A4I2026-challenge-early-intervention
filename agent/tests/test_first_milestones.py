"""End-to-end verification tests for First Milestones ADK Agent, Tools & Workbench API."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml
from fastapi.testclient import TestClient

AGENT_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = AGENT_DIR.parent
if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))

from first_milestones import root_agent  # noqa: E402
from first_milestones.tools import (  # noqa: E402
    audit_multihop_bounce_hubs,
    detect_regional_bottleneck_hubs,
    find_compliant_45d_pathways,
    find_viable_45d_paths,
    prioritize_community_screening_tracts,
    rank_outreach_zones,
    run_post_output_equity_audit,
    simulate_hub_intervention,
)
from main import app  # noqa: E402


def test_tools_yaml_and_notebook_valid() -> None:
    tools_cfg = yaml.safe_load((AGENT_DIR / "tools.yaml").read_text(encoding="utf-8"))
    assert "ei_bigquery" in tools_cfg["sources"]
    assert tools_cfg["sources"]["ei_bigquery"]["kind"] == "bigquery"
    assert len(tools_cfg["tools"]) == 4
    assert "first_milestones_bq" in tools_cfg["toolsets"]

    nb = json.loads((REPO_ROOT / "notebooks" / "c_ei_02_graph_and_audit.ipynb").read_text(encoding="utf-8"))
    assert nb["nbformat"] == 4
    assert any("CREATE OR REPLACE PROPERTY GRAPH" in "".join(c["source"]) for c in nb["cells"])


def test_adk_root_agent_loaded() -> None:
    assert root_agent.name == "first_milestones_coordinator"
    assert len(root_agent.tools) >= 6


def test_prefix_deduplicated_audit_and_counterfactual() -> None:
    audit = audit_multihop_bounce_hubs(only_breaches=True, limit_chains=5)
    totals = audit["network_totals"]
    # Exact challenge ground truth: 44 chains, 35 multi-hop (3-4), 26 >45d breaches (zero prefix duplicates!)
    assert totals["total_complete_chains"] == 44
    assert totals["chains_3_to_4_hops"] == 35
    assert totals["statutory_breaches_over_45d"] == 26
    assert "GRAPH_TABLE" in audit["iso_gql_query"]

    top_hub = audit["top_hidden_bounce_hub"]
    assert top_hub is not None
    assert top_hub["flat_median_internal_wait_days"] <= 6
    assert top_hub["breached_over_45d"] >= 7

    sim = simulate_hub_intervention(target_provider_id=top_hub["provider_id"])
    assert sim["impact_summary"]["total_delayed_child_days_saved"] > 100
    assert (
        sim["impact_summary"]["simulated_breaches_over_45d"]
        < sim["impact_summary"]["baseline_breaches_over_45d"]
    )


def test_routing_45d_guardrails_and_zero_audit_leakage() -> None:
    res = find_compliant_45d_pathways(
        child_tract_geoid="28049003500",
        child_age_months=32,
        concern_domain="Social-Communication / Autism Screen",
        needs_medicaid=True,
        needs_bilingual=True,
        has_household_vehicle=False,
    )
    serialized = json.dumps(res)
    for forbidden_col in (
        "audit_black_share",
        "audit_hispanic_share",
        "audit_asian_share",
        "audit_indigenous_share",
        "audit_white_share",
    ):
        assert forbidden_col not in res["child_profile"]
        assert forbidden_col not in json.dumps(res["recommended_pathway"])

    rec = res["recommended_pathway"]
    assert rec is not None
    assert rec["clears_45_day_clock"] is True
    assert rec["expected_cumulative_days"] <= 45
    assert res["cautionary_historical_bounce_chain"]["total_wait_days"] > 45

    alert_codes = {a["code"] for a in res["guardrail_alerts"]}
    assert "IDEA_PART_C_36M_AGING_OUT_CLIFF" in alert_codes
    assert "ZERO_VEHICLE_MOBILITY_SUPPORT" in alert_codes


def test_post_output_equity_and_nsch_grain_discipline() -> None:
    eq = run_post_output_equity_audit()
    assert eq["governance_attestation"]["audit_columns_excluded_from_routing"] is True
    assert len(eq["statewide_nsch_screening_context"]) == 6
    assert all(
        r["geographic_level"] == "Statewide" for r in eq["statewide_nsch_screening_context"]
    )
    assert len(eq["breach_vs_timely_neighborhood_equity"]) == 2

    outreach = prioritize_community_screening_tracts(top_n=4)
    assert len(outreach["priority_screening_tracts"]) == 4
    assert all(
        t["verified_downstream_45d_pathway"]["clears_45d_mandate"]
        for t in outreach["priority_screening_tracts"]
    )


def test_fastapi_workbench_and_leading_zero_states() -> None:
    client = TestClient(app)

    r_home = client.get("/")
    assert r_home.status_code == 200
    assert "First Milestones" in r_home.text

    r_ca = client.get("/api/brief?state=CA")
    assert r_ca.status_code == 200
    ca_data = r_ca.json()
    assert ca_data["state_code"] == "CA"
    # Verify leading-zero 11-character California FIPS ('06...')
    ca_tract = ca_data["routing"]["child_profile"]["home_tract_geoid"]
    assert len(ca_tract) == 11 and ca_tract.startswith("06")
    assert "Español" in r_home.text
    assert len(ca_data["caregiver_notes"]["spanish"]) > 80

    # Test all 3 track intents over /api/chat
    for prompt in (
        "Route a 32-month-old toddler in tract 28049003500 needing Spanish Autism screen on Medicaid",
        "Audit >45-day multi-hop bounce hubs in MS and simulate upgrading SYN-PROV-MS-011 from fax",
        "Which high-poverty zero-vehicle tracts should mobile developmental screening visit first?",
    ):
        r_chat = client.post("/api/chat", json={"message": prompt, "state_code": "MS"})
        assert r_chat.status_code == 200
        payload = r_chat.json()
        assert len(payload["reply"]) > 50
        assert len(payload["tools_invoked"]) >= 1
        assert payload["brief"]["network_audit"]["network_totals"]["statutory_breaches_over_45d"] == 26


def test_three_killer_gql_tools_and_property_graph_ddl() -> None:
    ddl_sql = (REPO_ROOT / "scripts" / "setup_graph.sql").read_text(encoding="utf-8")
    for required_symbol in (
        "v_graph_neighborhoods",
        "v_graph_refers_to_edges",
        "v_graph_serves_area_edges",
        "AS Neighborhood",
        "AS REFERS_TO",
        "AS SERVES_AREA",
    ):
        assert required_symbol in ddl_sql

    # Track 1: find_viable_45d_paths
    t1 = find_viable_45d_paths(
        zip_or_tract="28049003500",
        languages="Spanish",
        insurance="Medicaid",
        specialty="Speech",
        child_age_months=31,
        has_household_vehicle=False,
    )
    assert "GRAPH_TABLE" in t1["iso_gql_query"]
    assert "SERVES_AREA" in t1["iso_gql_query"]
    assert "REFERS_TO" in t1["iso_gql_query"]
    assert "audit_black_share" not in json.dumps(t1["tract_context"])
    assert all(p["total_expected_days"] <= 45 for p in t1["viable_paths"])

    # Track 2: detect_regional_bottleneck_hubs
    t2 = detect_regional_bottleneck_hubs(region="ALL", max_days=45, top_n=5)
    assert "GRAPH_TABLE" in t2["iso_gql_query"]
    assert "REFERS_TO" in t2["iso_gql_query"]
    assert t2["total_breached_multihop_chains"] == 26
    assert len(t2["bottleneck_hubs"]) >= 1
    assert t2["bottleneck_hubs"][0]["betweenness_flow_share_pct"] > 0

    # Track 3: rank_outreach_zones
    t3 = rank_outreach_zones(needs_medicaid=True, needs_bilingual=True, top_n=6)
    assert "GRAPH_TABLE" in t3["iso_gql_query"]
    assert "SERVES_AREA" in t3["iso_gql_query"]
    assert len(t3["ranked_outreach_zones"]) == 6
    assert t3["governance_attestation"]["audit_columns_excluded_from_scoring"] is True
