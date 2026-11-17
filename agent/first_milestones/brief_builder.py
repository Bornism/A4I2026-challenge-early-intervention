"""Structured 45-Day Pathway & Bottleneck Brief composer (with EN/ES Caregiver Notes).

Assembles a complete, UI-ready structured artifact combining:
  1. Multi-hop `<=45`-day compliant pathway + cautionary 4-hop `paper_fax` bounce loop
  2. Regional Bounce Hub diagnosis + Counterfactual single-hub intervention impact
  3. Post-Output Equity Audit (`audit_*` shares + zero-vehicle mobility + NSCH context)
  4. Warm, jargon-free English & Spanish caregiver action notes
"""

from __future__ import annotations

from typing import Any

from .tools import (
    detect_regional_bottleneck_hubs,
    find_viable_45d_paths,
    rank_outreach_zones,
)
from .tools.equity_audit import prioritize_community_screening_tracts, run_post_output_equity_audit
from .tools.graph_audit import audit_multihop_bounce_hubs, simulate_hub_intervention
from .tools.graph_routing import find_compliant_45d_pathways
from .tools.reference_lookups import lookup_regional_agency_kpis


def _clean_org_name(raw_name: str) -> str:
    """Keeps `[Synthetic]` transparency while formatting cleanly for caregiver notes."""
    return raw_name.strip()


def build_caregiver_notes(routing_result: dict[str, Any]) -> dict[str, str]:
    """Generates plain-language English & Spanish caregiver action notes for a pathway."""
    profile = routing_result.get("child_profile", {})
    rec = routing_result.get("recommended_pathway")
    if not rec:
        return {
            "english": "Your Early Intervention coordinator is arranging an expedited evaluation and transportation support within the 45-day federal timeline.",
            "spanish": "Su coordinador de Intervención Temprana está organizando una evaluación acelerada y apoyo de transporte dentro del plazo federal de 45 días.",
        }

    hops = rec.get("hops", [])
    total_days = rec.get("expected_cumulative_days", 30)
    age_m = profile.get("child_age_months", 22)
    domain = profile.get("concern_domain", "developmental milestones")
    needs_nemt = (not profile.get("has_household_vehicle", True)) or (
        profile.get("tract_zero_vehicle_pct", 0.0) >= 10.0
    )

    coord_hop = hops[0] if len(hops) >= 1 else {}
    eval_hop = hops[1] if len(hops) >= 3 else None
    vendor_hop = hops[-1] if len(hops) >= 2 else {}

    coord_name = _clean_org_name(coord_hop.get("target_name", "Regional Intake Coordinator [Synthetic]"))
    coord_days = coord_hop.get("cumulative_wait_days", 6)

    if eval_hop:
        eval_name = _clean_org_name(eval_hop.get("target_name", "Developmental Evaluation Center [Synthetic]"))
        eval_days = eval_hop.get("cumulative_wait_days", 18)
        step2_en = (
            f"2. **Bilingual Developmental Checkup (By Day {eval_days}):** **{eval_name}** will complete your child's "
            f"play-based evaluation ({domain}) in your preferred language at zero out-of-pocket cost under Medicaid."
        )
        step2_es = (
            f"2. **Evaluación del Desarrollo Bilingüe (Para el Día {eval_days}):** **{eval_name}** realizará la evaluación "
            f"basada en el juego de su hijo/a ({domain}) en español, sin ningún costo para su familia a través de Medicaid."
        )
        step3_num = "3"
    else:
        step2_en = ""
        step2_es = ""
        step3_num = "2"

    vendor_name = _clean_org_name(vendor_hop.get("target_name", "Early Intervention Therapy Team [Synthetic]"))

    nemt_en = (
        "\n- **Free Ride & Home/Mobile Option:** Because getting across town shouldn't delay care, your coordinator has flagged **free Medicaid ride assistance (NEMT)** and home/mobile visit options."
        if needs_nemt
        else ""
    )
    nemt_es = (
        "\n- **Transporte Gratuito y Opción a Domicilio:** Para que el transporte nunca sea una barrera, su coordinador activó el **transporte gratuito de Medicaid (NEMT)** y opciones de visita móvil o en casa."
        if needs_nemt
        else ""
    )

    cliff_en = (
        f"\n- **Age-3 Transition Support:** Since your toddler is {age_m} months old, we will also help you plan smoothly for age-3 preschool support so there is zero gap in care."
        if age_m >= 30
        else ""
    )
    cliff_es = (
        f"\n- **Apoyo de Transición a los 3 Años:** Como su niño/a tiene {age_m} meses, también prepararemos juntos la transición preescolar de los 3 años para que no haya ninguna interrupción en sus terapias."
        if age_m >= 30
        else ""
    )

    en_lines = [
        f"**Your Child's Early Milestones Plan (Target: ~{total_days} Calendar Days — Well Under the 45-Day Federal Guarantee)**",
        "",
        f"1. **Welcome Call & Electronic Intake (By Day {coord_days}):** **{coord_name}** has received your clinic's electronic referral today (no paper fax delays) and confirmed Medicaid & bilingual support.",
    ]
    if step2_en:
        en_lines.append(step2_en)
    en_lines.extend([
        f"{step3_num}. **Family Service Plan & First Therapy Steps (By Day {total_days}):** Together with **{vendor_name}**, we will finalize your Individualized Family Service Plan (IFSP) and begin support.",
        "",
        "**What You Need to Know:**",
        "- **Zero Cost & Bilingual Rights:** Early Intervention evaluations and interpreter support are free to your family."
        + nemt_en
        + cliff_en,
        "- *(Demo Notice: All provider names `[Synthetic]` are fictional stage-safe organizations.)*",
    ])

    es_lines = [
        f"**Plan de Primeros Pasos de su Hijo/a (Meta: ~{total_days} Días Calendario — Dentro de la Garantía Federal de 45 Días)**",
        "",
        f"1. **Llamada de Bienvenida y Registro Electrónico (Para el Día {coord_days}):** **{coord_name}** recibió hoy la referencia electrónica de su clínica (sin demoras de fax en papel) y confirmó cobertura de Medicaid y atención bilingüe.",
    ]
    if step2_es:
        es_lines.append(step2_es)
    es_lines.extend([
        f"{step3_num}. **Plan Familiar (IFSP) e Inicio de Terapia (Para el Día {total_days}):** Junto con **{vendor_name}**, completaremos su Plan Individualizado de Servicios Familiares (IFSP) para comenzar el apoyo.",
        "",
        "**Lo Que Su Familia Debe Saber:**",
        "- **Sin Costo y en Su Idioma:** Las evaluaciones de Intervención Temprana y el servicio en español son completamente gratuitos para su familia."
        + nemt_es
        + cliff_es,
        "- *(Aviso de Demostración: Todos los proveedores `[Synthetic]` son organizaciones ficticias.)*",
    ])

    return {
        "english": "\n".join(en_lines),
        "spanish": "\n".join(es_lines),
    }


