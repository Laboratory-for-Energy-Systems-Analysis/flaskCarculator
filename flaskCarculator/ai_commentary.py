# ai_commentary.py
import os, json, time as _t
from openai import OpenAI

OPENAI_MODEL = os.getenv("HOSTED_MODEL", "gpt-4o-mini")
OPENAI_API_KEY = os.getenv("HOSTED_API_KEY")
# Set a short client-level timeout default; you can override per call
client = OpenAI(api_key=OPENAI_API_KEY, timeout=10.0) if OPENAI_API_KEY else None

LANG_NAMES = {"en":"English","fr":"French","de":"German","it":"Italian"}

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

PROMPT_TMPL_COMPACT = """
Vehicles (id → {{indicator, total, total_2dp,
  attrs:{{capacity_utilization, target_range_km, electricity_consumption_kwh_per_100km, fuel_consumption_l_per_100km, electricity_type, hydrogen_type, powertrain, top_stages, func_unit}},
  feats:{{capacity_utilization_label, energy_intensity_kwh_per_km, ttw_energy_mj_per_fu}}}}):
{veh_payload}

Rules:
- Internally sort by TOTAL (ascending = best) to orient your narrative. DO NOT output a ranking list.
- Treat vehicles with |Δ total| < {close_band} as "effectively similar".
- Summary (≤180 words):
    - First sentence: explicitly state BEST (lowest total) and WORST (highest total) with ids and totals,
      displaying totals with 2 decimals using "total_2dp" **and** the unit "kgCO2-eq" and the FU,
      e.g., 0.31 kgCO2-eq per vehicle-kilometer (vkm).
    - Refer to results per the functional unit (e.g., "per vehicle-kilometer (vkm)").
    - **Energy wording:** say **"tank-to-wheel energy"** (not "ttw energy") and report it in **MJ per FU**
      using feats["ttw_energy_mj_per_fu"].
    - **Capacity utilization:** present as percentages with no decimals (e.g., 43%), computed as
      capacity_utilization × 100; still use capacity_utilization_label when relevant.
    - Where helpful, cite top_stages (e.g., "road", "energy chain") to ground the reasoning.
    - Keep factual; no invented units. Round: totals 2 decimals; ranges whole km; MJ/FU to 1–2 decimals.
- Capacity_and_range:
    - For each vehicle: id, capacity_utilization (low|medium|high|unknown + numeric utilization_value if available),
      range_km_est (use target_range_km), note ≤12 words.

Return ONLY this JSON:
{{
  "summary": "≤180 words",
  "capacity_and_range": [
    {{"id":"...","capacity_utilization":"low|medium|high|unknown","utilization_value": number|null,"range_km_est": number|null,"note":"≤12 words"}}
  ]
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
        "func_unit",  # ← NEW
    }
    KEEP_FEATS = {
        "capacity_utilization",
        "capacity_utilization_label",
        "energy_intensity_kwh_per_km",
        "ttw_energy_mj_per_fu",  # ← NEW
    }
    slim = {}
    for vid, d in veh_payload.items():
        slim[vid] = {
            "indicator": d.get("indicator"),
            "total": d.get("total"),
            "attrs": {k: d.get("attrs", {}).get(k) for k in KEEP_ATTRS if k in d.get("attrs", {})},
            "feats": {k: d.get("feats", {}).get(k) for k in KEEP_FEATS if k in d.get("feats", {})},
        }
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
    lang = _pick_lang(language)
    system = f"You are an LCA assistant. Respond in {LANG_NAMES[lang]}. Use only provided numbers. Output strict JSON."

    slim_payload = _filter_essentials(veh_payload)

    # Add 2-decimal display total for narration
    for vid, d in slim_payload.items():
        d["total_2dp"] = _round_or_none(d.get("total"), nd=2)

    # Resolve the functional unit from vehicle attrs (majority wins)
    fu_code, fu_mixed = _resolve_fu_from_payload(slim_payload, fallback="vkm")
    fu_label = FU_NAME_MAP.get(fu_code, "vehicle-kilometer")

    vcount = max(1, len(slim_payload))
    max_tok = 500 if vcount <= 3 else 700
    payload_str = json.dumps(slim_payload, ensure_ascii=False, separators=(",", ":"))

    prompt = PROMPT_TMPL_COMPACT.format(veh_payload=payload_str, close_band=0.02) + f"""

    Functional unit (FU): "{fu_label}" (code: {fu_code}).
    If units are mixed across vehicles, briefly note that and avoid cross-unit comparisons.

    Energy reporting policy:
    - Prefer feats["ttw_energy_mj_per_fu"] and report as MJ per {fu_code}.
    - Do NOT mention liters or kWh unless MJ is unavailable.

    Totals display policy:
    - When citing totals, display "total_2dp" (two decimals) with "kgCO2-eq" and the FU
      (e.g., 0.31 kgCO2-eq per {fu_label} ({fu_code})).
    - Use the phrase "tank-to-wheel energy", not "ttw energy".
    """

    result = _call_openai(
        system=system,
        prompt=prompt,
        max_tokens=max_tok,
        temp=0.2,
        timeout_s=timeout_s
    )

    if result.get("_error") or not result:
        return {"language": lang, "comparison": {"summary": "Time-limited comparison.", "capacity_and_range": []}}

    # sanitize: only keep allowed keys
    for k in ["drivers", "ranking", "spread", "recommendations", "range_headroom_km"]:
        result.pop(k, None)

    # round numbers and ensure target range appears as integer km
    cleaned = {"summary": result.get("summary", "").strip(), "capacity_and_range": []}
    for item in result.get("capacity_and_range", []):
        cleaned["capacity_and_range"].append({
            "id": item.get("id"),
            "capacity_utilization": item.get("capacity_utilization"),
            "utilization_value": _round_or_none(item.get("utilization_value"), nd=3),
            "range_km_est": _int_or_none(item.get("range_km_est")),
            "note": (item.get("note") or "").strip()[:60]
        })

    return {"language": lang, "comparison": cleaned}


