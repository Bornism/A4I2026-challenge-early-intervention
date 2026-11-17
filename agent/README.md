# First Milestones — Python ADK Agent, Managed MCP & Coordinator Workbench

Built for **Agents for Impact 2026 · Challenge 04: Early Intervention & Developmental Screening Triage**.

## Architecture Summary

- **Python ADK Agent (`first_milestones/agent.py`):** Root `LlmAgent` (`first_milestones_coordinator`) powered by **Gemini 2.5 Pro** (`A4I_GEMINI_MODEL=gemini-2.5-pro`) with statutory 45-day IDEA Part C (`34 CFR § 303.310`), 36-month aging-out cliff, zero-vehicle NEMT, and `100% [Synthetic]` stage-safety guardrails.
- **BigQuery Property Graph Differentiator (`first_milestones/tools/`):**
  - `find_compliant_45d_pathways` (`graph_routing.py`): Prospective `<=45`-day multi-hop pathway routing (`Clinic -> Coordinator -> Eval Hub -> Therapy Vendor`) combining `GRAPH_TABLE` ISO GQL with native `ST_DISTANCE` spatial proximity, Medicaid/Part C/bilingual hard filters, 36-month aging-out cliff checks, and zero-vehicle mobility guardrails (strictly excluding `audit_*` and all-zero `limited_english_rate`).
  - `audit_multihop_bounce_hubs` & `simulate_hub_intervention` (`graph_audit.py`): Variable-length `-{2,4}->` ISO GQL traversal correlated on `case_chain_id` and prefix-deduplicated (preventing Type B `Vendor -> Vendor` 3-hop prefix double-counting), plus counterfactual `paper_fax` -> `ehr_electronic_portal` child-days-saved simulation.
  - `run_post_output_equity_audit` & `prioritize_community_screening_tracts` (`equity_audit.py`): Post-output join to ACS `audit_*` demographic shares, zero-vehicle mobility disparity analysis, and statewide-only HRSA NSCH screening context (`6` statewide strata, zero 6x tract fan-out).
- **Google-Managed MCP Integration (`tools.yaml` + `mcp_integration.py`):**
  - Connects automatically to **Google MCP Toolbox for Databases** (`googleapis/mcp-toolbox` via ADK `ToolboxToolset` using `agent/tools.yaml`) inside Cloud Run, or to **BigQuery's Built-in Remote Managed MCP Server** (`https://bigquery.googleapis.com/mcp` via ADK `McpToolset` + Google ADC headers).
- **Split-Pane Coordinator Workbench UI (`main.py` + `static/`):**
  - Designed for internal state/regional IDEA Part C Intake & Quality Coordinators: live ADK chat + preset scenarios on the left, paired with a visual Multi-Hop Path Comparator (4-hop red `paper_fax` bounce vs. `<=45`-day green electronic pathway), 45-day clock meter, counterfactual simulator, Post-Output Equity Audit, and toggleable **English / Español** Caregiver Action Notes on the right.

---

## Quick Start

### 1. Deploy Everything to Google Cloud Run (Recommended in Cloud Shell)
From the **repository root** in Google Cloud Shell:

```bash
bash scripts/deploy_cloud_run.sh MS     # or CA, AL, GA, TX, NY
```

This single script:
1. Enables required GCP APIs + BigQuery MCP,
2. Runs `scripts/setup_graph.sh` to provision the zero-baseline `a4i-graph` Enterprise reservation, load all five tables into `a4i_early_intervention`, and create `a4i_early_intervention.ReferralGraph`,
3. Grants `bigquery.dataViewer`, `bigquery.jobUser`, and `aiplatform.user` to the Cloud Run service account, and
4. Deploys the unified ADK + MCP Toolbox + Split-Pane UI container to Cloud Run with `--min-instances=1` (zero cold starts during your recorded demo).

### 2. Run Locally (or in Cloud Shell Preview)

**Split-Pane Coordinator Workbench (`http://localhost:8080`):**
```bash
pip install -r agent/requirements.txt
python agent/main.py
```

**Built-in ADK Developer Web UI (`adk web`):**
```bash
adk web agent
```

### 3. (Alternative) Deploy to Vertex AI Agent Engine
```bash
adk deploy agent_engine --project="$GOOGLE_CLOUD_PROJECT" --region=us-central1 ./agent/first_milestones
```
