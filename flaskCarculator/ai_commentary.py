# ai_commentary.py
import math
from openai import OpenAI
from httpx import Timeout
import os, json

OPENAI_MODEL = os.getenv("HOSTED_MODEL", "gpt-4o-mini")
OPENAI_API_KEY = os.getenv("HOSTED_API_KEY")


LANG_NAMES = {"en":"English","fr":"French","de":"German","it":"Italian"}


# Put near the top
DETAIL_CONFIG = {
    "compact":   {"word_limit": 140, "max_tokens": 320,  "include_appendix": False},
    "standard":  {"word_limit": 320, "max_tokens": 900,  "include_appendix": True},
    "deep":      {"word_limit": 600, "max_tokens": 1600, "include_appendix": True},
    "narrative": {"word_limit": 600, "max_tokens": 1600, "include_appendix": False},
}
# Compact prompt (shorter output = faster)
# ai_commentary.py

FU_NAME_MAP = {"tkm": "ton-kilometer", "vkm": "vehicle-kilometer"}

def _resolve_fu_from_payload(slim_payload: dict, fallback="vkm"):
    counts = {"vkm": 0, "tkm": 0}
    for _, d in slim_payload.items():
        fu = (d.get("attrs", {}).get("func_unit") or "").lower()
        if fu in counts:
            counts[fu] += 1
    chosen = max(counts, key=counts.get) if any(counts.values()) else fallback
    mixed = (sum(1 for v in counts.values() if v > 0) > 1)
    return chosen, mixed


COST_POLICY = """
Cost payload semantics (authoritative):
- The "cost" block contains CHF per functional unit (FU) for each vehicle.
- "total" is the total cost per FU; "components" is a per-FU breakdown (e.g., energy cost, purchase amortisation, maintenance, tolls, canton road charge).
- When you mention costs, always state: value + "CHF per {fu_code}".
- Be concise: one sentence comparing cost-best vs cost-worst and naming the top cost driver for each.
- Do NOT invent missing values; only use provided numbers.
"""


# COMPACT template: output only summary
PROMPT_TMPL_COMPACT = """
Vehicles (id → {{indicator, total, total_2dp,
  attrs:{{capacity_utilization, target_range_km, electricity_consumption_kwh_per_100km, fuel_consumption_l_per_100km, electricity_type, hydrogen_type, powertrain, top_stages, func_unit, curb_mass_kg, driving_mass_kg, gross_mass_kg}},
  feats:{{energy_intensity_kwh_per_km, ttw_energy_mj_per_fu, available_payload_kg, battery_energy_kwh, power_kw, power_to_mass_kw_per_t, battery_specific_energy_kwh_per_t_vehicle, mass_fraction_curb_vs_gross}},
  cost:{{currency, per_fu, total, components}},
  stage_shares_pct:{{... optional ...}}}}):
{veh_payload}

{cost_policy}

Rules (follow exactly):
- Use numbers from "Authoritative numeric facts" verbatim; do not re-derive.
- Sort internally by TOTAL (ascending) to orient your narrative; do NOT output a ranking list.
- Treat vehicles with |Δ total| < {close_band} as "effectively similar".
- Stage naming: "energy chain" = upstream energy supply chain (production + delivery); "road" must be called "road infrastructure construction & upkeep (embodied)".
- Payload policy: use feats["available_payload_kg"] (gross − curb) to discuss carrying capacity; **do not** discuss "capacity utilization" in the summary.
- Cost sentence: include only if ≥2 vehicles have numeric cost totals; name top 1–2 cost drivers from the provided components.
- Tank-to-wheel energy sentence: include only if any vehicle has feats["ttw_energy_mj_per_fu"].
- Battery & masses: mention battery_energy_kwh, curb/driving/gross mass, mass_fraction_curb_vs_gross, and power_to_mass_kw_per_t when they help explain differences.
- Stage drivers: use attrs["top_stages"] and any stage_shares_pct if present; tie them to observed differences.
- Never write "null" or "unknown" in the summary; omit that sentence instead.
- 4–6 short paragraphs covering: (1) GHG magnitudes (best/worst with total_2dp, kgCO2-eq per {fu_code}); (2) costs with drivers (CHF per {fu_code}); (3) energy & efficiency (MJ per {fu_code}, energy_intensity_kwh_per_km, power_to_mass); (4) payload & battery/masses (available payload, battery size, curb/gross); (5) stage drivers.
- Range sentence (MANDATORY): Compare the longest- and shortest-range vehicles using display values (target_range_km_int, in km). Mention each vehicle’s range at least once.

Coverage policy:
- There are {veh_count} vehicles. Mention every vehicle at least once by label.
- Include one compact line enumerating all vehicles with their GHG and cost, e.g.:
  Vehicle 1: 0.02 kgCO2-eq/{fu_code}, 0.05 CHF/{fu_code}; Vehicle 2: ...

Formatting policy (mandatory):
- Always refer to vehicles using the Name map (e.g., "Vehicle 1"), never the internal ids.
- Use numbers from Display facts verbatim:
  • Tank-to-wheel energy: 2 decimals (MJ per {fu_code})
  • Cost per {fu_code}: 2 decimals (CHF per {fu_code})
  • Battery size (kWh): integer
  • Available payload (kg): integer
  • Total GHG: use total_2dp as given (kgCO2-eq per {fu_code})

Name map (id → label; use labels in the text):
{name_map}

Display facts (rounded; quote these numbers exactly):
{display_facts}

Return ONLY this JSON:
{{
  "summary": "text"
}}
"""


