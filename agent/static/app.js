/* First Milestones Coordinator Workbench Frontend Logic */

let currentSessionId = null;
let currentBrief = null;
let activeCaregiverLang = "english";

const stateSelect = document.getElementById("stateSelect");
const chatMessages = document.getElementById("chatMessages");
const chatForm = document.getElementById("chatForm");
const chatInput = document.getElementById("chatInput");
const sendBtn = document.getElementById("sendBtn");
const toggleGqlBtn = document.getElementById("toggleGqlBtn");
const gqlDrawer = document.getElementById("gqlDrawer");
const simHubSelect = document.getElementById("simHubSelect");
const runSimBtn = document.getElementById("runSimBtn");
const copyNoteBtn = document.getElementById("copyNoteBtn");

function escapeHtml(str) {
  return String(str ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function renderMarkdownLite(md) {
  let html = escapeHtml(md);
  html = html.replace(/^### (.+)$/gm, "<h3>$1</h3>");
  html = html.replace(/^#### (.+)$/gm, "<h4>$1</h4>");
  html = html.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  html = html.replace(/\*(.+?)\*/g, "<em>$1</em>");
  html = html.replace(/`([^`]+)`/g, "<code>$1</code>");
  html = html.replace(/^- (.+)$/gm, "<li>$1</li>");
  html = html.replace(/(<li>.*<\/li>)/gs, "<ul>$1</ul>");
  html = html.replace(/\n{2,}/g, "<br/><br/>");
  return html;
}

function shortRole(role) {
  const map = {
    Screening_Pediatric_Clinic: "Screening Clinic",
    Part_C_Intake_Coordinator: "Part C Coordinator",
    Multidisciplinary_Eval_Hub: "Multidisciplinary Eval Hub",
    EI_Therapy_Vendor: "EI Therapy Vendor",
  };
  return map[role] || role;
}

function cleanOrgTitle(name) {
  return String(name || "").replace(/\s*\[Synthetic\]\s*/g, "").trim();
}

function appendMessage(role, text, tools = []) {
  const div = document.createElement("div");
  div.className = `msg msg-${role}`;
  let traceHtml = "";
  if (tools && tools.length > 0) {
    traceHtml =
      `<div class="tool-trace-row">` +
      tools.map((t) => `<span class="tool-pill">⚡ ${escapeHtml(t)}</span>`).join("") +
      `</div>`;
  }
  div.innerHTML = traceHtml + (role === "agent" ? renderMarkdownLite(text) : escapeHtml(text));
  chatMessages.appendChild(div);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

function renderHopChain(container, hops, isBreach) {
  if (!hops || hops.length === 0) {
    container.innerHTML = `<span class="muted-small">No trajectory available.</span>`;
    return;
  }

  const pieces = [];
  const first = hops[0];
  pieces.push(`
    <div class="node-box ${isBreach ? "" : "node-good"}">
      <div>
        <div class="node-id">${escapeHtml(first.source_provider_id)}</div>
        <div class="node-role">${escapeHtml(shortRole(first.source_role))}</div>
        <div class="node-name">${escapeHtml(cleanOrgTitle(first.source_name))}</div>
      </div>
      <div class="node-tags"><span class="mini-tag">[Synthetic] Origin</span></div>
    </div>
  `);

  hops.forEach((h) => {
    const isFax = h.transmission_channel === "paper_fax";
    const chLabel = isFax ? "paper_fax" : h.transmission_channel === "phone_voicemail" ? "voicemail" : "ehr_portal";
    const bounceCls = h.is_bounce_hop ? "node-bounce" : isBreach ? "" : "node-good";

    pieces.push(`
      <div class="edge-arrow">
        <span class="edge-channel ${isFax ? "fax" : "ehr"}">${escapeHtml(chLabel)} · +${h.handoff_wait_days}d</span>
        <span class="edge-line">──────▶</span>
        <span class="edge-cum">Day ${h.cumulative_wait_days}</span>
      </div>
    `);

    const tags = [`<span class="mini-tag">[Synthetic]</span>`];
    if (h.is_bounce_hop) {
      tags.push(`<span class="mini-tag warn">BOUNCE HOP</span>`);
    } else if (!isBreach) {
      tags.push(`<span class="mini-tag ok">✓ Medicaid &amp; Bilingual</span>`);
    }
    if (h.distance_from_home_km !== undefined) {
      tags.push(`<span class="mini-tag">${h.distance_from_home_km} km</span>`);
    }

    pieces.push(`
      <div class="node-box ${bounceCls}">
        <div>
          <div class="node-id">${escapeHtml(h.target_provider_id)}</div>
          <div class="node-role">${escapeHtml(shortRole(h.target_role))}</div>
          <div class="node-name">${escapeHtml(cleanOrgTitle(h.target_name))}</div>
        </div>
        <div class="node-tags">${tags.join("")}</div>
      </div>
    `);
  });

  container.innerHTML = pieces.join("");
}

function renderSimulationCard(sim) {
  const box = document.getElementById("simImpactBox");
  if (!sim || !sim.impact_summary) {
    box.innerHTML = "";
    return;
  }
  const s = sim.impact_summary;
  box.innerHTML = `
    <div>
      <strong>Counterfactual Target: <code>${escapeHtml(sim.target_intervention_scope)}</code></strong>
      <p class="muted-small" style="margin-top:3px">
        ${escapeHtml(cleanOrgTitle(sim.target_organization_name))} · Upgrading <code>paper_fax</code> → <code>ehr_electronic_portal</code> + bilingual/Medicaid slot pre-check
      </p>
      <div class="sim-metric-grid">
        <div class="sim-stat">
          <strong>${s.baseline_breaches_over_45d} → ${s.simulated_breaches_over_45d}</strong>
          <span>&gt;45-Day Breaches (${s.breaches_eliminated} Eliminated)</span>
        </div>
        <div class="sim-stat">
          <strong>${s.total_delayed_child_days_saved} days</strong>
          <span>Delayed Child-Days Saved</span>
        </div>
        <div class="sim-stat">
          <strong>${s.mean_episode_wait_before_days}d → ${s.mean_episode_wait_after_days}d</strong>
          <span>Mean Episode Wait</span>
        </div>
        <div class="sim-stat">
          <strong>${sim.flat_spreadsheet_appearance ? sim.flat_spreadsheet_appearance.median_internal_wait_days + "d" : "5-6d"}</strong>
          <span>Deceptive Flat Internal Wait</span>
        </div>
      </div>
    </div>
  `;
}

function renderCaregiverNote() {
  const noteBox = document.getElementById("caregiverNoteBox");
  if (!currentBrief || !currentBrief.caregiver_notes) {
    noteBox.textContent = "";
    return;
  }
  const raw = currentBrief.caregiver_notes[activeCaregiverLang] || "";
  noteBox.innerHTML = renderMarkdownLite(raw);
}

function renderBrief(brief) {
  currentBrief = brief;
  const routing = brief.routing || {};
  const profile = routing.child_profile || {};
  const rec = routing.recommended_pathway;
  const bounce = routing.cautionary_historical_bounce_chain;
  const audit = brief.network_audit || {};
  const totals = audit.network_totals || {};
  const equity = brief.equity_audit || {};

  // Runtime status
  if (brief.runtime) {
    document.getElementById("runtimeStatusText").textContent =
      `Engine: ${routing.execution_engine || brief.execution_engine} · Model: ${brief.runtime.gemini_model}`;
    document.getElementById("mcpBadge").textContent =
      brief.runtime.mcp_mode.startsWith("mcp_toolbox")
        ? "MCP Toolbox Connected"
        : brief.runtime.mcp_mode.startsWith("google_bigquery")
        ? "BigQuery MCP Connected"
        : "MCP + ISO GQL Ready";
  }

  // Header Subtitle & KPI Strip
  const lowestAgency = (brief.agencies || [])[0];
  document.getElementById("briefScopeSubtitle").textContent =
    `State: ${brief.state_code} · Home Tract ${profile.home_tract_geoid || ""} (${profile.county_name || ""}) · Child Age: ${profile.child_age_months}m (${profile.concern_domain})`;

  document.getElementById("kpiStrip").innerHTML = `
    <div class="kpi-chip">
      <span class="kpi-val" style="color:#dc2626">${totals.statutory_breaches_over_45d ?? "--"}/${totals.total_complete_chains ?? "--"}</span>
      <span class="kpi-lbl">State Chains &gt;45d</span>
    </div>
    <div class="kpi-chip">
      <span class="kpi-val" style="color:#047857">${rec ? rec.expected_cumulative_days + "d" : "--"}</span>
      <span class="kpi-lbl">Recommended Route</span>
    </div>
    <div class="kpi-chip">
      <span class="kpi-val" style="color:#1d4ed8">${lowestAgency ? lowestAgency.timely_45d_ifsp_pct + "%" : "--"}</span>
      <span class="kpi-lbl">Lowest Regional IFSP</span>
    </div>
  `;

  // Guardrail Banners
  const alerts = routing.guardrail_alerts || [];
  document.getElementById("guardrailContainer").innerHTML = alerts
    .map(
      (a) => `
      <div class="guardrail-banner ${a.severity === "HIGH" ? "high" : ""}">
        <strong>${a.severity === "HIGH" ? "⏰ 36-Month Aging-Out Cliff Guardrail:" : "🚐 Zero-Vehicle Mobility Guardrail:"}</strong>
        ${escapeHtml(a.message)}
      </div>`
    )
    .join("");

  // GQL Drawer
  gqlDrawer.textContent =
    (routing.iso_gql_query || "") + "\n\n" + (audit.iso_gql_query || "");

  // Path 1: Historical Bounce Loop
  if (bounce) {
    document.getElementById("bounceSummaryMeta").textContent =
      `${bounce.case_chain_id} · ${bounce.total_hops} Hops (${bounce.paper_fax_hops} paper_fax) · ${bounce.total_wait_days} Days (+${bounce.days_over_45d_limit}d Over Federal Limit ❌)`;
    renderHopChain(document.getElementById("bouncePathCanvas"), bounce.hops, true);
  }

  // Path 2: Recommended <=45d Pathway
  if (rec) {
    const savedTxt = routing.days_saved_vs_bounce_loop
      ? ` · Saves ${routing.days_saved_vs_bounce_loop} Days vs. Bounce Loop`
      : "";
    document.getElementById("recSummaryMeta").textContent =
      `${rec.total_hops} Hops · ${rec.expected_cumulative_days} Calendar Days (${rec.statutory_45d_headroom_days}d Headroom ✓)${savedTxt}`;
    renderHopChain(document.getElementById("recPathCanvas"), rec.hops, false);

    const pct = Math.min(100, Math.round((rec.expected_cumulative_days / 45.0) * 100));
    document.getElementById("clockBarFill").style.width = `${pct}%`;
    document.getElementById("clockDaysLabel").textContent =
      `Expected Cumulative Timeline: ${rec.expected_cumulative_days} / 45 Federal Statutory Days`;
    document.getElementById("ageCliffLabel").textContent =
      `Projected Age at Initial IFSP: ${profile.est_age_at_ifsp_recommended_months}m (vs. ${profile.est_age_at_ifsp_if_bounced_months}m if bounced · 36m Cutoff)`;
  }

  // Coordinator Audit Table + Sim Selector
  const coords = audit.intake_coordinator_bounce_hub_ranking || [];
  const tbody = document.querySelector("#coordAuditTable tbody");
  tbody.innerHTML = coords
    .map(
      (c, idx) => `
      <tr style="${idx === 0 ? "background:#fff1f2;font-weight:600" : ""}">
        <td><code>${escapeHtml(c.provider_id)}</code> (${escapeHtml(c.city)})</td>
        <td>${c.flat_median_internal_wait_days}d <span class="muted-small">(WL ${c.flat_active_waitlist})</span></td>
        <td>${c.breached_over_45d}/${c.routed_episodes} (${c.breach_rate_pct}%)</td>
        <td>+${c.total_excess_days_over_45}d</td>
      </tr>`
    )
    .join("");

  const prevHub = simHubSelect.value;
  simHubSelect.innerHTML =
    coords
      .map(
        (c) =>
          `<option value="${escapeHtml(c.provider_id)}">${escapeHtml(c.provider_id)} (${escapeHtml(c.city)} · ${c.flat_median_internal_wait_days}d flat wait)</option>`
      )
      .join("") + `<option value="ALL">ALL Regional Coordinators (${brief.state_code})</option>`;
  if (prevHub && [...simHubSelect.options].some((o) => o.value === prevHub)) {
    simHubSelect.value = prevHub;
  }

  renderSimulationCard(brief.counterfactual_simulation);

  // Equity Table & Rigor Box
  const eqRows = equity.breach_vs_timely_neighborhood_equity || [];
  document.querySelector("#equityTable tbody").innerHTML = eqRows
    .map(
      (r) => `
      <tr>
        <td><strong>${escapeHtml(r.ifsp_status)}</strong></td>
        <td>${r.episodes}</td>
        <td>${r.avg_tract_poverty_pct}%</td>
        <td>${r.avg_zero_vehicle_pct}%</td>
        <td>${r.audit_black_pct}% / ${r.audit_hispanic_pct}% / ${r.audit_white_pct}%</td>
      </tr>`
    )
    .join("");

  const nschRows = equity.statewide_nsch_screening_context || [];
  const lowestNsch = nschRows[0];
  const highestNsch = nschRows[nschRows.length - 1];
  document.getElementById("rigorChecklist").innerHTML = `
    <strong>Verified Data &amp; Graph Rigor Guardrails</strong>
    <ul>
      <li><strong>ACS Zero-Column Trap Caught:</strong> <code>limited_english_rate = 0.0</code> excluded from formulas.</li>
      <li><strong>NSCH 6x Grain Preserved:</strong> Statewide-only screening gap (${lowestNsch ? lowestNsch.primary_home_language + ": " + lowestNsch.standardized_screening_rate_pct + "%" : ""} vs. ${highestNsch ? highestNsch.standardized_screening_rate_pct + "%" : ""}) never cross-joined to tracts.</li>
      <li><strong>Prefix-Safe ISO GQL:</strong> Correlated <code>case_chain_id</code> + deduplicated 4-hop <code>Vendor→Vendor</code> prefixes (${totals.total_complete_chains} exact chains).</li>
      <li><strong>Stage-Safe Provenance:</strong> <code>SYN-PROV-*</code> &amp; <code>SYN-PARTC-*</code> are 100% <code>[Synthetic]</code>.</li>
    </ul>
  `;

  renderCaregiverNote();
}

async function loadBriefForState(stateCode) {
  const resp = await fetch(`/api/brief?state=${encodeURIComponent(stateCode)}`);
  const data = await resp.json();
  renderBrief(data);
  return data;
}

async function sendChatMessage(messageText) {
  const stateCode = stateSelect.value;
  appendMessage("user", messageText);
  sendBtn.disabled = true;
  sendBtn.textContent = "Tracing...";

  try {
    const resp = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: messageText,
        session_id: currentSessionId,
        state_code: stateCode,
      }),
    });
    const data = await resp.json();
    currentSessionId = data.session_id;
    if (data.brief) {
      renderBrief(data.brief);
    }
    appendMessage("agent", data.reply, data.tools_invoked || []);
  } catch (err) {
    appendMessage("agent", `Error communicating with triage backend: ${err.message}`);
  } finally {
    sendBtn.disabled = false;
    sendBtn.textContent = "Run Triage";
  }
}

// Event Listeners
stateSelect.addEventListener("change", async () => {
  const st = stateSelect.value;
  await loadBriefForState(st);
  appendMessage(
    "agent",
    `Switched active dataset context to **${st}**. Loaded 30 \`[Synthetic]\` CareNode organizations, 44 multi-hop referral chains, and real US Census ACS under-5 tracts.`,
    ["generate_complete_45d_brief"]
  );
});

chatForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const txt = chatInput.value.trim();
  if (!txt) return;
  chatInput.value = "";
  await sendChatMessage(txt);
});

