"""
Test script to verify FastMCP Server functionality via direct in-process calls.
"""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from agent.mcp.server import (
    mcp,
    mcp_trace_referral_bounce_loop,
    mcp_find_compliant_45day_pathway,
    mcp_run_equity_audit
)

def test_mcp_tools():
    print("="*70)
    print("  TESTING FAST_MCP TOOLS IN agent/mcp")
    print("="*70)
    
    trace = mcp_trace_referral_bounce_loop(state_code="MS", case_chain_id="CHAIN-MS-009")
    print("\n[MCP Tool 1: trace_referral_bounce_loop]")
    print(f"Status: Success | Chain: {trace['chains'][0]['case_chain_id']} | Wait Days: {trace['chains'][0]['cumulative_wait_days']}")
    
    pathway = mcp_find_compliant_45day_pathway(
        child_age_months=20,
        home_tract_geoid="28011950701",
        requires_medicaid=True,
        requires_bilingual=True,
        state_code="MS"
    )
    print("\n[MCP Tool 2: find_compliant_45day_pathway]")
    print(f"Status: Success | Cumulative Days: {pathway['cumulative_wait_days']} | Compliant: {pathway['is_compliant']}")
    
    equity = mcp_run_equity_audit(home_tract_geoid="28011950701", state_code="MS")
    print("\n[MCP Tool 3: run_equity_audit]")
    print(f"Status: Success | County: {equity['county_name']} | Poverty Rate: {equity['neighborhood_poverty_rate_pct']}%")
    
    print("\n" + "="*70)
    print("✓ All FastMCP tools verified in agent/mcp successfully!")
    print("="*70)

if __name__ == "__main__":
    test_mcp_tools()
