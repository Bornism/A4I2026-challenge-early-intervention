"""Root Python ADK Agent definition for First Milestones (`first_milestones`).

Compatible with:
  - `adk web agent` (local & Cloud Shell developer UI)
  - `agent/main.py` (Unified Cloud Run FastAPI + Split-Pane Coordinator Workbench UI)
  - `adk deploy agent_engine` (Vertex AI Agent Engine)
"""

from __future__ import annotations

import os

from google.adk.agents import LlmAgent

from .brief_builder import generate_complete_45d_brief
from .mcp_integration import load_managed_mcp_tools
from .prompts import SYSTEM_INSTRUCTION
from .tools import (
    audit_multihop_bounce_hubs,
    detect_regional_bottleneck_hubs,
    find_compliant_45d_pathways,
    find_viable_45d_paths,
    prioritize_community_screening_tracts,
    rank_outreach_zones,
    run_post_output_equity_audit,
    simulate_hub_intervention,
)

DEFAULT_MODEL = os.environ.get("A4I_GEMINI_MODEL", "gemini-2.5-pro")

managed_mcp_tools, ACTIVE_MCP_MODE = load_managed_mcp_tools()

root_agent = LlmAgent(
    name="first_milestones_coordinator",
    model=DEFAULT_MODEL,
    description=(
        "IDEA Part C Early Intervention Triage & Multi-Hop Referral Network Audit "
        "Assistant powered by BigQuery Property Graphs (ISO GQL), Google-managed MCP, "
        "and Gemini."
    ),
    instruction=SYSTEM_INSTRUCTION,
    tools=[
        find_compliant_45d_pathways,
        find_viable_45d_paths,
        audit_multihop_bounce_hubs,
        detect_regional_bottleneck_hubs,
        simulate_hub_intervention,
        run_post_output_equity_audit,
        prioritize_community_screening_tracts,
        rank_outreach_zones,
        generate_complete_45d_brief,
        *managed_mcp_tools,
    ],
)
