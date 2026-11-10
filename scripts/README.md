# scripts/

Headless alternatives to the notebook, for when a Colab Enterprise runtime is slow or
unavailable.

`load.sh` reaches the same end state as `notebooks/c_ei_01_load_explore.ipynb`—provisioning the
zero-baseline Enterprise reservation (`a4i-graph`, \$0 when idle) required for BigQuery Graph
(`GQL`) and rebuilding all five BigQuery tables in `a4i_early_intervention` with native `GEOGRAPHY`
columns (`tract_geom`, `intake_geom`, `provider_geom`) and leading-zero-safe 11-digit tract GEOIDs.
Use the notebook if you can: Section 2 proves why sorting flat provider waitlists misses multi-hop
`paper_fax` coordinator bottlenecks, and Sections 4–5 expose the all-zero `limited_english_rate`
column and 6× statewide NSCH grain traps. Use this script if you cannot.

## Running it

From the **root of the repo**, in Cloud Shell:

```bash
bash scripts/load.sh              # loads Mississippi (MS)—the default
bash scripts/load.sh AL           # Alabama (leading-zero FIPS 01)
bash scripts/load.sh CA           # California (leading-zero FIPS 06)
bash scripts/load.sh --list       # show every pre-staged state
bash scripts/load.sh --help       # usage
```

**It takes a two-letter state abbreviation (`MS`, `AL`, `GA`, `TX`, `CA`, `NY`).** Invoke it with
`bash` rather than `./scripts/load.sh` so it works regardless of whether the file's executable bit
survived how your copy of the repository was created.

If `A4I_SNAPSHOT_BUCKET` is configured in `.env` (or exported in your shell; see `.env.example`),
`load.sh` loads pre-filtered GeoParquet snapshots from Cloud Storage. Otherwise, it loads and
filters directly from the repository's `data/*.parquet` files using `bq`.

## It is safe to run more than once

Both the `a4i-graph` Enterprise reservation setup and every `--replace` table load are idempotent.
Canceling halfway through or switching states on a second run overwrites the previous state's
tables cleanly without mixing states.

## What the verification block checks

- **Enterprise graph reservation (`a4i-graph`)**: `ENTERPRISE`, `0` baseline slots, `50` autoscale
  max slots, assigned to `QUERY` jobs in your project (`US`).
- **Multi-hop graph topology & 45-day statutory breaches**: verifies `>= 2`-hop referral chains,
  `> 45`-day IDEA Part C episode breaches, and `0` orphan `source_provider_id` /
  `target_provider_id` foreign keys against `pediatric_and_ei_provider_directory`.
