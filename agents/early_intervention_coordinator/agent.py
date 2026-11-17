"""
ADK Web Entrypoint Agent for Early Intervention Triage & 45-Day Pathway Optimization.
Equipped with Core Routing, Graph Traversal, Equity Audits, plus 3 Advanced Extensions:
1. Public Transit & Zero-Vehicle Feasibility (GTFS / Transit API Simulation)
2. Community Screening Site Locator (Public Head Start / WIC Sites Directory)
3. Concurrency-Safe Slot Reservation Service (Firestore / Transactional State Simulation)
"""
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

# Ensure virtualenv site-packages are first in sys.path
VENV_PACKAGES = "/config/Desktop/AgentsForImpact/.venv/lib/python3.14/site-packages"
if os.path.exists(VENV_PACKAGES) and VENV_PACKAGES not in sys.path:
    sys.path.insert(0, VENV_PACKAGES)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(1, str(REPO_ROOT))

from google.adk.agents import Agent
from agent.prompts.coordinator_prompt import SYSTEM_INSTRUCTION
from agent.tools.graph_service import (
    trace_referral_chain,
    find_compliant_pathway,
    get_equity_audit
)
from agent.subagents import tool_counterfactual_simulation
from agent.tools.advanced_extensions import (
    check_zero_vehicle_transit_feasibility,
    find_community_screening_sites,
    reserve_evaluation_slot
)

MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

# Tool 1: Graph Bounce Loop Diagnosis
def trace_referral_bounce_loop(case_chain_id: str = "CHAIN-MS-009", state_code: str = "MS") -> Dict[str, Any]:
    """
    Traces multi-hop referral chains over BigQuery referral logs to diagnose paper-fax bottlenecks
    and 3-hop bounce loops that breach the federal 45-day IDEA Part C clock.
    """
    return trace_referral_chain(state_code=state_code, case_chain_id=case_chain_id)

# Tool 2: 45-Day Route Finder
def find_compliant_45day_pathway(
    child_age_months: int = 20,
    home_tract_geoid: str = "28011950701",
    requires_medicaid: bool = True,
    requires_bilingual: bool = True,
    state_code: str = "MS"
) -> Dict[str, Any]:
    """
    Finds a verified <=45-day compliant pathway connecting an origin clinic, electronic coordinator hub,
    multidisciplinary evaluation hub, and therapy vendor matching Medicaid and bilingual requirements.
    """
    return find_compliant_pathway(
        child_age_months=child_age_months,
        home_tract_geoid=home_tract_geoid,
        requires_medicaid=requires_medicaid,
        requires_bilingual=requires_bilingual,
        state_code=state_code
    )

# Tool 3: Demographics & Poverty Equity Audit
def run_equity_audit(home_tract_geoid: str = "28011950701", state_code: str = "MS") -> Dict[str, Any]:
    """
    Audits the child's home neighborhood demographics (poverty, zero-vehicle households) against state
    averages to evaluate transport barriers and ensure equitable access.
    """
    return get_equity_audit(home_tract_geoid=home_tract_geoid, state_code=state_code)

# Tool 4: Counterfactual Hub Upgrade Simulation
def run_counterfactual_simulation(hub_id: str = "SYN-PROV-MS-009", state_code: str = "MS") -> Dict[str, Any]:
    """
    Simulates the regional impact of upgrading a paper-fax coordinator hub to an electronic portal,
    calculating total child-days saved across all breached referral chains.
    """
    return tool_counterfactual_simulation(state_code=state_code, hub_id=hub_id)

# Tool 5: Transit & GTFS Feasibility (Extension 1)
def check_transit_accessibility(origin_tract_geoid: str = "28011950701", target_hub_id: str = "SYN-PROV-MS-019") -> Dict[str, Any]:
    """
    Determines if a zero-vehicle caregiver can reach an evaluation hub by public bus using transit GTFS
    and distance routing, or whether Medicaid Non-Emergency Medical Transportation (NEMT) is required.
    """
    return check_zero_vehicle_transit_feasibility(origin_tract_geoid=origin_tract_geoid, target_hub_id=target_hub_id)

# Tool 6: Head Start & WIC Screening Sites (Extension 2)
def find_head_start_and_wic_screening_sites(target_county: str = "Bolivar County", require_bilingual: bool = True) -> Dict[str, Any]:
    """
    Locates licensed federal Head Start and state WIC public clinics for community developmental screening days
    where zero-vehicle and high-poverty families regularly attend.
    """
    return find_community_screening_sites(target_county=target_county, require_bilingual=require_bilingual)

# Tool 7: Real-Time Transactional Slot Lock (Extension 3)
def reserve_live_evaluation_slot(
    case_chain_id: str = "CHAIN-MS-009",
    provider_id: str = "SYN-PROV-MS-019",
    child_age_months: int = 20,
    coordinator_id: str = "COORD-CLARKSDALE-01"
) -> Dict[str, Any]:
    """
    Atomically locks and reserves a live multidisciplinary evaluation slot at an evaluation hub, preventing
    concurrent coordinators from double-booking capacity (Firestore / Cloud SQL transactional state model).
    """
    return reserve_evaluation_slot(
        case_chain_id=case_chain_id,
        provider_id=provider_id,
        child_age_months=child_age_months,
        coordinator_id=coordinator_id
    )

# The root agent exposed to ADK Web
root_agent = Agent(
    name="early_intervention_coordinator",
    description="IDEA Part C Early Intervention Intake & Quality Coordinator Agent.",
    model=MODEL,
    instruction=SYSTEM_INSTRUCTION + """

### Advanced Capabilities (Extensions)
- When a family lacks a vehicle, use `check_transit_accessibility` to evaluate bus routes or arrange Medicaid NEMT transport.
- For community screening events, use `find_head_start_and_wic_screening_sites` to identify licensed WIC/Head Start locations.
- To prevent coordinator double-booking, use `reserve_live_evaluation_slot` to secure a confirmed appointment with an ACID lock.
""",
    tools=[
        trace_referral_bounce_loop,
        find_compliant_45day_pathway,
        run_equity_audit,
        run_counterfactual_simulation,
        check_transit_accessibility,
        find_head_start_and_wic_screening_sites,
        reserve_live_evaluation_slot
    ]
)