PROMPT_TMPL_STANDARD = PROMPT_TMPL_COMPACT.replace(
    "Summary (≤{word_limit} words):",
    "Summary (≤{word_limit} words):"
).replace(
    'Output policy:\n- Output only JSON with keys: "summary" and "capacity_and_range".',
    'Output policy:\n- Output only JSON with keys: "summary", "capacity_and_range", and (optionally) "appendix".'
)


def _is_finite_number(x) -> bool:
    try:
        return isinstance(x, (int, float)) and math.isfinite(float(x))
    except Exception:
        return False

def _sanitize_numbers(obj):
    """Recursively replace non-finite numbers with None and drop empty dicts."""
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            sv = _sanitize_numbers(v)
            # Optionally drop None-only components if desired
            out[k] = sv
        return out
    elif isinstance(obj, list):
        return [_sanitize_numbers(v) for v in obj]
    elif isinstance(obj, (int, float)):
        return float(obj) if _is_finite_number(obj) else None
    return obj

def _extract_json(text: str) -> dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        s, e = text.find("{"), text.rfind("}")
        if s >= 0 and e >= 0:
            try: return json.loads(text[s:e+1])
            except Exception: pass
        return {}

def _top_cost_drivers(components: dict, n=2):
    if not components:
        return []
    pairs = []
    for k, v in components.items():
        try:
            pairs.append((k, float(v)))
        except Exception:
            pass
    pairs.sort(key=lambda kv: kv[1], reverse=True)
    return [k for k, _ in pairs[:n]]


