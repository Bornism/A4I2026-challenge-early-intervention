"""
Model Context Protocol (MCP) Server for Early Intervention 45-Day Referral Graph.
Built with FastMCP to expose BigQuery / Property Graph triage tools over standard MCP protocol.
"""
import sys
from pathlib import Path
from typing import Any, Dict, Optional

# Add repo root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from fastmcp import FastMCP
from agent.tools.graph_service import (
    trace_referral_chain,
    find_compliant_pathway,
    get_equity_audit
)

# Initialize FastMCP Server
mcp = FastMCP(
    name="FirstMilestones-ReferralGraph-MCP",
    instructions="MCP Server for IDEA Part C Early Intervention 45-day statutory clock referral routing and bottleneck diagnosis."
)

@mcp.tool(
    name="trace_referral_bounce_loop",
    description="Traces variable-length (2..4 hop) referral chains to diagnose paper-fax bottlenecks and multi-hop bounce loops exceeding the 45-day federal IDEA Part C clock."
)
def mcp_trace_referral_bounce_loop(state_code: str = "MS", case_chain_id: Optional[str] = "CHAIN-MS-009") -> Dict[str, Any]:
    """
    Traces multi-hop referral chains and returns hop-by-hop breakdown, transmission channels,
    and cumulative wait days against the 45-day federal ceiling.
    """
    return trace_referral_chain(state_code=state_code, case_chain_id=case_chain_id)

@mcp.tool(
    name="find_compliant_45day_pathway",
    description="Discovers an optimal <=45-day compliant referral pathway for an incoming toddler matching age, Medicaid, and Spanish bilingual requirements."
)
def mcp_find_compliant_45day_pathway(
    child_age_months: int = 20,
    home_tract_geoid: str = "28011950701",
    requires_medicaid: bool = True,
    requires_bilingual: bool = True,
    max_days: int = 45,
    state_code: str = "MS"
) -> Dict[str, Any]:
    """
    Finds a compliant provider sequence: Clinic -> Electronic Coordinator Hub -> Bilingual Eval Hub -> Therapy Vendor.
    """
    return find_compliant_pathway(
        child_age_months=child_age_months,
        home_tract_geoid=home_tract_geoid,
        requires_medicaid=requires_medicaid,
        requires_bilingual=requires_bilingual,
        max_days=max_days,
        state_code=state_code
    )

@mcp.tool(
    name="run_equity_audit",
    description="Audits the child's home neighborhood demographics (poverty rate, zero-vehicle rate, racial/ethnic shares) against state averages to detect transport and systemic access barriers."
)
def mcp_run_equity_audit(home_tract_geoid: str = "28011950701", state_code: str = "MS") -> Dict[str, Any]:
    """
    Runs post-output equity audit joining tract GEOID to Census under-5 ACS demographics.
    """
    return get_equity_audit(home_tract_geoid=home_tract_geoid, state_code=state_code)

@mcp.resource("referral://standards/idea-part-c")
def get_idea_part_c_standards() -> str:
    """Returns statutory IDEA Part C 45-day timeline and equity compliance rules."""
    return """
    INDIVIDUALS WITH DISABILITIES EDUCATION ACT (IDEA) - PART C (34 CFR § 303.310)
    1. 45-Day Statutory Clock: From the date of referral, the lead agency has 45 calendar days
       to complete screening, multidisciplinary evaluation, child assessment, and hold the initial IFSP meeting.
    2. Language & Cultural Equity: Evaluations must be conducted in the child/family's native language.
    3. Medicaid & Financial Rights: Part C evaluations and service coordination are provided at no cost to families.
    """

if __name__ == "__main__":
    mcp.run()
