"""FastAPI + Google ADK Unified Server for First Milestones Coordinator Workbench.

Serves:
  - `/` & `/static/*`: Custom Split-Pane Web UI ("45-Day Pathway & Bottleneck Brief")
  - `GET  /api/health`: Runtime & MCP status check
  - `GET  /api/brief`: Complete initial or state-switched 45-Day Pathway & Bottleneck Brief
  - `POST /api/simulate`: Interactive counterfactual Bounce Hub simulator endpoint
  - `POST /api/chat`: Multi-turn conversational ADK Runner endpoint (`gemini-2.5-pro`)
    that captures live MCP + ISO GQL tool invocations and returns updated visual
    brief state alongside the coordinator's response. Also includes an automatic
    deterministic fallback synthesis if Gemini/Vertex credentials are not yet set
    in a local offline preview environment.
"""

from __future__ import annotations

import logging
import os
import re
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from pydantic import BaseModel, Field

from first_milestones.agent import ACTIVE_MCP_MODE, DEFAULT_MODEL, root_agent
from first_milestones.brief_builder import build_caregiver_notes, generate_complete_45d_brief
from first_milestones.tools.bq_client import VALID_STATES, get_config, load_local_state_frames
from first_milestones.tools.equity_audit import (
    prioritize_community_screening_tracts,
    run_post_output_equity_audit,
)
from first_milestones.tools.graph_audit import (
    audit_multihop_bounce_hubs,
    simulate_hub_intervention,
)
from first_milestones.tools.graph_routing import find_compliant_45d_pathways

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("first_milestones.server")

