# ai_commentary.py
import os, json, time as _t
from openai import OpenAI

OPENAI_MODEL = os.getenv("HOSTED_MODEL", "gpt-4o-mini")
OPENAI_API_KEY = os.getenv("HOSTED_API_KEY")
# Set a short client-level timeout default; you can override per call
client = OpenAI(api_key=OPENAI_API_KEY, timeout=10.0) if OPENAI_API_KEY else None

LANG_NAMES = {"en":"English","fr":"French","de":"German","it":"Italian"}


# Put near the top
DETAIL_CONFIG = {
    "compact":   {"word_limit": 180, "max_tokens": 700,  "include_appendix": False},
    "standard":  {"word_limit": 300, "max_tokens": 1000, "include_appendix": True},
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

# Add near the top, after FU_NAME_MAP
STAGE_GLOSSARY = """
Stage glossary (authoritative definitions; follow strictly):
- "road": Embodied greenhouse-gas emissions from constructing and maintaining the road infrastructure used by the trucks.
  This is NOT tailpipe/driving emissions.
- "energy chain": Upstream greenhouse-gas emissions from producing and supplying the energy carrier
  (e.g., refining and distributing diesel, generating and delivering electricity, producing and compressing/transporting hydrogen).
"""

CAPACITY_UTILIZATION_NOTE = """
Capacity utilization policy (authoritative):
- "capacity utilization" is the logistics load factor: the fraction of total carrying capacity that is actually used.
- It reflects fleet/operations planning (how full the trucks run), not mechanical/engine efficiency or drivetrain performance.
- Do NOT equate capacity utilization with efficiency; treat it as a demand allocation factor over the functional unit.
"""

COST_POLICY = """
Cost payload semantics (authoritative):
- The "cost" block contains CHF per functional unit (FU) for each vehicle.
- "total" is the total cost per FU; "components" is a per-FU breakdown (e.g., energy cost, purchase amortisation, maintenance, tolls, canton road charge).
- When you mention costs, always state: value + "CHF per {fu_code}".
- Be concise: one sentence comparing cost-best vs cost-worst and naming the top cost driver for each.
- Do NOT invent missing values; only use provided numbers.
"""

APPENDIX_JSON_CLAUSE = """,
  "appendix": {{
    "cost_overview": [
      {{"id":"...","total_chf_per_{fu_code}": number|null,"top_cost_drivers": ["energy cost","amortised purchase", "..."]}}
    ],
    "stage_breakdown": [
      {{"id":"...","top_stages":["energy chain","road infrastructure (embodied)"],"stage_shares_pct": {{ "energy chain": number, "road": number }} }}
    ],
    "per_vehicle": [
      {{"id":"...","ghg_total_kgco2e_per_{fu_code}": number,"tank_to_wheel_mj_per_{fu_code}": number|null,"capacity_utilization_pct": number|null,"note":"≤18 words"}}
    ],
    "notes": ["short bullet 1","short bullet 2"]
  }}"""

# Replace your PROMPT_TMPL_COMPACT with this (only the tail is new)
PROMPT_TMPL_COMPACT = """
Vehicles (id → {{indicator, total, total_2dp,
  attrs:{{capacity_utilization, target_range_km, electricity_consumption_kwh_per_100km, fuel_consumption_l_per_100km, electricity_type, hydrogen_type, powertrain, top_stages, func_unit}},
  feats:{{capacity_utilization_label, energy_intensity_kwh_per_km, ttw_energy_mj_per_fu}},
  cost:{{currency, per_fu, total, components, shares_pct}},
  stage_shares_pct:{{... optional ...}}}}):
{veh_payload}

{stage_glossary}
{capacity_utilization_note}
{cost_policy}

Rules:
- Internally sort by TOTAL (ascending = best) to orient your narrative. DO NOT output a ranking list.
- Treat vehicles with |Δ total| < {close_band} as "effectively similar".
- When referencing stages in attrs["top_stages"]:
    - If you mention "road", explicitly call it "road infrastructure construction & upkeep (embodied)".
    - "energy chain" must be described as the upstream energy supply chain (production + delivery) for the relevant carrier.

- Summary (≤{word_limit} words):
    - Open with BEST and WORST by total GHG (use total_2dp, kgCO2-eq per FU).
    - Add ONE concise **cost** sentence: lowest- vs highest-cost vehicles with totals in CHF per {fu_code} and their dominant cost driver(s).
    - Interpret stage drivers: explain what “energy chain” and “road infrastructure construction & upkeep (embodied)” mean and how they shape differences.
    - Discuss **tank-to-wheel energy** in MJ per FU and relate it to results where relevant.
    - Explain **capacity utilization** as a logistics load factor (%, no decimals) and how changes (e.g., ±10 percentage points) would qualitatively shift per-FU results.
    - Note any mixed functional units (if detected) and avoid cross-unit comparisons.
    - Keep factual; round totals to 2 decimals; ranges whole km; MJ/FU to 1–2 decimals; costs to 2 decimals.
If additional detail is requested, include an "appendix" object with the sections below. Omit "appendix" entirely if insufficient data.

Appendix spec (only when detailed):
- "cost_overview": per vehicle, total cost and its top 1–2 drivers (use cost.shares_pct or components).
- "stage_breakdown": per vehicle, top stages and stage_shares_pct (if provided).
- "per_vehicle": concise facts per id (GHG total, tank-to-wheel energy, capacity utilization %, short note).
- "notes": short bullet points on assumptions/limits (e.g., mixed FUs, missing costs).

Write the summary as 3–5 short paragraphs: (1) overall ranking & magnitudes, (2) costs, (3) stage drivers, (4) energy & utilization, (5) caveats.

Return ONLY this JSON:
{{
  "summary": "≤{word_limit} words",
  "capacity_and_range": [
    {{"id":"...","capacity_utilization":"low|medium|high|unknown","utilization_value": number|null,"range_km_est": number|null,"note":"≤12 words"}}
  ]{appendix_clause}
}}
"""


def _extract_json(text: str) -> dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        s, e = text.find("{"), text.rfind("}")
        if s >= 0 and e >= 0:
            try: return json.loads(text[s:e+1])
            except Exception: pass
        return {}

def _call_openai(system: str, prompt: str, max_tokens=700, temp=0.2, timeout_s=10.0) -> dict:
    try:
        resp = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role":"system","content":system},{"role":"user","content":prompt}],
            temperature=temp,
            max_tokens=max_tokens,
            response_format={"type":"json_object"},
            timeout=timeout_s,   # <- hard cap
        )
        return _extract_json(resp.choices[0].message.content)
    except Exception as e:
        # propagate the reason so you can see it in the response
        return {"_error": repr(e)}