def _build_facts_table(slim_payload: dict, fu_code: str):
    def r2(x):
        try: return round(float(x), 2)
        except Exception: return None
    def r0(x):
        try: return int(round(float(x)))
        except Exception: return None

    name_map = {vid: f"Vehicle {i}" for i, vid in enumerate(slim_payload.keys(), start=1)}

    rows = []
    for vid, d in slim_payload.items():
        feats = d.get("feats") or {}
        attrs = d.get("attrs") or {}
        cost  = d.get("cost")  or {}

        raw_total_2dp = d.get("total_2dp")
        raw_ttw_mj    = feats.get("ttw_energy_mj_per_fu")
        raw_ei_kwhkm  = feats.get("energy_intensity_kwh_per_km")
        raw_payload   = feats.get("available_payload_kg")
        raw_batt_kwh  = feats.get("battery_energy_kwh")
        raw_cost_fu   = cost.get("total")
        raw_range_km  = attrs.get("target_range_km")  # ← NEW

        disp = {
            f"total_kgco2e_per_{fu_code}": raw_total_2dp,
            f"ttw_mj_per_{fu_code}_2dp": r2(raw_ttw_mj),
            "energy_intensity_kwh_per_km_2dp": r2(raw_ei_kwhkm),
            "available_payload_kg_int": r0(raw_payload),
            "battery_energy_kwh_int": r0(raw_batt_kwh),
            f"cost_chf_per_{fu_code}_2dp": r2(raw_cost_fu),
            "cost_total_chf_int": r0(raw_cost_fu),
            "target_range_km_int": r0(raw_range_km),
        }

        rows.append({
            "id": vid,
            "label": name_map[vid],
            f"total_kgco2e_per_{fu_code}": raw_total_2dp,
            f"ttw_mj_per_{fu_code}": raw_ttw_mj,
            "energy_intensity_kwh_per_km": raw_ei_kwhkm,
            "available_payload_kg": raw_payload,
            "battery_energy_kwh": raw_batt_kwh,
            f"cost_chf_per_{fu_code}": raw_cost_fu,
            "top_cost_drivers": _top_cost_drivers((cost or {}).get("components") or {}, 2),
            "power_kw": feats.get("power_kw"),
            "power_to_mass_kw_per_t": feats.get("power_to_mass_kw_per_t"),
            "mass_fraction_curb_vs_gross": feats.get("mass_fraction_curb_vs_gross"),
            "curb_mass_kg": attrs.get("curb_mass_kg"),
            "driving_mass_kg": attrs.get("driving_mass_kg"),
            "gross_mass_kg": attrs.get("gross_mass_kg"),
            "powertrain": attrs.get("powertrain"),
            "size": attrs.get("size"),
            "top_stages": attrs.get("top_stages"),
            "target_range_km": raw_range_km,
            "display": disp,
        })


    # Orientation by total (use labels too)
    key = f"total_kgco2e_per_{fu_code}"
    with_tot = [r for r in rows if isinstance(r.get(key), (int, float))]
    with_tot.sort(key=lambda r: r[key])

    orient = {}
    if with_tot:
        orient = {
            "best_id": with_tot[0]["id"],
            "best_label": with_tot[0]["label"],            # NEW
            "best_total": with_tot[0][key],
            "worst_id": with_tot[-1]["id"],
            "worst_label": with_tot[-1]["label"],          # NEW
            "worst_total": with_tot[-1][key],
        }

    return {"per_vehicle": rows, "orientation": orient, "name_map": name_map}


_OPENAI_CLIENT = None

def _get_openai_client():
    global _OPENAI_CLIENT
    if not OPENAI_API_KEY:
        raise RuntimeError("OpenAI API key not configured")
    if _OPENAI_CLIENT is None:
        _OPENAI_CLIENT = OpenAI(
            api_key=OPENAI_API_KEY,
            timeout=Timeout(connect=10.0, read=60.0, write=20.0, pool=5.0),
            max_retries=0,
        )
    return _OPENAI_CLIENT

def _call_openai(*, system, prompt, max_tokens, temp=0.0, timeout_s):
    # in _call_openai
    def _valid(data: dict) -> bool:
        return isinstance(data, dict) and isinstance(data.get("summary"), str) and data["summary"].strip() != ""

    try:
        client = _get_openai_client()
    except Exception as e:
        return {"_error": f"ClientInitError: {e}"}

    max_tokens = int(max_tokens or 300)
    max_tokens = max(220, min(max_tokens, 1200))

    try:
        r = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=float(temp) if temp is not None else 0.0,
            max_tokens=max_tokens,
            timeout=float(timeout_s),
            n=1,
        )
        data = _extract_json((r.choices[0].message.content or "").strip())
        if _valid(data):
            return data
        return {"_error": "Model returned invalid/empty JSON."}
    except Exception as e:
        return {"_error": f"{type(e).__name__}: {e}"}


