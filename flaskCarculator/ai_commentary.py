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

PROMPT_TMPL_COMPACT = """
Vehicles (id → {{indicator, total,
  attrs:{{capacity_utilization, target_range_km, electricity_consumption_kwh_per_100km, fuel_consumption_l_per_100km, electricity_type, hydrogen_type, powertrain, top_stages}},
  feats:{{capacity_utilization_label, energy_intensity_kwh_per_km}}}}):
{veh_payload}

Rules:
- Internally sort by TOTAL (ascending = best) to orient your narrative. DO NOT output a ranking list.
- Treat vehicles with |Δ total| < {close_band} as "effectively similar".
- Summary (≤180 words):
    - First sentence: explicitly state BEST (lowest total) and WORST (highest total) with ids and totals.
    - Bring context with capacity utilization (use capacity_utilization_label if present) and target_range_km.
    - Use energy context: electricity_type / hydrogen_type / fuel_consumption_l_per_100km / electricity_consumption_kwh_per_100km to explain differences.
    - Where helpful, cite top_stages (e.g., "road", "energy chain") to ground the reasoning.
    - Keep factual; no normalization or invented units. Round numbers sensibly (e.g., totals to 3 decimals; ranges as whole km).
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
        "top_stages",  # NEW
    }
    KEEP_FEATS = {
        "capacity_utilization",
        "capacity_utilization_label",
        "energy_intensity_kwh_per_km",
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
    vcount = max(1, len(slim_payload))
    max_tok = 500 if vcount <= 3 else 700
    payload_str = json.dumps(slim_payload, ensure_ascii=False, separators=(",", ":"))

    result = _call_openai(...)
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