def _pick_lang(language: str) -> str:
    lang = (language or "en").lower()
    return lang if lang in LANG_NAMES else "en"

def _filter_essentials(veh_payload: dict) -> dict:
    KEEP_ATTRS = {
        "capacity_utilization",
        "target_range_km",
        "electricity_consumption_kwh_per_100km",
        "fuel_consumption_l_per_100km",
        "electricity_type",
        "hydrogen_type",
        "powertrain",
        "top_stages",
        "func_unit",
    }
    KEEP_FEATS = {
        "capacity_utilization",
        "capacity_utilization_label",
        "energy_intensity_kwh_per_km",
        "ttw_energy_mj_per_fu",
    }
    slim = {}
    for vid, d in veh_payload.items():
        slim[vid] = {
            "indicator": d.get("indicator"),
            "total": d.get("total"),
            "attrs": {k: d.get("attrs", {}).get(k) for k in KEEP_ATTRS if k in d.get("attrs", {})},
            "feats": {k: d.get("feats", {}).get(k) for k in KEEP_FEATS if k in d.get("feats", {})},
        }
        # ---- NEW: cost passthrough ----
        if "cost" in d:
            slim[vid]["cost"] = d["cost"]
        # keep stage shares if you find them useful in narration
        if "stage_shares_pct" in d:
            slim[vid]["stage_shares_pct"] = d["stage_shares_pct"]
    return slim



