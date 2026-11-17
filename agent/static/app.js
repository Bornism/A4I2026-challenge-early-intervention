/* First Milestones Clinical Workbench Frontend Logic */
"use strict";

// ---------------------------------------------------------------------------
// State & Configuration
// ---------------------------------------------------------------------------
const state = {
  sessionId: null,
  brief: null,
  health: null,
  caregiverLang: "english",
  activeTab: "pathway",
  activeGqlKey: "routing",
  briefRequestSeq: 0,
  lastModalTrigger: null,
};

const PRESET_TARGET_TAB = {
  triage: "pathway",
  audit: "hubs",
  outreach: "outreach",
};

const TAB_PANELS = {
  pathway: "panelPathway",
  hubs: "panelHubs",
  outreach: "panelOutreach",
};

// Crisp inline SVG icons (zero emojis)
const ICONS = {
  bolt: `<svg class="icon" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>`,
  clockAlert: `<svg class="icon" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>`,
  mobility: `<svg class="icon" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="1" y="3" width="15" height="13" rx="2"/><polygon points="16 8 20 8 23 11 23 16 16 16 16 8"/><circle cx="5.5" cy="18.5" r="2.5"/><circle cx="18.5" cy="18.5" r="2.5"/></svg>`,
  alertTriangle: `<svg class="icon" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>`,
  checkCircle: `<svg class="icon" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>`,
  shieldCheck: `<svg class="icon" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><polyline points="9 12 11 14 15 10"/></svg>`,
  info: `<svg class="icon" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>`,
  arrowConnector(isFax) {
    const cls = isFax ? "hop-arrow-svg fax" : "hop-arrow-svg ehr";
    return `<svg class="${cls}" width="44" height="14" viewBox="0 0 44 14" fill="none" aria-hidden="true"><line x1="2" y1="7" x2="36" y2="7" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><polyline points="32 2 39 7 32 12" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
  },
};

// ---------------------------------------------------------------------------
// DOM Helpers
// ---------------------------------------------------------------------------
const $ = (id) => document.getElementById(id);

function escapeHtml(str) {
  return String(str ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function formatInlineMarkdown(escapedLine) {
  return escapedLine
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/\*(.+?)\*/g, "<em>$1</em>")
    .replace(/`([^`]+)`/g, "<code>$1</code>");
}

function renderMarkdownLite(md) {
  const escaped = escapeHtml(md).replace(/\r\n/g, "\n");
  const lines = escaped.split("\n");
  const out = [];
  let inList = false;
  let paraBuffer = [];

  const flushPara = () => {
    if (paraBuffer.length > 0) {
      out.push(`<p>${paraBuffer.join("<br/>")}</p>`);
      paraBuffer = [];
    }
  };
  const closeList = () => {
    if (inList) {
      out.push("</ul>");
      inList = false;
    }
  };

  for (const rawLine of lines) {
    const trimmed = rawLine.trim();
    if (!trimmed) {
      flushPara();
      closeList();
      continue;
    }
    const h4Match = trimmed.match(/^####\s+(.+)$/);
    if (h4Match) {
      flushPara();
      closeList();
      out.push(`<h4>${formatInlineMarkdown(h4Match[1])}</h4>`);
      continue;
    }
    const h3Match = trimmed.match(/^###\s+(.+)$/);
    if (h3Match) {
      flushPara();
      closeList();
      out.push(`<h3>${formatInlineMarkdown(h3Match[1])}</h3>`);
      continue;
    }
    const liMatch = rawLine.match(/^\s*[-*]\s+(.+)$/);
    if (liMatch) {
      flushPara();
      if (!inList) {
        out.push("<ul>");
        inList = true;
      }
      out.push(`<li>${formatInlineMarkdown(liMatch[1])}</li>`);
      continue;
    }
    closeList();
    paraBuffer.push(formatInlineMarkdown(trimmed));
  }

  flushPara();
  closeList();
  return out.join("");
}

function shortRole(role) {
  const map = {
    Screening_Pediatric_Clinic: "Screening Clinic",
    Part_C_Intake_Coordinator: "Part C Coordinator",
    Multidisciplinary_Eval_Hub: "Eval Hub",
    EI_Therapy_Vendor: "EI Therapy Vendor",
  };
  return map[role] || String(role || "Provider").replace(/_/g, " ");
}

function formatChannel(channel) {
  const map = {
    paper_fax: "Paper Fax",
    phone_voicemail: "Voicemail",
    ehr_electronic_portal: "EHR Portal",
  };
  return map[channel] || String(channel || "Portal").replace(/_/g, " ");
}

function cleanOrgTitle(name) {
  return String(name || "").replace(/\s*\[Synthetic\]\s*/g, "").trim();
}

function formatNumber(val, fallback = "--") {
  if (val === null || val === undefined || Number.isNaN(Number(val))) return fallback;
  return Number(val).toLocaleString();
}

async function fetchJson(url, options = {}) {
  const resp = await fetch(url, options);
  if (!resp.ok) {
    let detail = `HTTP ${resp.status}`;
    try {
      const errBody = await resp.json();
      if (errBody?.detail) detail = String(errBody.detail);
    } catch {
      // Ignore non-JSON error body
    }
    throw new Error(detail);
  }
  return resp.json();
}

async function copyTextToClipboard(text) {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return;
  }
  const ta = document.createElement("textarea");
  ta.value = text;
  ta.setAttribute("readonly", "");
  ta.style.position = "fixed";
  ta.style.opacity = "0";
  document.body.appendChild(ta);
  ta.select();
  document.execCommand("copy");
  document.body.removeChild(ta);
}

// ---------------------------------------------------------------------------
// Adaptive Table Renderer (matches any <thead> column set cleanly)
// ---------------------------------------------------------------------------
function renderAdaptiveTable(tableId, rows, colDefs, emptyText) {
  const table = $(tableId);
  if (!table) return;

  let tbody = table.querySelector("tbody");
  if (!tbody) {
    tbody = document.createElement("tbody");
    table.appendChild(tbody);
  }

  let thead = table.querySelector("thead");
  let activeCols = colDefs;

  if (thead) {
    const ths = Array.from(thead.querySelectorAll("th"));
    if (ths.length > 0) {
      activeCols = ths.map((th, idx) => {
        const label = th.textContent.trim();
        return colDefs.find((c) => c.match.test(label)) || colDefs[idx] || {
          header: label,
          render: () => `<span class="muted-small">--</span>`,
        };
      });
    }
  } else {
    thead = document.createElement("thead");
    thead.innerHTML = `<tr>${colDefs.map((c) => `<th>${escapeHtml(c.header)}</th>`).join("")}</tr>`;
    table.insertBefore(thead, tbody);
  }

  if (!Array.isArray(rows) || rows.length === 0) {
    tbody.innerHTML = `<tr><td colspan="${Math.max(1, activeCols.length)}" class="muted-small">${escapeHtml(emptyText)}</td></tr>`;
    return;
  }

  tbody.innerHTML = rows
    .map((row, idx) => {
      const rowCls = row.__rowClass ? ` class="${escapeHtml(row.__rowClass)}"` : "";
      const cells = activeCols.map((col) => `<td>${col.render(row, idx)}</td>`).join("");
      return `<tr${rowCls}>${cells}</tr>`;
    })
    .join("");
}

// ---------------------------------------------------------------------------
// Tab Management (WAI-ARIA Tabs + Keyboard Arrow Navigation)
// ---------------------------------------------------------------------------
function switchTab(tabName, { moveFocus = false } = {}) {
  if (!TAB_PANELS[tabName]) return;
  state.activeTab = tabName;

  const tabs = Array.from(document.querySelectorAll('[role="tab"][data-tab]'));
  tabs.forEach((tab) => {
    const isActive = tab.dataset.tab === tabName;
    tab.setAttribute("aria-selected", String(isActive));
    tab.setAttribute("tabindex", isActive ? "0" : "-1");
    tab.classList.toggle("active", isActive);
    if (moveFocus && isActive) {
      tab.focus();
    }
  });

  Object.entries(TAB_PANELS).forEach(([key, panelId]) => {
    const panel = $(panelId);
    if (!panel) return;
    const isActive = key === tabName;
    panel.hidden = !isActive;
    panel.classList.toggle("hidden", !isActive);
  });
}

function initTabs() {
  const tabs = Array.from(document.querySelectorAll('[role="tab"][data-tab]'));
  if (tabs.length === 0) return;

  tabs.forEach((tab, idx) => {
    tab.addEventListener("click", () => {
      switchTab(tab.dataset.tab);
    });

    tab.addEventListener("keydown", (e) => {
      let nextIdx = null;
      if (e.key === "ArrowRight") {
        nextIdx = (idx + 1) % tabs.length;
      } else if (e.key === "ArrowLeft") {
        nextIdx = (idx - 1 + tabs.length) % tabs.length;
      } else if (e.key === "Home") {
        nextIdx = 0;
      } else if (e.key === "End") {
        nextIdx = tabs.length - 1;
      }
      if (nextIdx !== null) {
        e.preventDefault();
        switchTab(tabs[nextIdx].dataset.tab, { moveFocus: true });
      }
    });
  });

  switchTab(state.activeTab);
}

// ---------------------------------------------------------------------------
// Runtime & Header Renderers
// ---------------------------------------------------------------------------
function renderRuntimeMeta(runtime, engineOverride) {
  const rt = runtime || state.health || {};
  const badge = $("runtimeBadge");
  if (badge) {
    const mcp = String(rt.mcp_mode || "");
    const model = rt.gemini_model ? ` · ${rt.gemini_model}` : "";
    const live = rt.llm_credentials_active ? "Live ADK" : "Graph Preview";
    let label = `${live}${model}`;
    if (mcp.startsWith("mcp_toolbox")) {
      label = `MCP Toolbox · ${live}`;
    } else if (mcp.startsWith("google_bigquery")) {
      label = `BigQuery MCP · ${live}`;
    }
    badge.innerHTML = `${ICONS.checkCircle} <span>${escapeHtml(label)}</span>`;
  }

  const engineChip = $("engineChip");
  if (engineChip) {
    const engine = engineOverride || state.brief?.execution_engine || state.brief?.routing?.execution_engine || "";
    const isBq = String(engine).toLowerCase().includes("bigquery");
    const shortEngine = isBq
      ? "BigQuery ISO GQL"
      : engine
      ? "Local GeoParquet Graph"
      : "ISO GQL Ready";
    engineChip.textContent = shortEngine;
    if (engine) engineChip.title = String(engine);
  }
}

function renderHeaderAndKpis(brief) {
  const routing = brief.routing || {};
  const profile = routing.child_profile || {};
  const rec = routing.recommended_pathway;
  const totals = brief.network_audit?.network_totals || {};
  const agencies = Array.isArray(brief.agencies) ? brief.agencies : [];
  const lowestAgency = agencies.reduce((min, item) => {
    if (!min) return item;
    return Number(item.timely_45d_ifsp_pct) < Number(min.timely_45d_ifsp_pct) ? item : min;
  }, null);
  const hiddenDeserts = brief.outreach_zones?.hidden_ei_deserts_count;

  const subtitle = $("contextSubtitle");
  if (subtitle) {
    const parts = [`State: ${brief.state_code || "--"}`];
    if (profile.home_tract_geoid) {
      parts.push(`Tract ${profile.home_tract_geoid}${profile.county_name ? ` (${profile.county_name})` : ""}`);
    }
    if (profile.child_age_months !== undefined) {
      parts.push(`Age ${profile.child_age_months}m`);
    }
    if (profile.concern_domain) {
      parts.push(profile.concern_domain);
    }
    subtitle.textContent = parts.join(" · ");
  }

  const kpiStrip = $("kpiStrip");
  if (kpiStrip) {
    const breaches = totals.statutory_breaches_over_45d;
    const totalChains = totals.total_complete_chains;
    const timelyPct = totals.overall_timely_45d_pct;
    const recDays = rec?.expected_cumulative_days;
    const headroom = rec?.statutory_45d_headroom_days;
    const lowestPct = lowestAgency?.timely_45d_ifsp_pct;

    kpiStrip.innerHTML = `
      <div class="kpi-card kpi-danger">
        <span class="kpi-label">Breach Chains &gt;45d</span>
        <strong class="kpi-value">${breaches ?? "--"}${totalChains !== undefined ? ` / ${totalChains}` : ""}</strong>
        <span class="kpi-sub">${timelyPct !== undefined ? `${timelyPct}% timely <=45d` : "Multi-hop audit"}</span>
      </div>
      <div class="kpi-card kpi-success">
        <span class="kpi-label">Recommended Route</span>
        <strong class="kpi-value">${recDays !== undefined ? `${recDays}d` : "--"}</strong>
        <span class="kpi-sub">${headroom !== undefined ? `${headroom}d clock headroom` : "Electronic portal"}</span>
      </div>
      <div class="kpi-card kpi-info">
        <span class="kpi-label">Lowest Regional IFSP</span>
        <strong class="kpi-value">${lowestPct !== undefined ? `${lowestPct}%` : "--"}</strong>
        <span class="kpi-sub">${lowestAgency ? escapeHtml(cleanOrgTitle(lowestAgency.synthetic_agency_name)) : "OSEP Indicator C7"}</span>
      </div>
      <div class="kpi-card kpi-warn">
        <span class="kpi-label">Hidden EI Deserts</span>
        <strong class="kpi-value">${hiddenDeserts ?? "--"}</strong>
        <span class="kpi-sub">Tracts w/ 0 reachable &lt;=45d paths</span>
      </div>
    `;
  }
}

// ---------------------------------------------------------------------------
// Tab 1: Pathway & Triage Renderers
// ---------------------------------------------------------------------------
function renderGuardrails(brief) {
  const container = $("guardrailContainer");
  if (!container) return;

  const routingAlerts = Array.isArray(brief.routing?.guardrail_alerts) ? brief.routing.guardrail_alerts : [];
  const viableAlerts = Array.isArray(brief.viable_45d_paths?.guardrail_alerts) ? brief.viable_45d_paths.guardrail_alerts : [];
  const alerts = routingAlerts.length > 0 ? routingAlerts : viableAlerts;

  if (alerts.length === 0) {
    container.innerHTML = "";
    return;
  }

  container.innerHTML = alerts
    .map((a) => {
      const isHigh = String(a.severity || "").toUpperCase() === "HIGH";
      const icon = isHigh ? ICONS.clockAlert : ICONS.mobility;
      const title =
        a.code === "IDEA_PART_C_36M_AGING_OUT_CLIFF" || isHigh
          ? "36-Month Aging-Out Cliff Guardrail"
          : "Zero-Vehicle Mobility Guardrail";
      return `
        <div class="guardrail-banner ${isHigh ? "high" : "medium"}">
          <span class="guardrail-icon">${icon}</span>
          <div>
            <strong>${escapeHtml(title)}:</strong>
            <span>${escapeHtml(a.message)}</span>
          </div>
        </div>
      `;
    })
    .join("");
}

function normalizeHop(h) {
  if (!h || typeof h !== "object") return null;
  const sourceId = h.source_provider_id ?? h.source_id ?? "";
  const targetId = h.target_provider_id ?? h.target_id ?? "";
  const sourceName = h.source_name ?? h.source_provider_name ?? sourceId;
  const targetName = h.target_name ?? h.provider_name ?? targetId;
  const sourceRole = h.source_role ?? h.source_type ?? "";
  const targetRole = h.target_role ?? h.hop_type ?? h.target_type ?? "";
  const channel = h.transmission_channel ?? "ehr_electronic_portal";
  const waitDays = h.handoff_wait_days ?? h.edge_wait_days ?? h.incremental_wait_days ?? 0;
  const cumDays = h.cumulative_wait_days ?? 0;
  const isBounce = Boolean(h.is_bounce_hop || h.bounce_flag);
  const bounceReason = h.bounce_reason ?? h.handoff_reason ?? "";
  const distanceKm = h.distance_from_home_km ?? h.distance_km;
  const isBilingual = h.target_bilingual ?? h.is_bilingual_target;
  const acceptsMedicaid = h.target_medicaid ?? h.accepts_medicaid_target;

  return {
    sourceId,
    targetId,
    sourceName,
    targetName,
    sourceRole,
    targetRole,
    channel,
    waitDays,
    cumDays,
    isBounce,
    bounceReason,
    distanceKm,
    isBilingual,
    acceptsMedicaid,
  };
}

function renderHopChain(container, rawHops, isBreach, pathwayMeta = {}) {
  if (!container) return;
  const hops = (Array.isArray(rawHops) ? rawHops : []).map(normalizeHop).filter(Boolean);
  if (hops.length === 0) {
    container.innerHTML = `<span class="muted-small">No multi-hop trajectory available for current selection.</span>`;
    return;
  }

  const pieces = [];
  const first = hops[0];
  const originName = cleanOrgTitle(first.sourceName) || first.sourceId;

  pieces.push(`
    <div class="hop-card ${isBreach ? "hop-origin" : "hop-good"}">
      <div class="hop-edge-top">
        <span class="hop-edge-pill">Step 1 · Origin</span>
        <span class="hop-edge-day">Day 0</span>
      </div>
      <div class="hop-card-head">
        <span class="hop-type">${escapeHtml(shortRole(first.sourceRole || "Screening_Pediatric_Clinic"))}</span>
        <code class="hop-id">${escapeHtml(first.sourceId)}</code>
      </div>
      <div class="hop-name" title="${escapeHtml(originName)}">${escapeHtml(originName)}</div>
      <div class="hop-tags">
        <span class="mini-tag">Origin</span>
        <span class="mini-tag">Synthetic</span>
      </div>
    </div>
  `);

  hops.forEach((h, idx) => {
    const isFax = h.channel === "paper_fax";
    const chLabel = isFax ? "Fax" : h.channel.startsWith("ehr") ? "EHR" : formatChannel(h.channel);
    const stepNum = idx + 2;

    const nodeCls = h.isBounce ? "hop-bounce" : isBreach ? "hop-breach-step" : "hop-good";
    const targetName = cleanOrgTitle(h.targetName) || h.targetId;
    const tags = [];

    if (h.isBounce) {
      tags.push(
        `<span class="mini-tag warn" title="${escapeHtml(h.bounceReason)}">${ICONS.alertTriangle} Bounce</span>`
      );
    } else if (!isBreach) {
      const med = h.acceptsMedicaid ?? pathwayMeta.all_nodes_medicaid_enrolled;
      const bil = h.isBilingual ?? pathwayMeta.all_care_nodes_bilingual;
      if (med && bil) {
        tags.push(`<span class="mini-tag ok">${ICONS.checkCircle} Medicaid/Bilingual</span>`);
      } else if (med) {
        tags.push(`<span class="mini-tag ok">${ICONS.checkCircle} Medicaid</span>`);
      } else if (bil) {
        tags.push(`<span class="mini-tag ok">${ICONS.checkCircle} Bilingual</span>`);
      } else {
        tags.push(`<span class="mini-tag ok">${ICONS.checkCircle} Compliant</span>`);
      }
    } else {
      tags.push(`<span class="mini-tag">Handoff</span>`);
    }

    if (h.distanceKm !== undefined && h.distanceKm !== null) {
      tags.push(`<span class="mini-tag">${escapeHtml(h.distanceKm)} km</span>`);
    }

    pieces.push(`
      <div class="hop-card ${nodeCls}">
        <div class="hop-edge-top">
          <span class="hop-edge-pill ${isFax ? "fax" : "ehr"}">${ICONS.arrowConnector(isFax)} ${escapeHtml(chLabel)} +${escapeHtml(h.waitDays)}d</span>
          <span class="hop-edge-day">Day ${escapeHtml(h.cumDays)}</span>
        </div>
        <div class="hop-card-head">
          <span class="hop-type">Step ${stepNum} · ${escapeHtml(shortRole(h.targetRole))}</span>
          <code class="hop-id">${escapeHtml(h.targetId)}</code>
        </div>
        <div class="hop-name" title="${escapeHtml(targetName)}">${escapeHtml(targetName)}</div>
        <div class="hop-tags">${tags.join("")}</div>
      </div>
    `);
  });

  container.innerHTML = `<div class="hop-grid">${pieces.join("")}</div>`;
}

function renderPathwaysAndClock(brief) {
  const routing = brief.routing || {};
  const profile = routing.child_profile || {};
  const bounce = routing.cautionary_historical_bounce_chain;
  const rec = routing.recommended_pathway;

  const bounceMeta = $("bounceSummaryMeta");
  const bounceCanvas = $("bouncePathCanvas");
  if (bounce) {
    if (bounceMeta) {
      bounceMeta.innerHTML = `
        <span>${escapeHtml(bounce.case_chain_id)} · ${escapeHtml(bounce.total_hops)} Hops (${escapeHtml(bounce.paper_fax_hops ?? 0)} paper_fax) · <strong>${escapeHtml(bounce.total_wait_days)}d</strong> (+${escapeHtml(bounce.days_over_45d_limit)}d over limit)</span>
      `;
    }
    renderHopChain(bounceCanvas, bounce.hops, true);
  } else {
    if (bounceMeta) bounceMeta.textContent = "No historical >45d bounce chain matched.";
    renderHopChain(bounceCanvas, [], true);
  }

  const recMeta = $("recSummaryMeta");
  const recCanvas = $("recPathCanvas");
  if (rec) {
    const savedTxt = routing.days_saved_vs_bounce_loop
      ? ` · Saves ${routing.days_saved_vs_bounce_loop}d vs. bounce`
      : "";
    if (recMeta) {
      recMeta.innerHTML = `
        <span class="meta-ok">${ICONS.checkCircle} ${escapeHtml(rec.total_hops)} Hops · ${escapeHtml(rec.expected_cumulative_days)}d (${escapeHtml(rec.statutory_45d_headroom_days)}d headroom)${escapeHtml(savedTxt)}</span>
      `;
    }
    renderHopChain(recCanvas, rec.hops, false, rec);

    const pct = Math.min(100, Math.max(0, Math.round((Number(rec.expected_cumulative_days || 0) / 45) * 100)));
    const clockFill = $("clockBarFill");
    if (clockFill) {
      clockFill.style.width = `${pct}%`;
      clockFill.setAttribute("aria-valuenow", String(rec.expected_cumulative_days ?? 0));
    }
    const clockDays = $("clockDaysLabel");
    if (clockDays) {
      clockDays.textContent = `Expected Cumulative Timeline: ${rec.expected_cumulative_days} / 45 Calendar Days`;
    }
    const ageCliff = $("ageCliffLabel");
    if (ageCliff) {
      const recAge = profile.est_age_at_ifsp_recommended_months ?? "--";
      const bounceAge = profile.est_age_at_ifsp_if_bounced_months ?? "--";
      ageCliff.textContent = `Projected Age at IFSP: ${recAge}m (vs. ${bounceAge}m if bounced · 36m Part C Cutoff)`;
    }
  } else {
    if (recMeta) recMeta.textContent = "No compliant <=45-day electronic pathway found.";
    renderHopChain(recCanvas, [], false);
    const clockFill = $("clockBarFill");
    if (clockFill) clockFill.style.width = "0%";
    const clockDays = $("clockDaysLabel");
    if (clockDays) clockDays.textContent = "Expected Cumulative Timeline: -- / 45 Calendar Days";
    const ageCliff = $("ageCliffLabel");
    if (ageCliff) ageCliff.textContent = "Projected Age at IFSP: -- months (36m Part C Cutoff)";
  }
}

function renderViablePaths(brief) {
  const container = $("viablePathsList");
  if (!container) return;

  const vp = brief.viable_45d_paths || {};
  const paths = Array.isArray(vp.viable_paths) ? vp.viable_paths : [];
  const pruned = vp.pruned_high_bounce_edges_count;

  if (paths.length === 0) {
    container.innerHTML = `<div class="muted-small">No viable &lt;=45-day pruned graph paths returned for the active filters.</div>`;
    return;
  }

  const headerHtml = `
    <div class="viable-summary-bar">
      <span class="viable-count">${ICONS.checkCircle} <strong>${paths.length}</strong> viable &lt;=45-day routes</span>
      ${pruned !== undefined ? `<span class="mini-tag">Pruned ${escapeHtml(pruned)} high-bounce edges</span>` : ""}
    </div>
  `;

  const rowsHtml = paths
    .slice(0, 6)
    .map((p) => {
      const hopsCount =
        p.hop_count ??
        p.hops_count ??
        (Array.isArray(p.nodes) ? Math.max(1, p.nodes.length - 1) : "--");
      const days = p.total_expected_days ?? "--";
      const dist = p.distance_km ?? p.max_travel_km;
      const routeChain = Array.isArray(p.nodes) && p.nodes.length > 0
        ? p.nodes.join(" -> ")
        : p.nodes_summary ||
          (p.start_provider_id && p.eval_provider_id
            ? `${p.start_provider_id} -> ${p.eval_provider_id}`
            : p.path_id || "Viable Path");
      const evalLabel = p.eval_name ? cleanOrgTitle(p.eval_name) : "";
      const channels = Array.isArray(p.channels_used)
        ? p.channels_used.map(formatChannel).join(", ")
        : p.channels_used
        ? formatChannel(p.channels_used)
        : "";

      return `
        <div class="viable-path-row">
          <div class="viable-path-main">
            <code class="viable-nodes">${escapeHtml(routeChain)}</code>
            ${evalLabel ? `<span class="viable-eval-name">${escapeHtml(evalLabel)}</span>` : ""}
          </div>
          <div class="viable-path-meta">
            <span class="mini-tag ok">${escapeHtml(days)}d</span>
            <span class="mini-tag">${escapeHtml(hopsCount)} hops</span>
            ${dist !== undefined && dist !== null ? `<span class="mini-tag">${escapeHtml(dist)} km</span>` : ""}
            ${channels ? `<span class="mini-tag">${escapeHtml(channels)}</span>` : ""}
            ${p.score !== undefined && p.score !== null ? `<span class="mini-tag">Score ${escapeHtml(p.score)}</span>` : ""}
          </div>
        </div>
      `;
    })
    .join("");

  container.innerHTML = `${headerHtml}<div class="viable-list-stack">${rowsHtml}</div>`;
}

function renderCaregiverNote() {
  const noteBox = $("caregiverNoteBox");
  if (!noteBox) return;
  const notes = state.brief?.caregiver_notes;
  if (!notes) {
    noteBox.textContent = "";
    return;
  }
  const raw = notes[state.caregiverLang] || notes.english || "";
  noteBox.innerHTML = renderMarkdownLite(raw);
}

// ---------------------------------------------------------------------------
// Tab 2: Bounce Hubs & Simulator Renderers
// ---------------------------------------------------------------------------
function renderAuditAndBottlenecks(brief) {
  const audit = brief.network_audit || {};
  const totals = audit.network_totals || {};
  const btwn = brief.bottleneck_hubs || {};
  const topHub = audit.top_hidden_bounce_hub;

  const strip = $("auditSummaryStrip");
  if (strip) {
    strip.innerHTML = `
      <div class="audit-stat-pill">
        <span class="audit-stat-lbl">Complete Chains</span>
        <strong>${formatNumber(totals.total_complete_chains)}</strong>
      </div>
      <div class="audit-stat-pill">
        <span class="audit-stat-lbl">3-4 Hop Chains</span>
        <strong>${formatNumber(totals.chains_3_to_4_hops)}</strong>
      </div>
      <div class="audit-stat-pill danger">
        <span class="audit-stat-lbl">&gt;45d Breaches</span>
        <strong>${formatNumber(totals.statutory_breaches_over_45d)}</strong>
      </div>
      <div class="audit-stat-pill warn">
        <span class="audit-stat-lbl">30m+ in Breach</span>
        <strong>${formatNumber(totals.toddlers_30m_plus_in_breach)}</strong>
      </div>
      <div class="audit-stat-pill">
        <span class="audit-stat-lbl">Top Hidden Hub</span>
        <strong>${topHub ? escapeHtml(topHub.provider_id) : "--"}</strong>
      </div>
    `;
  }

  const coordsRaw =
    audit.coordinator_multihop_ranking ||
    audit.intake_coordinator_bounce_hub_ranking ||
    [];
  const coords = coordsRaw.map((c, idx) => ({
    ...c,
    __rowClass: idx === 0 ? "row-highlight-danger" : "",
  }));

  renderAdaptiveTable(
    "coordAuditTable",
    coords,
    [
      {
        header: "Coordinator Hub",
        match: /hub|coordinator|org|provider/i,
        render: (c) => {
          const name = cleanOrgTitle(c.synthetic_org_name || c.synthetic_organization_name);
          const city = c.city ? ` (${escapeHtml(c.city)})` : "";
          return `<div><code>${escapeHtml(c.provider_id)}</code>${city}</div>${name ? `<div class="muted-small">${escapeHtml(name)}</div>` : ""}`;
        },
      },
      {
        header: "Flat Wait",
        match: /flat|internal|waitlist/i,
        render: (c) => {
          const wl = c.active_waitlist_count ?? c.flat_active_waitlist;
          const wlTxt = wl !== undefined ? ` <span class="muted-small">(WL ${escapeHtml(wl)})</span>` : "";
          return `${escapeHtml(c.flat_median_internal_wait_days ?? "--")}d${wlTxt}`;
        },
      },
      {
        header: ">45d Breaches",
        match: /breach|chain/i,
        render: (c) => {
          const total = c.total_multihop_chains_touched ?? c.routed_episodes;
          const share = c.bounce_breach_share_pct ?? c.breach_rate_pct;
          const denom = total !== undefined ? `/${escapeHtml(total)}` : "";
          const pct = share !== undefined ? ` (${escapeHtml(share)}%)` : "";
          return `<strong>${escapeHtml(c.breached_over_45d ?? "--")}${denom}</strong>${pct}`;
        },
      },
      {
        header: "Excess Days",
        match: /excess/i,
        render: (c) => `+${escapeHtml(c.total_excess_days_over_45 ?? 0)}d`,
      },
      {
        header: "Primary Reason",
        match: /reason|cause|bounce/i,
        render: (c) => `<span class="muted-small">${escapeHtml(c.primary_bounce_reason || "paper_fax / slot mismatch")}</span>`,
      },
    ],
    "No coordinator multi-hop ranking data available."
  );

  const hubRows = (Array.isArray(btwn.bottleneck_hubs) ? btwn.bottleneck_hubs : []).map((b, idx) => ({
    ...b,
    __rowClass: idx === 0 ? "row-highlight-warn" : "",
  }));

  renderAdaptiveTable(
    "bottleneckTable",
    hubRows,
    [
      {
        header: "Bottleneck Hub",
        match: /hub|org|provider|node/i,
        render: (b) => {
          const name = cleanOrgTitle(b.synthetic_org_name || b.organization_name);
          const loc = b.city ? b.city : shortRole(b.node_role);
          return `<div><code>${escapeHtml(b.provider_id)}</code> <span class="muted-small">(${escapeHtml(loc)})</span></div><div class="muted-small">${escapeHtml(name)}</div>`;
        },
      },
      {
        header: "Flow Share",
        match: /betweenness|flow|share/i,
        render: (b) => `<strong>${escapeHtml(b.betweenness_flow_share_pct ?? "--")}%</strong>`,
      },
      {
        header: "Breaches",
        match: /breach|chain|path/i,
        render: (b) => {
          const cnt = b.breach_chains_touched ?? b.breached_paths_through_hub ?? "--";
          const tot = btwn.total_breached_multihop_chains;
          return tot !== undefined ? `${escapeHtml(cnt)} / ${escapeHtml(tot)}` : escapeHtml(cnt);
        },
      },
      {
        header: "Paper Fax %",
        match: /fax/i,
        render: (b) => `${escapeHtml(b.paper_fax_share_pct ?? "--")}%`,
      },
      {
        header: "Flat Wait",
        match: /flat|internal|wait/i,
        render: (b) => `${escapeHtml(b.flat_median_internal_wait_days ?? b.flat_internal_wait_days ?? "--")}d`,
      },
      {
        header: "Primary Bounce",
        match: /reason|bounce|cause/i,
        render: (b) => `<span class="muted-small">${escapeHtml(b.primary_bounce_reason || "--")}</span>`,
      },
    ],
    "No intermediate bottleneck hubs returned."
  );

  const simHubSelect = $("simHubSelect");
  if (simHubSelect) {
    const prevHub = simHubSelect.value;
    const optionsHtml = coordsRaw
      .map((c) => {
        const cityTxt = c.city ? `${c.city} · ` : "";
        return `<option value="${escapeHtml(c.provider_id)}">${escapeHtml(c.provider_id)} (${escapeHtml(cityTxt)}${escapeHtml(c.flat_median_internal_wait_days ?? "--")}d flat wait)</option>`;
      })
      .join("");
    simHubSelect.innerHTML =
      optionsHtml +
      `<option value="ALL">ALL Regional Coordinators (${escapeHtml(brief.state_code || "")})</option>`;
    if (prevHub && [...simHubSelect.options].some((o) => o.value === prevHub)) {
      simHubSelect.value = prevHub;
    }
  }
}

function renderSimulationCard(sim) {
  const box = $("simImpactBox");
  const episodeList = $("simEpisodeList");

  if (!sim || !sim.impact_summary) {
    if (box) box.innerHTML = `<div class="muted-small">Run a counterfactual simulation to inspect breach reductions.</div>`;
    if (episodeList) episodeList.innerHTML = "";
    return;
  }

  const s = sim.impact_summary;
  if (box) {
    box.innerHTML = `
      <div>
        <strong>Counterfactual Target: <code>${escapeHtml(sim.target_intervention_scope || sim.target_provider_id || "ALL")}</code></strong>
        <p class="muted-small" style="margin-top:3px">
          ${escapeHtml(cleanOrgTitle(sim.target_organization_name))} · Upgrading <code>paper_fax</code> to <code>ehr_electronic_portal</code> + bilingual/Medicaid slot pre-check
        </p>
        <div class="sim-metric-grid">
          <div class="sim-stat">
            <strong>${escapeHtml(s.baseline_breaches_over_45d)} &rarr; ${escapeHtml(s.simulated_breaches_over_45d)}</strong>
            <span>&gt;45-Day Breaches (${escapeHtml(s.breaches_eliminated)} Eliminated)</span>
          </div>
          <div class="sim-stat">
            <strong>${escapeHtml(s.total_delayed_child_days_saved)} days</strong>
            <span>Delayed Child-Days Saved</span>
          </div>
          <div class="sim-stat">
            <strong>${escapeHtml(s.mean_episode_wait_before_days)}d &rarr; ${escapeHtml(s.mean_episode_wait_after_days)}d</strong>
            <span>Mean Episode Wait (${escapeHtml(s.episodes_evaluated ?? "--")} chains)</span>
          </div>
          <div class="sim-stat">
            <strong>${sim.flat_spreadsheet_appearance ? escapeHtml(sim.flat_spreadsheet_appearance.median_internal_wait_days) + "d" : "5-6d"}</strong>
            <span>Deceptive Flat Internal Wait</span>
          </div>
        </div>
      </div>
    `;
  }

  if (episodeList) {
    const episodes = Array.isArray(sim.episode_level_simulation) ? sim.episode_level_simulation : [];
    if (episodes.length === 0) {
      episodeList.innerHTML = `<div class="muted-small">No affected multi-hop episodes for this hub selection.</div>`;
      return;
    }

    episodeList.innerHTML = episodes
      .slice(0, 12)
      .map((ep) => {
        const flipped = Boolean(ep.flipped_to_compliant_45d);
        const statusBadge = flipped
          ? `<span class="mini-tag ok">${ICONS.checkCircle} Flipped &lt;=45d</span>`
          : ep.simulated_wait_days <= 45
          ? `<span class="mini-tag">Already &lt;=45d</span>`
          : `<span class="mini-tag warn">Still &gt;45d</span>`;
        return `
          <div class="sim-episode-row ${flipped ? "flipped" : ""}">
            <div class="sim-episode-head">
              <code>${escapeHtml(ep.case_chain_id)}</code>
              <span class="muted-small">${escapeHtml(ep.child_age_months)}m · ${escapeHtml(ep.concern_domain)}</span>
              ${statusBadge}
            </div>
            <div class="sim-episode-metrics">
              <span>Hops: ${escapeHtml(ep.baseline_hops)} &rarr; ${escapeHtml(ep.simulated_hops)}</span>
              <span>Wait: ${escapeHtml(ep.baseline_wait_days)}d &rarr; <strong>${escapeHtml(ep.simulated_wait_days)}d</strong></span>
              <span class="saved-days">-${escapeHtml(ep.child_days_saved)}d saved</span>
            </div>
          </div>
        `;
      })
      .join("");
  }
}

// ---------------------------------------------------------------------------
// Tab 3: Outreach Deserts, Equity Audit & Agency KPIs Renderers
// ---------------------------------------------------------------------------
function renderOutreachAndEquity(brief) {
  const outreachZones = brief.outreach_zones || {};
  const screening = brief.screening_outreach || {};
  const equity = brief.equity_audit || {};
  const agencies = Array.isArray(brief.agencies) ? brief.agencies : [];

  const formulaBanner = $("outreachFormulaBanner");
  if (formulaBanner) {
    const note =
      screening.formula_note ||
      "Non-racial outreach priority index (excludes audit_* demographic shares and all-zero ACS limited_english_rate).";
    const deserts = outreachZones.hidden_ei_deserts_count;
    formulaBanner.innerHTML = `
      <span class="banner-icon">${ICONS.info}</span>
      <div>
        <strong>Non-Racial Outreach Scoring &amp; Hidden EI Desert Detection${deserts !== undefined ? ` (${escapeHtml(deserts)} deserts)` : ""}:</strong>
        <span>${escapeHtml(note)}</span>
      </div>
    `;
  }

  const zones = Array.isArray(outreachZones.ranked_outreach_zones)
    ? outreachZones.ranked_outreach_zones
    : [];
  const screeningMap = new Map(
    (Array.isArray(screening.priority_screening_tracts) ? screening.priority_screening_tracts : []).map((t) => [
      t.census_tract_geoid,
      t,
    ])
  );

  const mergedZones =
    zones.length > 0
      ? zones.map((z) => ({
          ...z,
          verified_downstream_45d_pathway: screeningMap.get(z.census_tract_geoid)?.verified_downstream_45d_pathway,
          __rowClass: z.is_hidden_ei_desert ? "row-highlight-danger" : "",
        }))
      : (screening.priority_screening_tracts || []).map((t) => ({
          ...t,
          outreach_priority_score: t.non_racial_outreach_priority_score,
          is_hidden_ei_desert: false,
          mobility_support_recommended: Boolean(t.verified_downstream_45d_pathway?.deploy_mobile_eval_van_with_screening),
          reachable_45d_paths_count: t.verified_downstream_45d_pathway?.clears_45d_mandate ? 1 : 0,
          nearest_any_clinic_km: t.verified_downstream_45d_pathway?.eval_hub_distance_km,
        }));

  renderAdaptiveTable(
    "outreachZonesTable",
    mergedZones,
    [
      {
        header: "Census Tract",
        match: /tract|geoid/i,
        render: (z) => `<code>${escapeHtml(z.census_tract_geoid)}</code><div class="muted-small">${escapeHtml(z.county_name || "")}</div>`,
      },
      {
        header: "County",
        match: /county/i,
        render: (z) => escapeHtml(z.county_name || "--"),
      },
      {
        header: "Under 5",
        match: /under|child|pop/i,
        render: (z) => formatNumber(z.children_under_5_count),
      },
      {
        header: "Poverty %",
        match: /poverty/i,
        render: (z) => `${escapeHtml(z.poverty_pct ?? "--")}%`,
      },
      {
        header: "Zero-Veh %",
        match: /veh/i,
        render: (z) => `${escapeHtml(z.zero_vehicle_pct ?? "--")}%`,
      },
      {
        header: "Nearest Clinic",
        match: /nearest|clinic|km|dist/i,
        render: (z) => (z.nearest_any_clinic_km !== undefined ? `${escapeHtml(z.nearest_any_clinic_km)} km` : "--"),
      },
      {
        header: "<=45d Paths",
        match: /45d|path|reach/i,
        render: (z) => `<strong>${escapeHtml(z.reachable_45d_paths_count ?? "--")}</strong>`,
      },
      {
        header: "Status / Mobility",
        match: /desert|status|mobility|flag/i,
        render: (z) => {
          const desertTag = z.is_hidden_ei_desert
            ? `<span class="mini-tag warn">${ICONS.alertTriangle} Hidden Desert</span>`
            : `<span class="mini-tag ok">${ICONS.checkCircle} Reachable</span>`;
          const mobTag = z.mobility_support_recommended
            ? `<span class="mini-tag">NEMT / Mobile</span>`
            : "";
          return `<div class="tag-inline">${desertTag}${mobTag}</div>`;
        },
      },
      {
        header: "Score",
        match: /score|priority/i,
        render: (z) => `<strong>${escapeHtml(z.outreach_priority_score ?? z.non_racial_outreach_priority_score ?? "--")}</strong>`,
      },
    ],
    "No priority outreach tracts returned."
  );

  const eqRows = Array.isArray(equity.breach_vs_timely_neighborhood_equity)
    ? equity.breach_vs_timely_neighborhood_equity
    : [];
  renderAdaptiveTable(
    "equityTable",
    eqRows,
    [
      {
        header: "Episode Outcome",
        match: /outcome|status/i,
        render: (r) => `<strong>${escapeHtml(r.ifsp_status)}</strong>`,
      },
      {
        header: "Cases",
        match: /case|episode/i,
        render: (r) => formatNumber(r.episodes),
      },
      {
        header: "Mean Wait",
        match: /wait/i,
        render: (r) => (r.mean_wait_days !== undefined ? `${escapeHtml(r.mean_wait_days)}d` : "--"),
      },
      {
        header: "Poverty",
        match: /poverty/i,
        render: (r) => `${escapeHtml(r.avg_tract_poverty_pct ?? "--")}%`,
      },
      {
        header: "Zero-Veh",
        match: /veh/i,
        render: (r) => `${escapeHtml(r.avg_zero_vehicle_pct ?? "--")}%`,
      },
      {
        header: "Black / Hisp / White",
        match: /black\s*\/|hisp|race|demograph/i,
        render: (r) =>
          `${escapeHtml(r.audit_black_pct ?? "--")}% / ${escapeHtml(r.audit_hispanic_pct ?? "--")}% / ${escapeHtml(r.audit_white_pct ?? "--")}%`,
      },
      {
        header: "Black %",
        match: /^black/i,
        render: (r) => `${escapeHtml(r.audit_black_pct ?? "--")}%`,
      },
      {
        header: "Hispanic %",
        match: /^hispanic/i,
        render: (r) => `${escapeHtml(r.audit_hispanic_pct ?? "--")}%`,
      },
      {
        header: "Indigenous %",
        match: /indigenous|native/i,
        render: (r) => `${escapeHtml(r.audit_indigenous_pct ?? "--")}%`,
      },
      {
        header: "Asian %",
        match: /asian/i,
        render: (r) => `${escapeHtml(r.audit_asian_pct ?? "--")}%`,
      },
      {
        header: "White %",
        match: /^white/i,
        render: (r) => `${escapeHtml(r.audit_white_pct ?? "--")}%`,
      },
    ],
    "No post-output equity rows available."
  );

  renderAdaptiveTable(
    "agencyKpiTable",
    agencies,
    [
      {
        header: "Agency",
        match: /agency|name|id/i,
        render: (a) => `<code>${escapeHtml(a.agency_id)}</code><div class="muted-small">${escapeHtml(cleanOrgTitle(a.synthetic_agency_name))}</div>`,
      },
      {
        header: "Counties",
        match: /count/i,
        render: (a) => `<span class="muted-small">${escapeHtml(a.served_counties || "--")}</span>`,
      },
      {
        header: "FY",
        match: /fy|year/i,
        render: (a) => escapeHtml(a.reporting_fiscal_year ?? "--"),
      },
      {
        header: "Referrals",
        match: /referral/i,
        render: (a) => formatNumber(a.annual_referrals_received),
      },
      {
        header: "Evals",
        match: /eval/i,
        render: (a) => formatNumber(a.evaluations_completed_count),
      },
      {
        header: "<=45d IFSP",
        match: /timely|ifsp|45/i,
        render: (a) => {
          const pct = Number(a.timely_45d_ifsp_pct);
          const tagCls = pct < 65 ? "warn" : "ok";
          return `<span class="mini-tag ${tagCls}">${escapeHtml(a.timely_45d_ifsp_pct ?? "--")}%</span> <span class="muted-small">(${formatNumber(a.initial_ifsp_within_45_days_count)})</span>`;
        },
      },
      {
        header: "Capacity Delays",
        match: /delay|capacity/i,
        render: (a) => formatNumber(a.ifsp_delayed_capacity_count),
      },
    ],
    "No regional Part C agency KPIs available."
  );

  const nschRows =
    equity.statewide_nsch_screening_context ||
    outreachZones.statewide_nsch_screening_gap_context ||
    [];
  renderAdaptiveTable(
    "nschTable",
    nschRows,
    [
      {
        header: "Stratum",
        match: /stratum|id/i,
        render: (n) => `<code>${escapeHtml(n.survey_stratum_id)}</code>`,
      },
      {
        header: "Level",
        match: /level|geo/i,
        render: (n) => `<span class="mini-tag">${escapeHtml(n.geographic_level || "Statewide")}</span>`,
      },
      {
        header: "Income (FPL)",
        match: /income|fpl/i,
        render: (n) => escapeHtml(n.household_income_fpl_band || "--"),
      },
      {
        header: "Home Language",
        match: /lang/i,
        render: (n) => `<strong>${escapeHtml(n.primary_home_language || "--")}</strong>`,
      },
      {
        header: "Screened %",
        match: /screen/i,
        render: (n) => `${escapeHtml(n.standardized_screening_rate_pct ?? "--")}%`,
      },
      {
        header: "Follow-Up %",
        match: /follow/i,
        render: (n) => `${escapeHtml(n.followup_requested_pct ?? "--")}%`,
      },
    ],
    "No statewide HRSA NSCH strata available."
  );

  const rigorBox = $("rigorChecklist");
  if (rigorBox) {
    const lowestNsch = nschRows[0];
    const highestNsch = nschRows[nschRows.length - 1];
    const nschSummary =
      lowestNsch && highestNsch
        ? `${escapeHtml(lowestNsch.primary_home_language)}: ${escapeHtml(lowestNsch.standardized_screening_rate_pct)}% vs. ${escapeHtml(highestNsch.primary_home_language)}: ${escapeHtml(highestNsch.standardized_screening_rate_pct)}%`
        : "6 statewide strata";
    const totalChains = brief.network_audit?.network_totals?.total_complete_chains ?? "--";

    rigorBox.innerHTML = `
      <ul class="rigor-list">
        <li>${ICONS.checkCircle} <span><strong>ACS Zero-Column Trap Caught:</strong> <code>limited_english_rate = 0.0</code> excluded from routing &amp; outreach formulas.</span></li>
        <li>${ICONS.checkCircle} <span><strong>NSCH 6x Grain Preserved:</strong> Statewide-only screening gap (${nschSummary}) never cross-joined to tracts.</span></li>
        <li>${ICONS.checkCircle} <span><strong>Prefix-Safe ISO GQL:</strong> Correlated <code>case_chain_id</code> + deduplicated 4-hop chains (${escapeHtml(totalChains)} complete chains).</span></li>
        <li>${ICONS.checkCircle} <span><strong>Bias Firewall:</strong> <code>audit_*</code> demographic shares attached strictly post-output.</span></li>
        <li>${ICONS.checkCircle} <span><strong>Stage-Safe Provenance:</strong> <code>SYN-PROV-*</code> &amp; <code>SYN-PARTC-*</code> are 100% <code>[Synthetic]</code>.</span></li>
      </ul>
    `;
  }
}

// ---------------------------------------------------------------------------
// ISO GQL Modal & Focus Management
// ---------------------------------------------------------------------------
function getGqlText(key) {
  const brief = state.brief || {};
  if (key === "audit") {
    return [
      brief.network_audit?.iso_gql_query,
      brief.bottleneck_hubs?.iso_gql_query,
    ]
      .filter(Boolean)
      .join("\n\n-- ---------------------------------------------------------------------------\n\n");
  }
  if (key === "outreach") {
    return brief.outreach_zones?.iso_gql_query || "-- No outreach ISO GQL query available.";
  }
  return [
    brief.routing?.iso_gql_query,
    brief.viable_45d_paths?.iso_gql_query,
  ]
    .filter(Boolean)
    .join("\n\n-- ---------------------------------------------------------------------------\n\n");
}

function setGqlTab(key) {
  state.activeGqlKey = key;
  document.querySelectorAll("[data-gql]").forEach((btn) => {
    const isActive = btn.dataset.gql === key;
    btn.classList.toggle("active", isActive);
    btn.setAttribute("aria-pressed", String(isActive));
    if (btn.getAttribute("role") === "tab") {
      btn.setAttribute("aria-selected", String(isActive));
    }
  });
  const codeBlock = $("gqlCodeBlock");
  if (codeBlock) {
    codeBlock.textContent = getGqlText(key) || "-- ISO GQL query unavailable.";
  }
}

function isGqlModalOpen() {
  const modal = $("gqlModal");
  return Boolean(modal && !modal.hidden && !modal.classList.contains("hidden"));
}

function openGqlModal() {
  const modal = $("gqlModal");
  if (!modal) return;
  state.lastModalTrigger = document.activeElement;

  const defaultKey =
    state.activeTab === "hubs"
      ? "audit"
      : state.activeTab === "outreach"
      ? "outreach"
      : "routing";
  setGqlTab(defaultKey);

  modal.hidden = false;
  modal.classList.remove("hidden");
  modal.setAttribute("aria-hidden", "false");

  const closeBtn = $("closeGqlBtn");
  if (closeBtn) closeBtn.focus();
}

function closeGqlModal() {
  const modal = $("gqlModal");
  if (!modal) return;
  modal.hidden = true;
  modal.classList.add("hidden");
  modal.setAttribute("aria-hidden", "true");

  if (state.lastModalTrigger && typeof state.lastModalTrigger.focus === "function") {
    state.lastModalTrigger.focus();
  }
  state.lastModalTrigger = null;
}

// ---------------------------------------------------------------------------
// Master Brief Renderer & Data Loaders
// ---------------------------------------------------------------------------
function renderBrief(brief) {
  if (!brief || typeof brief !== "object") return;
  state.brief = brief;

  renderRuntimeMeta(brief.runtime, brief.execution_engine || brief.routing?.execution_engine);
  renderHeaderAndKpis(brief);
  renderGuardrails(brief);
  renderPathwaysAndClock(brief);
  renderViablePaths(brief);
  renderCaregiverNote();
  renderAuditAndBottlenecks(brief);
  renderSimulationCard(brief.counterfactual_simulation);
  renderOutreachAndEquity(brief);

  if (isGqlModalOpen()) {
    setGqlTab(state.activeGqlKey);
  }
}

async function loadHealth() {
  try {
    state.health = await fetchJson("/api/health");
    renderRuntimeMeta(state.health);
  } catch {
    const badge = $("runtimeBadge");
    if (badge) badge.textContent = "Backend Connecting";
  }
}

async function loadBriefForState(stateCode) {
  const reqId = ++state.briefRequestSeq;
  const subtitle = $("contextSubtitle");
  if (subtitle) subtitle.textContent = `Loading ${stateCode} multi-hop graph diagnostics...`;

  const data = await fetchJson(`/api/brief?state=${encodeURIComponent(stateCode)}`);
  if (reqId !== state.briefRequestSeq) return data;

  renderBrief(data);
  return data;
}

// ---------------------------------------------------------------------------
// Chat & Presets
// ---------------------------------------------------------------------------
function appendMessage(role, text, tools = []) {
  const chatMessages = $("chatMessages");
  if (!chatMessages) return;

  const div = document.createElement("div");
  div.className = `msg msg-${role}`;

  let traceHtml = "";
  if (Array.isArray(tools) && tools.length > 0) {
    traceHtml =
      `<div class="tool-trace-row">` +
      tools
        .map((t) => `<span class="tool-pill">${ICONS.bolt} ${escapeHtml(t)}</span>`)
        .join("") +
      `</div>`;
  }

  div.innerHTML = traceHtml + (role === "agent" ? renderMarkdownLite(text) : escapeHtml(text));
  chatMessages.appendChild(div);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

function buildPresetPrompt(presetKey, stateCode) {
  const tract =
    state.brief?.routing?.child_profile?.home_tract_geoid ||
    (stateCode === "CA" ? "06047000801" : stateCode === "AL" ? "01073000100" : "28049003500");
  const hub =
    state.brief?.network_audit?.top_hidden_bounce_hub?.provider_id ||
    `SYN-PROV-${stateCode}-011`;

  const presets = {
    triage: `Route an incoming 32-month-old toddler in census tract ${tract} (${stateCode}) referred for Social-Communication / Autism Screen. Family speaks Spanish at home, uses Medicaid, and has no household vehicle. Ensure we clear the 45-day IDEA Part C clock and provide an English and Spanish caregiver action note.`,
    audit: `Trace the 3-to-4-hop referral chains in ${stateCode} that breached the 45-day IDEA Part C limit, explain why ${hub} looks healthy in a flat waitlist sort yet drives multi-hop breaches, and simulate upgrading ${hub} from paper fax to electronic e-referral with bilingual slot pre-checks.`,
    outreach: `For this community developmental screening season in ${stateCode}, which high-poverty, zero-vehicle under-5 census tracts should mobile screening days visit first so every screened toddler has a verified <=45-day bilingual downstream evaluation pathway?`,
  };
  return presets[presetKey] || "";
}

async function sendChatMessage(messageText, targetTabOnDone = null) {
  const stateSelect = $("stateSelect");
  const sendBtn = $("sendBtn");
  const stateCode = stateSelect ? stateSelect.value : "MS";

  appendMessage("user", messageText);
  if (sendBtn) {
    sendBtn.disabled = true;
    sendBtn.textContent = "Tracing...";
  }

  try {
    const data = await fetchJson("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: messageText,
        session_id: state.sessionId,
        state_code: stateCode,
      }),
    });

    state.sessionId = data.session_id || state.sessionId;
    if (data.brief) {
      renderBrief(data.brief);
    }
    appendMessage("agent", data.reply || "", data.tools_invoked || []);

    if (targetTabOnDone) {
      switchTab(targetTabOnDone);
    }
  } catch (err) {
    appendMessage("agent", `Error communicating with triage backend: ${err.message}`);
  } finally {
    if (sendBtn) {
      sendBtn.disabled = false;
      sendBtn.textContent = "Run Triage";
    }
  }
}

// ---------------------------------------------------------------------------
// Event Wiring & Initialization
// ---------------------------------------------------------------------------
function bindEvents() {
  const stateSelect = $("stateSelect");
  if (stateSelect) {
    stateSelect.addEventListener("change", async () => {
      const st = stateSelect.value;
      try {
        await loadBriefForState(st);
        appendMessage(
          "agent",
          `Switched active dataset context to **${st}**. Loaded \`[Synthetic]\` CareNode organizations, multi-hop referral chains, and real US Census ACS under-5 tracts.`,
          ["generate_complete_45d_brief"]
        );
      } catch (err) {
        appendMessage("agent", `Unable to load brief for ${st}: ${err.message}`);
      }
    });
  }

  const chatForm = $("chatForm");
  const chatInput = $("chatInput");
  if (chatForm && chatInput) {
    chatForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const txt = chatInput.value.trim();
      if (!txt) return;
      chatInput.value = "";
      await sendChatMessage(txt);
    });

    chatInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
        e.preventDefault();
        chatForm.requestSubmit();
      }
    });
  }

  document.querySelectorAll(".preset-btn[data-preset]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const presetKey = btn.dataset.preset;
      const stateCode = $("stateSelect")?.value || "MS";
      const prompt = buildPresetPrompt(presetKey, stateCode);
      if (!prompt) return;

      document.querySelectorAll(".preset-btn[data-preset]").forEach((b) => {
        const active = b === btn;
        b.classList.toggle("active", active);
        b.setAttribute("aria-pressed", String(active));
      });

      sendChatMessage(prompt, PRESET_TARGET_TAB[presetKey] || null);
    });
  });

  const runSimBtn = $("runSimBtn");
  const simHubSelect = $("simHubSelect");
  if (runSimBtn && simHubSelect) {
    runSimBtn.addEventListener("click", async () => {
      const origLabel = runSimBtn.textContent;
      runSimBtn.disabled = true;
      runSimBtn.textContent = "Simulating...";
      try {
        const simData = await fetchJson("/api/simulate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            state_code: $("stateSelect")?.value || "MS",
            target_provider_id: simHubSelect.value,
            upgrade_fax_to_ehr: true,
            precheck_bilingual_and_slot_capacity: true,
          }),
        });
        renderSimulationCard(simData);
      } catch (err) {
        const box = $("simImpactBox");
        if (box) {
          box.innerHTML = `<div class="muted-small">Simulation failed: ${escapeHtml(err.message)}</div>`;
        }
      } finally {
        runSimBtn.disabled = false;
        runSimBtn.textContent = origLabel;
      }
    });
  }

  document.querySelectorAll(".lang-btn[data-lang]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const lang = btn.dataset.lang === "spanish" ? "spanish" : "english";
      state.caregiverLang = lang;
      document.querySelectorAll(".lang-btn[data-lang]").forEach((b) => {
        const active = b === btn;
        b.classList.toggle("active", active);
        b.setAttribute("aria-pressed", String(active));
      });
      renderCaregiverNote();
    });
  });

  const copyNoteBtn = $("copyNoteBtn");
  if (copyNoteBtn) {
    copyNoteBtn.addEventListener("click", async () => {
      const txt = state.brief?.caregiver_notes?.[state.caregiverLang] || "";
      if (!txt) return;
      const origHtml = copyNoteBtn.innerHTML;
      try {
        await copyTextToClipboard(txt);
        copyNoteBtn.innerHTML = `${ICONS.checkCircle} Copied`;
        setTimeout(() => {
          copyNoteBtn.innerHTML = origHtml;
        }, 1500);
      } catch {
        copyNoteBtn.textContent = "Copy Failed";
        setTimeout(() => {
          copyNoteBtn.innerHTML = origHtml;
        }, 1500);
      }
    });
  }

  const toggleGqlBtn = $("toggleGqlBtn");
  if (toggleGqlBtn) {
    toggleGqlBtn.addEventListener("click", () => {
      if (isGqlModalOpen()) {
        closeGqlModal();
      } else {
        openGqlModal();
      }
    });
  }

  const closeGqlBtn = $("closeGqlBtn");
  if (closeGqlBtn) {
    closeGqlBtn.addEventListener("click", closeGqlModal);
  }

  const gqlModal = $("gqlModal");
  if (gqlModal) {
    gqlModal.addEventListener("click", (e) => {
      if (e.target === gqlModal) {
        closeGqlModal();
      }
    });
  }

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && isGqlModalOpen()) {
      e.preventDefault();
      closeGqlModal();
    }
  });

  document.querySelectorAll("[data-gql]").forEach((btn) => {
    btn.addEventListener("click", () => {
      setGqlTab(btn.dataset.gql);
    });
  });

  const copyGqlBtn = $("copyGqlBtn");
  if (copyGqlBtn) {
    copyGqlBtn.addEventListener("click", async () => {
      const codeBlock = $("gqlCodeBlock");
      const txt = codeBlock?.textContent || "";
      if (!txt) return;
      const origHtml = copyGqlBtn.innerHTML;
      try {
        await copyTextToClipboard(txt);
        copyGqlBtn.innerHTML = `${ICONS.checkCircle} Copied SQL/GQL`;
        setTimeout(() => {
          copyGqlBtn.innerHTML = origHtml;
        }, 1500);
      } catch {
        copyGqlBtn.textContent = "Copy Failed";
        setTimeout(() => {
          copyGqlBtn.innerHTML = origHtml;
        }, 1500);
      }
    });
  }
}

