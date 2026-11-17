"""Google-managed MCP server integration for First Milestones ADK Agent.

Supports two sanctioned Google-managed MCP backends out of the box:
  1. Google MCP Toolbox for Databases (`googleapis/mcp-toolbox` running via
     `tools.yaml` on `TOOLBOX_URL`, default `http://127.0.0.1:5000`), consumed
     through ADK's built-in `ToolboxToolset`.
  2. Google BigQuery Built-in Remote MCP Server (`https://bigquery.googleapis.com/mcp`),
     consumed through ADK's `McpToolset` + `StreamableHTTPConnectionParams` with
     automatic Google Application Default Credentials (ADC) token refresh.

When running locally without a live Toolbox process or GCP credentials (e.g.,
offline laptop preview), returns local parity reference tools backed by the
starter GeoParquet files so `adk web` and unit tests never crash on startup.
"""

from __future__ import annotations

import logging
import os
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)

BIGQUERY_MCP_URL = "https://bigquery.googleapis.com/mcp"


def _is_toolbox_reachable(url: str, timeout: float = 1.2) -> bool:
    """Checks whether the MCP Toolbox HTTP server is listening."""
    try:
        req = urllib.request.Request(url.rstrip("/") + "/api/toolset", method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return 200 <= resp.status < 500
    except Exception:  # noqa: BLE001
        return False


def _get_adc_headers(_context: Any = None) -> dict[str, str]:
    """Supplies refreshed OAuth2 bearer headers for BigQuery's remote MCP server."""
    import google.auth
    import google.auth.transport.requests

    credentials, project_id = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    auth_req = google.auth.transport.requests.Request()
    credentials.refresh(auth_req)
    resolved_project = os.environ.get("GOOGLE_CLOUD_PROJECT") or project_id or ""
    headers = {
        "Authorization": f"Bearer {credentials.token}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    if resolved_project:
        headers["x-goog-user-project"] = resolved_project
    return headers


def load_managed_mcp_tools() -> tuple[list[Any], str]:
    """Returns `(tools_list, mcp_mode_label)` for the root ADK agent.

    Controlled by `A4I_MCP_MODE`:
      - `auto` (default): Prefer local/sidecar MCP Toolbox if reachable, else
        BigQuery remote managed MCP server if GCP ADC credentials are active,
        else offline local parity fallback tools.
      - `toolbox`: Force `ToolboxToolset` against `TOOLBOX_URL`.
      - `bigquery_mcp`: Force remote `https://bigquery.googleapis.com/mcp`.
      - `fallback`: Use local GeoParquet parity reference tools.
    """
    mode = os.environ.get("A4I_MCP_MODE", "auto").strip().lower()
    toolbox_url = os.environ.get("TOOLBOX_URL", "http://127.0.0.1:5000").strip()

    # 1. MCP Toolbox for Databases (Google-managed binary configured via tools.yaml)
    if mode in ("auto", "toolbox"):
        if mode == "toolbox" or _is_toolbox_reachable(toolbox_url):
            try:
                from google.adk.tools.toolbox_toolset import ToolboxToolset

                toolset = ToolboxToolset(
                    server_url=toolbox_url,
                    toolset_name="first_milestones_bq",
                )
                logger.info("Connected to Google MCP Toolbox for Databases at %s", toolbox_url)
                return [toolset], f"mcp_toolbox ({toolbox_url})"
            except Exception as exc:  # noqa: BLE001
                logger.warning("MCP Toolbox initialization skipped (%s)", exc)
                if mode == "toolbox":
                    raise

    # 2. BigQuery Built-in Remote Managed MCP Server (bigquery.googleapis.com/mcp)
    if mode in ("auto", "bigquery_mcp") and os.environ.get("A4I_FORCE_LOCAL_PARQUET") != "1":
        try:
            initial_headers = _get_adc_headers()
            if initial_headers.get("x-goog-user-project"):
                from google.adk.tools.mcp_tool.mcp_session_manager import (
                    StreamableHTTPConnectionParams,
                )
                from google.adk.tools.mcp_tool.mcp_toolset import McpToolset

                bq_mcp = McpToolset(
                    connection_params=StreamableHTTPConnectionParams(
                        url=BIGQUERY_MCP_URL,
                        headers=initial_headers,
                    ),
                    tool_filter=[
                        "list_dataset_ids",
                        "get_dataset_info",
                        "list_table_ids",
                        "get_table_info",
                        "execute_sql",
                    ],
                    header_provider=_get_adc_headers,
                )
                logger.info(
                    "Connected to Google-managed BigQuery Remote MCP Server (%s)",
                    BIGQUERY_MCP_URL,
                )
                return [bq_mcp], "google_bigquery_remote_mcp (bigquery.googleapis.com/mcp)"
        except Exception as exc:  # noqa: BLE001
            logger.info("Remote BigQuery MCP not active locally (%s); using parity lookup tools.", exc)
            if mode == "bigquery_mcp":
                raise

    # 3. Local parity fallback tools (when previewing without GCP credentials)
    from .tools.reference_lookups import (
        lookup_carenode_directory,
        lookup_regional_agency_kpis,
        lookup_statewide_nsch_strata,
        lookup_tract_routing_context,
    )

    return [
        lookup_regional_agency_kpis,
        lookup_statewide_nsch_strata,
        lookup_tract_routing_context,
        lookup_carenode_directory,
    ], "local_parquet_parity_tools (configure GOOGLE_CLOUD_PROJECT or start toolbox for live MCP)"