def _round_or_none(x, nd=3):
    try:
        return round(float(x), nd)
    except Exception:
        return None

def _int_or_none(x):
    try:
        return int(round(float(x)))
    except Exception:
        return None


def ai_compare_across_vehicles_swisscargo(veh_payload: dict, language="en", detail="compact", timeout_s=10.0) -> dict:
    cfg = DETAIL_CONFIG.get(detail, DETAIL_CONFIG["compact"])
    lang = _pick_lang(language)
    system = (
        f"You are an LCA assistant. Respond in {LANG_NAMES[lang]}. "
        "Use only provided numbers. Output strict JSON. "
        "Do not conflate capacity utilization with mechanical efficiency. "
        "When reporting costs, use CHF per FU exactly as provided."
    )

    slim_payload = _filter_essentials(veh_payload)
    for vid, d in slim_payload.items():
        d["total_2dp"] = _round_or_none(d.get("total"), nd=2)

    fu_code, fu_mixed = _resolve_fu_from_payload(slim_payload, fallback="vkm")
    fu_label = FU_NAME_MAP.get(fu_code, "vehicle-kilometer")

    payload_str = json.dumps(slim_payload, ensure_ascii=False, separators=(",", ":"))

    appendix_clause = "" if not cfg["include_appendix"] else APPENDIX_JSON_CLAUSE.format(fu_code=fu_code)

    prompt = PROMPT_TMPL_COMPACT.format(
        veh_payload=payload_str,
        close_band=0.02,
        stage_glossary=STAGE_GLOSSARY.strip(),
        capacity_utilization_note=CAPACITY_UTILIZATION_NOTE.strip(),
        cost_policy=COST_POLICY.strip().format(fu_code=fu_code),
        word_limit=cdfg["word_limit"],  # ← make sure spelled correctly
        fu_code=fu_code,
        appendix_clause=appendix_clause,
    ) + f"""
        Functional unit (FU): "{fu_label}" (code: {fu_code}).
        If units are mixed across vehicles, briefly note that and avoid cross-unit comparisons.
        
        Energy reporting policy:
        - Prefer feats["ttw_energy_mj_per_fu"] and report as MJ per {fu_code}.
        - Do NOT mention liters or kWh unless MJ is unavailable.
        
        Totals display policy:
        - When citing totals, display "total_2dp" with "kgCO2-eq" per {fu_label} ({fu_code}).
        - Use the phrase "tank-to-wheel energy", not "ttw energy".
    """

    result = _call_openai(
        system=system,
        prompt=prompt,
        max_tokens=cfg["max_tokens"],
        temp=0.2,
        timeout_s=max(timeout_s, 20.0 if cfg["max_tokens"] > 1000 else timeout_s),
    )

    if result.get("_error") or not result:
        return {"language": lang, "comparison": {"summary": "Time-limited comparison.", "capacity_and_range": []}}

    cleaned = {
        "summary": (result.get("summary") or "").strip(),
        "capacity_and_range": [],
    }
    for item in result.get("capacity_and_range", []):
        cleaned["capacity_and_range"].append({
            "id": item.get("id"),
            "capacity_utilization": item.get("capacity_utilization"),
            "utilization_value": _round_or_none(item.get("utilization_value"), nd=3),
            "range_km_est": _int_or_none(item.get("range_km_est")),
            "note": (item.get("note") or "").strip()[:60],
        })
    # DO NOT pass through 'appendix' at all
    return {"language": lang, "comparison": cleaned}



