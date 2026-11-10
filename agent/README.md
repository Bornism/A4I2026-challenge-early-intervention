# Your agent goes here

This folder is empty on purpose.

We built the on-ramp: real American Community Survey under-five neighborhood demographics, statewide HRSA NSCH developmental screening strata, synthetic IDEA Part C lead agencies calibrated to federal OSEP benchmarks, a 100% synthetic `CareNode` provider network and multi-hop `ReferralHandoff` log, an automatic zero-baseline Enterprise reservation setup, and a validation suite that checks graph key integrity before you start. We did not build the vehicle. The design decisions in your agent are what you will be judged on.

## What has to be true of what you build here

- **An ADK agent**, in Python.
- **At least one tool you built yourself.** A Python function tool or one you defined in MCP Toolbox both count. The obvious candidate wraps your multi-hop `GRAPH ... MATCH` query, while the more valuable one holds the triage and routing logic: matching a child's home tract, Medicaid coverage, and primary home language to a provider path that clears the 45-day IDEA Part C statutory clock, or isolating systemic re-referral bounce hubs. Consuming only prebuilt generic tools and calling that your design does not count.
- **At least one Google-managed MCP server, consumed.** Do not author your own from scratch. Use BigQuery's built-in MCP server or the [MCP Toolbox for Databases](https://github.com/googleapis/mcp-toolbox).
- **Deployed to Google Cloud**, on Agent Runtime or Cloud Run (your choice).
- **Your required differentiator: BigQuery Property Graphs.** Your agent must execute genuine variable-length ISO GQL graph traversals (`CREATE OR REPLACE PROPERTY GRAPH` + `-{2,4}->` `MATCH` patterns). A single-hop query or a flat SQL `JOIN` with the word "graph" in a function name does not count, and it is the most common way a team misses the point while appearing to hit it.

## The thing worth remembering while you build

**A graph makes a hidden bottleneck visible. It does not make the policy or routing decision.**

Sorting providers by `active_waitlist_count` points at busy downstream evaluation clinics, which are symptoms at hop 2 and hop 3. Traversing `case_chain_id` paths across `-{2,4}->` hops exposes intake coordinators whose internal wait is only five days (`median_internal_wait_days = 5`), yet whose `paper_fax` handoffs into non-bilingual or non-Medicaid hubs trigger 70-day multi-hop breaches of federal law. What you do *after* the traversal (recommending an eligible <=45-day route for today's toddler, quantifying which regional hub fix saves the most child-days, and stating plainly that provider and referral rows are 100% synthetic) is where this agent becomes useful instead of merely clever.

See Section 13 of [`notebooks/c_ei_01_load_explore.ipynb`](../notebooks/c_ei_01_load_explore.ipynb) for the `CREATE PROPERTY GRAPH` DDL, ISO GQL syntax rules, and `case_chain_id` correlation guardrails.