document.querySelectorAll(".chip").forEach((btn) => {
  btn.addEventListener("click", () => {
    const st = stateSelect.value;
    const tract =
      currentBrief?.routing?.child_profile?.home_tract_geoid ||
      (st === "CA" ? "06047000801" : "28049003500");
    const hub =
      currentBrief?.network_audit?.top_hidden_bounce_hub?.provider_id ||
      `SYN-PROV-${st}-011`;

    const presets = {
      triage: `Route an incoming 32-month-old toddler in census tract ${tract} (${st}) referred for Social-Communication / Autism Screen. Family speaks Spanish at home, uses Medicaid, and has no household vehicle. Ensure we clear the 45-day IDEA Part C clock and provide an English and Spanish caregiver action note.`,
      audit: `Trace the 3-to-4-hop referral chains in ${st} that breached the 45-day IDEA Part C limit, explain why ${hub} looks healthy in a flat waitlist sort yet drives multi-hop breaches, and simulate upgrading ${hub} from paper fax to electronic e-referral with bilingual slot pre-checks.`,
      outreach: `For this community developmental screening season in ${st}, which high-poverty, zero-vehicle under-5 census tracts should mobile screening days visit first so every screened toddler has a verified <=45-day bilingual downstream evaluation pathway?`,
    };
    sendChatMessage(presets[btn.dataset.preset]);
  });
});