async function init() {
  initTabs();
  bindEvents();
  await loadHealth();

  const initialState = $("stateSelect")?.value || "MS";
  try {
    const brief = await loadBriefForState(initialState);
    const totals = brief.network_audit?.network_totals || {};
    const topHub = brief.network_audit?.top_hidden_bounce_hub;
    const routedDenom =
      topHub?.total_multihop_chains_touched ?? topHub?.routed_episodes ?? "--";

    appendMessage(
      "agent",
      `### Welcome to First Milestones (${brief.state_code})\n\n` +
        `Loaded **\`[Synthetic]\` CareNode providers** and **${totals.total_complete_chains ?? "--"} multi-hop referral chains** (` +
        `**${totals.statutory_breaches_over_45d ?? "--"}** breaching the 45-day IDEA Part C limit). ` +
        (topHub
          ? `Intake Hub **\`${topHub.provider_id}\`** shows only a **${topHub.flat_median_internal_wait_days}-day** internal wait in a flat table, yet drives **${topHub.breached_over_45d}/${routedDenom}** >45-day bounce chains via \`paper_fax\`.\n\n`
          : "\n\n") +
        `Select a **Quick Demo Scenario** above or enter a custom triage or bottleneck query.`,
      ["generate_complete_45d_brief", "mcp_get_regional_agency_performance"]
    );
  } catch (err) {
    appendMessage(
      "agent",
      `Unable to initialize workbench brief for ${initialState}: ${err.message}`
    );
  }
}

init();
