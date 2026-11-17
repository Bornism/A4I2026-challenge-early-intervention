-- =============================================================================
-- A4I 2026 · Challenge 04 ("First Milestones")
-- BigQuery Property Graph DDL (ISO/IEC 39075 GQL)
--
-- Syntax guardrails enforced:
--   1. Unbackticked dataset-qualified table/view names inside NODE/EDGE TABLES.
--   2. REFERENCES CareNode (provider_id) and REFERENCES Neighborhood (tract_geoid)
--      use the node alias without dataset.
--   3. Excludes GEOGRAPHY columns (`provider_geom`, `tract_geom`) and governed
--      columns (`limited_english_rate`, `audit_*`) so all vertex/edge properties
--      are scalar GQL-compatible types (`latitude` & `longitude` remain available).
-- =============================================================================

CREATE OR REPLACE VIEW a4i_early_intervention.v_graph_neighborhoods AS
SELECT
  LPAD(census_tract_geoid, 11, '0') AS tract_geoid,
  state_code,
  county_name,
  children_under_5_count,
  poverty_rate,
  no_vehicle_rate,
  assistance_rate,
  median_household_income,
  latitude,
  longitude
FROM a4i_early_intervention.acs_under5_tract_demographics;

CREATE OR REPLACE VIEW a4i_early_intervention.v_graph_refers_to_edges AS
SELECT
  referral_event_id,
  source_provider_id,
  target_provider_id,
  case_chain_id,
  hop_sequence,
  handoff_wait_days,
  transmission_channel,
  handoff_reason,
  concern_domain,
  child_age_months,
  child_home_tract_geoid,
  IF(STARTS_WITH(handoff_reason, 'Re-Referral Bounce'), 1.0, 0.0) AS bounce_flag
FROM a4i_early_intervention.deidentified_part_c_referral_logs;

CREATE OR REPLACE VIEW a4i_early_intervention.v_graph_serves_area_edges AS
SELECT
  CONCAT(p.provider_id, '_', LPAD(n.census_tract_geoid, 11, '0')) AS serves_edge_id,
  p.provider_id,
  LPAD(n.census_tract_geoid, 11, '0') AS tract_geoid,
  ROUND(ST_DISTANCE(ST_GEOGPOINT(p.longitude, p.latitude), ST_GEOGPOINT(n.longitude, n.latitude)) / 1000.0, 2) AS travel_distance_km,
  CAST(ROUND((ST_DISTANCE(ST_GEOGPOINT(p.longitude, p.latitude), ST_GEOGPOINT(n.longitude, n.latitude)) / 1000.0) * 1.5, 0) AS INT64) AS estimated_travel_minutes,
  (p.node_role IN ('Part_C_Intake_Coordinator', 'Multidisciplinary_Eval_Hub') AND p.bilingual_services_listed) AS mobile_visit_capable
FROM a4i_early_intervention.pediatric_and_ei_provider_directory AS p
JOIN a4i_early_intervention.acs_under5_tract_demographics AS n
  ON p.state_code = n.state_code
WHERE ST_DISTANCE(ST_GEOGPOINT(p.longitude, p.latitude), ST_GEOGPOINT(n.longitude, n.latitude)) <= 80000;

CREATE OR REPLACE PROPERTY GRAPH a4i_early_intervention.ReferralGraph
  NODE TABLES (
    a4i_early_intervention.pediatric_and_ei_provider_directory AS CareNode
      KEY (provider_id)
      LABEL CareNode
      PROPERTIES ALL COLUMNS EXCEPT (provider_geom),
    a4i_early_intervention.v_graph_neighborhoods AS Neighborhood
      KEY (tract_geoid)
      LABEL Neighborhood
      PROPERTIES ALL COLUMNS
  )
  EDGE TABLES (
    a4i_early_intervention.deidentified_part_c_referral_logs AS ReferralHandoff
      KEY (referral_event_id)
      SOURCE KEY (source_provider_id) REFERENCES CareNode (provider_id)
      DESTINATION KEY (target_provider_id) REFERENCES CareNode (provider_id)
      LABEL ReferralHandoff
      PROPERTIES ALL COLUMNS,
    a4i_early_intervention.v_graph_refers_to_edges AS REFERS_TO
      KEY (referral_event_id)
      SOURCE KEY (source_provider_id) REFERENCES CareNode (provider_id)
      DESTINATION KEY (target_provider_id) REFERENCES CareNode (provider_id)
      LABEL REFERS_TO
      PROPERTIES ALL COLUMNS,
    a4i_early_intervention.v_graph_serves_area_edges AS SERVES_AREA
      KEY (serves_edge_id)
      SOURCE KEY (provider_id) REFERENCES CareNode (provider_id)
      DESTINATION KEY (tract_geoid) REFERENCES Neighborhood (tract_geoid)
      LABEL SERVES_AREA
      PROPERTIES ALL COLUMNS
  );