def _pick_lang(language: str) -> str:
    lang = (language or "en").lower()
    return lang if lang in LANG_NAMES else "en"

def _filter_essentials(veh_payload: dict) -> dict:
    KEEP_ATTRS = {
        "capacity_utilization",  # kept but NOT discussed in prose
        "target_range_km",
        "electricity_consumption_kwh_per_100km",
        "fuel_consumption_l_per_100km",
        "electricity_type",
        "hydrogen_type",
        "powertrain",
        "top_stages",
        "func_unit",
        # NEW: masses
        "curb_mass_kg", "driving_mass_kg", "gross_mass_kg",
    }
    KEEP_FEATS = {
        "energy_intensity_kwh_per_km",
        "ttw_energy_mj_per_fu",
        "available_payload_kg",
        # NEW: battery & power metrics
        "battery_energy_kwh",
        "power_kw",
        "power_to_mass_kw_per_t",
        "battery_specific_energy_kwh_per_t_vehicle",
        "mass_fraction_curb_vs_gross",
    }
    slim = {}
    for vid, d in veh_payload.items():
        slim[vid] = {
            "indicator": d.get("indicator"),
            "total": d.get("total"),
            "attrs": {k: d.get("attrs", {}).get(k) for k in KEEP_ATTRS if k in d.get("attrs", {})},
            "feats": {k: d.get("feats", {}).get(k) for k in KEEP_FEATS if k in d.get("feats", {})},
        }
        if "cost" in d:
            slim[vid]["cost"] = d["cost"]
        if "stage_shares_pct" in d:
            slim[vid]["stage_shares_pct"] = d["stage_shares_pct"]
    return slim



def _round_or_none(x, nd=3):
    try:
        return round(float(x), nd)
    except Exception:
        return None