def generate_complete_45d_brief(
    child_tract_geoid: str = "",
    child_age_months: int = 32,
    concern_domain: str = "Social-Communication / Autism Screen",
    needs_medicaid: bool = True,
    needs_bilingual: bool = True,
    has_household_vehicle: bool = False,
) -> dict[str, Any]:
    """Generates the complete 45-Day Pathway & Bottleneck Brief in a single call.

    Combines:
      - Multi-hop `<=45`-day compliant pathway routing + cautionary 4-hop bounce trace
      - Regional multi-hop network breach audit + #1 hidden Bounce Hub diagnosis
      - Counterfactual single-hub intervention simulation (`paper_fax` -> `ehr_electronic_portal`)
      - Post-output Equity Audit (`audit_*` demographic shares + zero-vehicle analysis + NSCH context)
      - Community screening priority tracts (Track 3)
      - Plain-language English & Spanish Caregiver Action Notes
    """
    routing = find_compliant_45d_pathways(
        child_tract_geoid=child_tract_geoid,
        child_age_months=child_age_months,
        concern_domain=concern_domain,
        needs_medicaid=needs_medicaid,
        needs_bilingual=needs_bilingual,
        has_household_vehicle=has_household_vehicle,
    )
    viable_45d_paths = find_viable_45d_paths(
        zip_or_tract=child_tract_geoid,
        languages="Spanish" if needs_bilingual else "English",
        insurance="Medicaid" if needs_medicaid else "Commercial",
        specialty=concern_domain,
        child_age_months=child_age_months,
        has_household_vehicle=has_household_vehicle,
    )
    audit = audit_multihop_bounce_hubs(only_breaches=True, limit_chains=6)
    bottleneck_hubs = detect_regional_bottleneck_hubs(region="ALL", max_days=45, top_n=5)
    top_hub_id = (
        audit["top_hidden_bounce_hub"]["provider_id"]
        if audit.get("top_hidden_bounce_hub")
        else ""
    )
    simulation = simulate_hub_intervention(
        target_provider_id=top_hub_id,
        upgrade_fax_to_ehr=True,
        precheck_bilingual_and_slot_capacity=True,
    )
    equity = run_post_output_equity_audit()
    outreach = prioritize_community_screening_tracts(top_n=5)
    outreach_zones = rank_outreach_zones(
        needs_medicaid=needs_medicaid,
        needs_bilingual=needs_bilingual,
        top_n=6,
    )
    agencies = lookup_regional_agency_kpis()
    caregiver_notes = build_caregiver_notes(routing)

    return {
        "state_code": routing["child_profile"]["state_code"],
        "execution_engine": routing["execution_engine"],
        "agencies": agencies["agencies"],
        "routing": routing,
        "viable_45d_paths": viable_45d_paths,
        "network_audit": audit,
        "bottleneck_hubs": bottleneck_hubs,
        "counterfactual_simulation": simulation,
        "equity_audit": equity,
        "screening_outreach": outreach,
        "outreach_zones": outreach_zones,
        "caregiver_notes": caregiver_notes,
    }
