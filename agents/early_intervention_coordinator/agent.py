"""
ADK Web Entrypoint Agent for Early Intervention Triage & 45-Day Pathway Optimization.
Loaded automatically by `adk web`.
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

MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

def trace_referral_bounce_loop(case_chain_id: str = "CHAIN-MS-009", state_code: str = "MS") -> Dict[str, Any]:
    """
    Traces multi-hop referral chains over BigQuery referral logs to diagnose paper-fax bottlenecks
    and 3-hop bounce loops that breach the federal 45-day IDEA Part C clock.
    """
    return trace_referral_chain(state_code=state_code, case_chain_id=case_chain_id)

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

def run_equity_audit(home_tract_geoid: str = "28011950701", state_code: str = "MS") -> Dict[str, Any]:
    """
    Audits the child's home neighborhood demographics (poverty, zero-vehicle households) against state
    averages to evaluate transport barriers and ensure equitable access.
    """
    return get_equity_audit(home_tract_geoid=home_tract_geoid, state_code=state_code)

def run_counterfactual_simulation(hub_id: str = "SYN-PROV-MS-009", state_code: str = "MS") -> Dict[str, Any]:
    """
    Simulates the regional impact of upgrading a paper-fax coordinator hub to an electronic portal,
    calculating total child-days saved across all breached referral chains.
    """
    return tool_counterfactual_simulation(state_code=state_code, hub_id=hub_id)

# The root agent exposed to ADK Web
root_agent = Agent(
    name="early_intervention_coordinator",
    description="IDEA Part C Early Intervention Intake & Quality Coordinator Agent.",
    model=MODEL,
    instruction=SYSTEM_INSTRUCTION,
    tools=[
        trace_referral_bounce_loop,
        find_compliant_45day_pathway,
        run_equity_audit,
        run_counterfactual_simulation
    ]
)