APP_NAME = "first_milestones"
STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(
    title="First Milestones — IDEA Part C Early Intervention Triage & Audit",
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

session_service = InMemorySessionService()
runner = Runner(
    app_name=APP_NAME,
    agent=root_agent,
    session_service=session_service,
)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    session_id: str | None = None
    state_code: str | None = None


class SimulateRequest(BaseModel):
    state_code: str | None = None
    target_provider_id: str = ""
    upgrade_fax_to_ehr: bool = True
    precheck_bilingual_and_slot_capacity: bool = True


def _apply_state_override(state_code: str | None) -> str:
    if state_code:
        cleaned = state_code.strip().upper()
        if cleaned in VALID_STATES:
            os.environ["A4I_STATE"] = cleaned
    return get_config()["state"]


def _has_llm_credentials() -> bool:
    """Checks whether Gemini API or Vertex AI ADC credentials are configured."""
    if os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY"):
        return True
    if os.environ.get("GOOGLE_GENAI_USE_VERTEXAI", "").strip().upper() in ("1", "TRUE", "YES"):
        if os.environ.get("GOOGLE_CLOUD_PROJECT"):
            return True
    return False


def _default_anchor_tract(state_code: str) -> str:
    """Picks the tract of the 32-month-old 4-hop autism case (CHAIN-*-023) as default demo anchor."""
    logs = load_local_state_frames(state_code)["logs"]
    c23 = logs[logs["case_chain_id"] == f"CHAIN-{state_code}-023"]
    if not c23.empty:
        return str(c23.iloc[0]["child_home_tract_geoid"])
    return ""


def _parse_intent_and_fallback_reply(msg: str, state_code: str) -> tuple[str, list[str], dict[str, Any]]:
    """Executes real ISO GQL / Equity tools and formats a fallback reply when offline."""
    lower = msg.lower()
    tract_match = re.search(r"\b(\d{11})\b", msg)
    tract = tract_match.group(1) if tract_match else _default_anchor_tract(state_code)

    age_match = re.search(r"\b(\d{1,2})\s*(?:-|\s)?(?:month|mo\b|m\b)", lower)
    age_m = int(age_match.group(1)) if age_match else 32

    if "autism" in lower or "social" in lower:
        domain = "Social-Communication / Autism Screen"
    elif "motor" in lower:
        domain = "Motor Milestone Delay"
    elif "feed" in lower or "sensory" in lower:
        domain = "Feeding & Sensory"
    else:
        domain = "Expressive Speech/Language"

    needs_bilingual = not ("english only" in lower or "non-bilingual" in lower)
    needs_medicaid = "private insurance" not in lower
    has_vehicle = "has vehicle" in lower or "with vehicle" in lower

    prov_match = re.search(r"(SYN-PROV-[A-Z]{2}-\d{3})", msg, re.IGNORECASE)
    target_hub = prov_match.group(1).upper() if prov_match else ""

    brief = generate_complete_45d_brief(
        child_tract_geoid=tract,
        child_age_months=age_m,
        concern_domain=domain,
        needs_medicaid=needs_medicaid,
        needs_bilingual=needs_bilingual,
        has_household_vehicle=has_vehicle,
    )
    if target_hub:
        brief["counterfactual_simulation"] = simulate_hub_intervention(
            target_provider_id=target_hub,
            upgrade_fax_to_ehr=True,
            precheck_bilingual_and_slot_capacity=True,
        )

    rec = brief["routing"]["recommended_pathway"]
    bounce = brief["routing"]["cautionary_historical_bounce_chain"]
    top_hub = brief["network_audit"]["top_hidden_bounce_hub"]
    sim = brief["counterfactual_simulation"]["impact_summary"]
    outreach_top = brief["screening_outreach"]["priority_screening_tracts"][0]

    if "screen" in lower or "outreach" in lower or "mobile" in lower:
        tools_used = [
            "prioritize_community_screening_tracts",
            "find_compliant_45d_pathways",
            "run_post_output_equity_audit",
        ]
        reply = (
            f"### Community Developmental Screening Readiness ({state_code})\n\n"
            f"- **Top Priority Neighborhood:** Tract `{outreach_top['census_tract_geoid']}` ({outreach_top['county_name']}) — "
            f"**{outreach_top['children_under_5_count']}** children under 5, **{outreach_top['poverty_pct']}%** poverty, "
            f"**{outreach_top['zero_vehicle_pct']}%** zero-vehicle households.\n"
            f"- **Verified <=45-Day Downstream Capacity:** Paired with `{outreach_top['verified_downstream_45d_pathway']['eval_hub_id']}` "
            f"(~**{outreach_top['verified_downstream_45d_pathway']['expected_cumulative_days']} days** cumulative to initial IFSP).\n"
            f"- **Data Rigor Guardrails:** Ranked without `audit_*` racial shares and without the all-zero ACS `limited_english_rate` (`0.0`) column.\n\n"
            f"*(Right-hand brief updated with full screening readiness, multi-hop graph comparison, and Post-Output Equity Audit.)*"
        )
    elif "audit" in lower or "bounce" in lower or "bottleneck" in lower or "simulat" in lower or "fax" in lower:
        tools_used = [
            "audit_multihop_bounce_hubs",
            "simulate_hub_intervention",
            "run_post_output_equity_audit",
            "mcp_get_regional_agency_performance",
        ]
        reply = (
            f"### Multi-Hop Network Bottleneck Audit & Counterfactual Fix ({state_code})\n\n"
            f"- **Why Flat SQL Misleads:** Sorting by `active_waitlist_count` points at saturated downstream clinics, while **`{top_hub['provider_id']}`** "
            f"({top_hub['synthetic_organization_name']}) looks healthy in a flat table (**{top_hub['flat_median_internal_wait_days']}d** internal wait) "
            f"yet triggers **{top_hub['breached_over_45d']} of {top_hub['routed_episodes']}** `>45`-day statutory breaches (**{top_hub['total_excess_days_over_45']}** excess days) via `paper_fax` and unverified slot handoffs.\n"
            f"- **Counterfactual Single-Hub Fix (`{brief['counterfactual_simulation']['target_intervention_scope']}`):** Upgrading `paper_fax` to `ehr_electronic_portal` + pre-checking bilingual/Medicaid slot capacity reduces breaches from **{sim['baseline_breaches_over_45d']} → {sim['simulated_breaches_over_45d']}** and saves **{sim['total_delayed_child_days_saved']} delayed child-days**.\n"
            f"- **Provenance & Equity:** All `SYN-PROV-*` / `SYN-PARTC-*` rows are `100% [Synthetic]`; see the Post-Output Equity Audit panel on the right."
        )
    else:
        tools_used = [
            "find_compliant_45d_pathways",
            "audit_multihop_bounce_hubs",
            "run_post_output_equity_audit",
        ]
        hops_str = " → ".join(
            [rec["hops"][0]["source_provider_id"]] + [h["target_provider_id"] for h in rec["hops"]]
        )
        reply = (
            f"### <=45-Day Compliant Pathway vs. Historical Bounce Diagnosis ({state_code})\n\n"
            f"- **Recommended Electronic Route ({rec['expected_cumulative_days']} Days — Clears 45-Day Mandate by {rec['statutory_45d_headroom_days']}d):**\n"
            f"  `{hops_str}` via `ehr_electronic_portal` (100% Medicaid-enrolled, Part C vendor-verified, Spanish-bilingual).\n"
            f"- **Avoided Bounce Loop (`{bounce['case_chain_id']}` — {bounce['total_wait_days']} Days ❌):** Bypassed the 4-hop `paper_fax` re-referral loop (**{brief['routing']['days_saved_vs_bounce_loop']} days faster**).\n"
            + (
                f"- **36-Month Aging-Out Alert:** At **{age_m} months**, avoiding a {bounce['total_wait_days']}-day delay protects the toddler before the 36-month IDEA Part C cutoff; initiate concurrent Part B transition notice.\n"
                if age_m >= 30
                else ""
            )
            + f"- **Mobility & Caregiver Note:** Medicaid NEMT / mobile evaluation flagged for tract `{tract}` (**{brief['routing']['child_profile']['tract_zero_vehicle_pct']}%** zero-vehicle rate). English & Spanish caregiver notes are ready in the right panel."
        )

    return reply, tools_used, brief


@app.get("/api/health")
async def health() -> dict[str, Any]:
    cfg = get_config()
    return {
        "status": "ok",
        "agent": root_agent.name,
        "gemini_model": DEFAULT_MODEL,
        "llm_credentials_active": _has_llm_credentials(),
        "mcp_mode": ACTIVE_MCP_MODE,
        "state_code": cfg["state"],
        "state_name": cfg["state_name"],
        "dataset": cfg["dataset"],
        "project": cfg["project"] or "(local GeoParquet preview)",
    }


@app.get("/api/brief")
async def get_brief(
    state: str = Query(default="", description="Two-letter starter state (MS, AL, GA, TX, CA, NY)"),
    tract_geoid: str = Query(default="", description="Optional 11-char census_tract_geoid"),
    age_months: int = Query(default=32, ge=0, le=35),
    concern_domain: str = Query(default="Social-Communication / Autism Screen"),
    needs_medicaid: bool = Query(default=True),
    needs_bilingual: bool = Query(default=True),
    has_vehicle: bool = Query(default=False),
) -> dict[str, Any]:
    active_state = _apply_state_override(state)
    resolved_tract = tract_geoid.strip() or _default_anchor_tract(active_state)
    brief = generate_complete_45d_brief(
        child_tract_geoid=resolved_tract,
        child_age_months=age_months,
        concern_domain=concern_domain,
        needs_medicaid=needs_medicaid,
        needs_bilingual=needs_bilingual,
        has_household_vehicle=has_vehicle,
    )
    brief["runtime"] = await health()
    return brief


@app.post("/api/simulate")
async def run_simulation(req: SimulateRequest) -> dict[str, Any]:
    _apply_state_override(req.state_code)
    return simulate_hub_intervention(
        target_provider_id=req.target_provider_id,
        upgrade_fax_to_ehr=req.upgrade_fax_to_ehr,
        precheck_bilingual_and_slot_capacity=req.precheck_bilingual_and_slot_capacity,
    )


@app.post("/api/chat")
async def chat_endpoint(req: ChatRequest) -> dict[str, Any]:
    active_state = _apply_state_override(req.state_code)
    session_id = req.session_id or f"coord-{uuid.uuid4().hex[:10]}"
    user_id = "part_c_coordinator"

    # If running in Google Cloud / with Gemini credentials, run full ADK LlmAgent loop
    if _has_llm_credentials():
        try:
            existing = await session_service.get_session(
                app_name=APP_NAME, user_id=user_id, session_id=session_id
            )
            if existing is None:
                await session_service.create_session(
                    app_name=APP_NAME, user_id=user_id, session_id=session_id
                )

            user_content = types.Content(
                role="user",
                parts=[
                    types.Part.from_text(
                        text=f"[Active State: {active_state}] {req.message}"
                    )
                ],
            )

            tool_calls_seen: list[str] = []
            captured_outputs: dict[str, Any] = {}
            final_chunks: list[str] = []

            async for event in runner.run_async(
                user_id=user_id,
                session_id=session_id,
                new_message=user_content,
            ):
                for fc in event.get_function_calls() or []:
                    if fc.name and fc.name not in tool_calls_seen:
                        tool_calls_seen.append(fc.name)
                for fr in event.get_function_responses() or []:
                    if fr.name and isinstance(fr.response, dict):
                        captured_outputs[fr.name] = fr.response
                if event.is_final_response() and event.content and event.content.parts:
                    for part in event.content.parts:
                        if getattr(part, "text", None):
                            final_chunks.append(part.text)

            # Hydrate complete right-pane brief, merging any specific tool outputs returned in turn
            if "generate_complete_45d_brief" in captured_outputs:
                brief = captured_outputs["generate_complete_45d_brief"]
            else:
                _, _, brief = _parse_intent_and_fallback_reply(req.message, active_state)
                if "find_compliant_45d_pathways" in captured_outputs:
                    brief["routing"] = captured_outputs["find_compliant_45d_pathways"]
                    brief["caregiver_notes"] = build_caregiver_notes(brief["routing"])
                if "audit_multihop_bounce_hubs" in captured_outputs:
                    brief["network_audit"] = captured_outputs["audit_multihop_bounce_hubs"]
                if "simulate_hub_intervention" in captured_outputs:
                    brief["counterfactual_simulation"] = captured_outputs["simulate_hub_intervention"]
                if "run_post_output_equity_audit" in captured_outputs:
                    brief["equity_audit"] = captured_outputs["run_post_output_equity_audit"]
                if "prioritize_community_screening_tracts" in captured_outputs:
                    brief["screening_outreach"] = captured_outputs[
                        "prioritize_community_screening_tracts"
                    ]

            reply_text = "\n".join(final_chunks).strip()
            if reply_text:
                return {
                    "session_id": session_id,
                    "mode": f"adk_gemini_live ({DEFAULT_MODEL})",
                    "tools_invoked": tool_calls_seen,
                    "reply": reply_text,
                    "brief": brief,
                }
        except Exception as exc:  # noqa: BLE001
            logger.warning("ADK live Gemini call encountered error (%s); using graph fallback.", exc)

    # Local offline preview fallback (executes real graph/equity tools deterministically)
    reply_text, tools_used, brief = _parse_intent_and_fallback_reply(req.message, active_state)
    return {
        "session_id": session_id,
        "mode": "local_graph_engine_preview (set GOOGLE_GENAI_USE_VERTEXAI=TRUE or GOOGLE_API_KEY for live Gemini)",
        "tools_invoked": tools_used,
        "reply": reply_text,
        "brief": brief,
    }


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
async def serve_index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", "8080"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