toggleGqlBtn.addEventListener("click", () => {
  gqlDrawer.classList.toggle("hidden");
});

runSimBtn.addEventListener("click", async () => {
  runSimBtn.disabled = true;
  try {
    const resp = await fetch("/api/simulate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        state_code: stateSelect.value,
        target_provider_id: simHubSelect.value,
        upgrade_fax_to_ehr: true,
        precheck_bilingual_and_slot_capacity: true,
      }),
    });
    const simData = await resp.json();
    renderSimulationCard(simData);
  } finally {
    runSimBtn.disabled = false;
  }
});

document.querySelectorAll(".tab-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    activeCaregiverLang = btn.dataset.lang;
    renderCaregiverNote();
  });
});

copyNoteBtn.addEventListener("click", async () => {
  const txt = currentBrief?.caregiver_notes?.[activeCaregiverLang] || "";
  if (!txt) return;
  await navigator.clipboard.writeText(txt);
  copyNoteBtn.textContent = "Copied ✓";
  setTimeout(() => {
    copyNoteBtn.textContent = "Copy Note";
  }, 1500);
});

// Initial Hydration
(async function init() {
  const brief = await loadBriefForState(stateSelect.value);
  const topHub = brief?.network_audit?.top_hidden_bounce_hub;
  appendMessage(
    "agent",
    `### Welcome to First Milestones (${brief.state_code})\n\n` +
      `Loaded **30 \`[Synthetic]\` CareNode providers** and **44 multi-hop referral chains** (` +
      `**${brief.network_audit.network_totals.statutory_breaches_over_45d}** breaching the 45-day IDEA Part C limit). ` +
      `Notice on the right how Intake Desk **\`${topHub?.provider_id}\`** has only a **${topHub?.flat_median_internal_wait_days}-day** internal wait in a flat table, yet drives **${topHub?.breached_over_45d}/${topHub?.routed_episodes}** >45-day bounce chains via \`paper_fax\`.\n\n` +
      `Select a **Quick Demo Scenario** above or ask a custom triage/audit question.`,
    ["generate_complete_45d_brief", "mcp_get_regional_agency_performance"]
  );
})();
