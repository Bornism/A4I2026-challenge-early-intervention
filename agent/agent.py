"""
Google ADK Agent for Early Intervention Triage & 45-Day Pathway Optimization.
Challenge 04: Agents for Impact 2026.
"""
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

# Ensure package root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from google.adk.agents import Agent
from agent.prompts.coordinator_prompt import SYSTEM_INSTRUCTION
from agent.tools.graph_service import (
    trace_referral_chain,
    find_compliant_pathway,
    get_equity_audit
)

def tool_trace_bounce_loop(case_chain_id: Optional[str] = "CHAIN-MS-009", state_code: str = "MS") -> Dict[str, Any]:
    """
    Traces multi-hop referral chains using variable-length path traversal to detect
    paper-fax bottlenecks and 3-hop bounce loops that breach the federal 45-day clock.
    """
    return trace_referral_chain(state_code=state_code, case_chain_id=case_chain_id)

def tool_find_compliant_pathway(
    child_age_months: int,
    home_tract_geoid: str,
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

def tool_run_equity_audit(home_tract_geoid: str, state_code: str = "MS") -> Dict[str, Any]:
    """
    Audits the child's home neighborhood demographics (poverty, zero-vehicle households, audit shares)
    against state averages to evaluate transport barriers and systemic disparities.
    """
    return get_equity_audit(home_tract_geoid=home_tract_geoid, state_code=state_code)

def create_coordinator_agent(model_name: Optional[str] = None) -> Agent:
    """
    Instantiates the Early Intervention ADK Triage Agent.
    """
    model = model_name or os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    
    agent = Agent(
        name="early_intervention_triage_coordinator",
        description="IDEA Part C Early Intervention Intake & Quality Coordinator Agent.",
        model=model,
        instruction=SYSTEM_INSTRUCTION,
        tools=[
            tool_trace_bounce_loop,
            tool_find_compliant_pathway,
            tool_run_equity_audit
        ]
    )
    return agent

if __name__ == "__main__":
    print("Initializing Early Intervention Triage Agent...")
    agent = create_coordinator_agent()
    print(f"Agent successfully created: {agent.name}")
    print(f"Registered tools: {[t.__name__ for t in agent.tools]}")