def ai_compare_across_vehicles_swisscargo(
    veh_payload: dict,
    language="en",
    detail="compact",
    timeout_s=10.0,
    remaining_before_ai_s: float | None = None,   # ← NEW
) -> dict:
    if not veh_payload or not isinstance(veh_payload, dict):
        return {"language": "en", "summary": "No vehicles to compare."}

    N = len(veh_payload) if isinstance(veh_payload, dict) else 0

    # Derive API budget from remaining time when available
    if remaining_before_ai_s and remaining_before_ai_s > 6.0:
        # keep 2s safety margin, cap at 20s
        api_budget = min(max(6.0, remaining_before_ai_s - 2.0), 20.0)
    else:
        budget = float(timeout_s) if timeout_s and timeout_s > 0 else 8.0
        api_budget = max(4.0, min(budget - 0.2, 12.0))

    # NEW: nudge budget for larger N (but never exceed 20s, or remaining time)
    if N >= 5:
        api_budget = min(api_budget + 2.0 + 0.8 * (N - 4), 20.0)

    if api_budget >= 10.0:
        detail = "deep"
    elif api_budget >= 7.0:
        detail = "standard"
    else:
        detail = "compact"

    cfg = DETAIL_CONFIG[detail].copy()

    lang = _pick_lang(language)

    system = (
        f"You are an LCA assistant. Respond in {LANG_NAMES[lang]}. "
        "Use only provided numbers. Output strict JSON. "
        "Do not conflate capacity utilization with mechanical efficiency. "
        "When reporting costs, use CHF per FU exactly as provided."
    )

    slim_payload = _filter_essentials(veh_payload)
    for vid, d in slim_payload.items():
        raw_total = d.get("total")
        # Keep both: precise total and rounded 2dp for display
        d["total"] = _round_or_none(raw_total, nd=6)
        d["total_2dp"] = _round_or_none(raw_total, nd=2)

        d["attrs"] = {k: v for k, v in d.get("attrs", {}).items() if v not in (None, "", [], {})}
        d["feats"] = {k: v for k, v in d.get("feats", {}).items() if v not in (None, "", [], {})}

        if "cost" in d:
            c = d["cost"]
            keep = {"currency": c.get("currency"), "total": c.get("total"), "per_fu": c.get("per_fu")}
            comps = c.get("components") or {}
            if c.get("shares_pct"):
                top2 = sorted(c["shares_pct"].items(), key=lambda it: it[1], reverse=True)[:2]
                keep["components"] = {k: comps.get(k) for k, _ in top2 if k in comps}
            else:
                keep["components"] = comps
            d["cost"] = keep

    fu_code, _ = _resolve_fu_from_payload(slim_payload, fallback="vkm")
    fu_label = FU_NAME_MAP.get(fu_code, "vehicle-kilometer")

    # Keep payload compact; avoid pretty printing and ASCII escaping

    facts = _build_facts_table(slim_payload, fu_code)
    facts_str = json.dumps(facts, separators=(",", ":"), allow_nan=False)

    sanitized_payload = _sanitize_numbers(slim_payload)
    payload_str = json.dumps(
        sanitized_payload,
        ensure_ascii=True,  # keep it plain ASCII
        separators=(",", ":"),
        allow_nan=False  # hard fail if NaN/Inf slipped through
    )
    # choose template based on detail
    tmpl = PROMPT_TMPL_COMPACT if detail == "compact" else PROMPT_TMPL_STANDARD

    name_map_str = json.dumps(facts["name_map"], separators=(",", ":"), ensure_ascii=True)
    display_facts_str = json.dumps(facts["per_vehicle"], separators=(",", ":"), allow_nan=False, ensure_ascii=True)
    veh_count = len(slim_payload)

    prompt = tmpl.format(
        veh_payload=payload_str,
        close_band=0.02,
        stage_glossary="",
        capacity_utilization_note="",
        cost_policy=COST_POLICY.strip(),
        word_limit=cfg["word_limit"],
        fu_code=fu_code,
        name_map=name_map_str,
        display_facts=display_facts_str,
        veh_count=veh_count,
    ) + f"""
        Authoritative numeric facts (use these numbers verbatim; do not re-derive):
        {facts_str}
        Functional unit (FU): "{fu_label}" (code: {fu_code}).
        If units are mixed across vehicles, briefly note that and avoid cross-unit comparisons.

        Energy reporting policy:
        - Prefer feats["ttw_energy_mj_per_fu"] and report as MJ per {fu_code}.
        - Do NOT mention liters or kWh unless MJ is unavailable.

        Totals display policy:
        - When citing totals, display "total_2dp" with "kgCO2-eq" per {fu_label} ({fu_code}).
        - Use the phrase "tank-to-wheel energy", not "ttw energy".
    """

    try:
        # IMPORTANT: do NOT inflate timeout here; pass the budget through.
        # Ensure your _call_openai() applies (connect_timeout, read_timeout) = (3.05, api_budget)
        # if using requests; or client timeout=api_budget if using an SDK.
        result = _call_openai(
            system=system,
            prompt=prompt,
            max_tokens=cfg["max_tokens"],
            temp=0.2,
            timeout_s=api_budget,  # respect caller budget
            # If you control _call_openai, also set max_retries=0–1 to avoid surprise delays.
        )

        if not result:
            return {"language": lang, "summary": "Empty response from AI."}
        if result.get("_error"):
            return {"language": lang, "summary": f"AI error: {result['_error']}"}


    except Exception as e:
        return {"language": lang, "summary": f"AI error: {e}"}

    if not result:
        return {"language": lang, "summary": f"AI error: {result.get('_error')}"}

    if result.get("_error"):
        return {"language": lang, "summary": f"AI error: {result['_error']}"}

    summary_text = (result.get("summary") or "").strip()
    return {"language": lang, "summary": summary_text}



