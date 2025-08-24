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
Vehicles (id → {{indicator, total, stages, attrs:{{capacity_utilization, target_range_km}}, feats:{{energy_intensity_kwh_per_km, theoretical_range_km, range_headroom_km, curb_mass_kg, driving_mass_kg}}}}):
{veh_payload}

Rules:
- Rank by TOTAL (ascending = best). Do not convert units.
- Spread: best, worst, absolute range (worst - best).
- "Drivers": ONE short sentence per vehicle (≤20 words), cite ≤2 stages + ≤2 attrs/feats.
- "Capacity_and_range": ONE line per vehicle:
    - capacity_utilization: low|medium|high|unknown + numeric if available
    - range_km_est and range_headroom_km if available; keep note ≤12 words.
- DO NOT include recommendations.

Summary (mandatory, ≤180 words):
- First sentence must correctly name BEST (lowest total) and WORST (highest total) vehicle ids and their totals.
- Then explain how differences in capacity utilization and range autonomy put these totals in perspective.
- Tie to stages where relevant (e.g., higher road ↔ heavier mass; higher energy chain ↔ higher kWh/100 km).
- Keep factual and grounded in provided numbers; no normalization.

Return ONLY this JSON:
{{
  "summary": "≤180 words",
  "ranking": [{{"id":"...","total": number}}],                           
  "spread": {{"best_id":"...","best_total":number,"worst_id":"...","worst_total":number,"range_abs":number}},
  "drivers": [{{"id":"...","note":"≤20 words"}}],                        
  "capacity_and_range": [{{"id":"...","capacity_utilization":"low|medium|high|unknown","utilization_value": number|null,"range_km_est": number|null,"range_headroom_km": number|null,"note":"≤12 words"}}]
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
    """Drop non-essential feats/attrs to cut prompt size."""
    KEEP_FEATS = {
        "capacity_utilization","energy_intensity_kwh_per_km","theoretical_range_km","range_headroom_km",
        "curb_mass_kg","driving_mass_kg","electricity_type","hydrogen_type",
    }
    KEEP_ATTRS = {
        "capacity_utilization","capacity_utilization_label",
        "energy_intensity_kwh_per_km","theoretical_range_km","range_headroom_km",
        "curb_mass_kg","driving_mass_kg"
    }

    slim = {}
    for vid, d in veh_payload.items():
        slim[vid] = {
            "indicator": d.get("indicator"),
            "total": d.get("total"),
            "stages": d.get("stages"),
            "attrs": {k: d.get("attrs", {}).get(k) for k in KEEP_ATTRS if k in d.get("attrs", {})},
            "feats": {k: d.get("feats", {}).get(k) for k in KEEP_FEATS if k in d.get("feats", {})},
        }
    return slim

def ai_compare_across_vehicles_swisscargo(veh_payload: dict, language="en", detail="compact", timeout_s=10.0) -> dict:
    """
    veh_payload: dict from build_compare_payload_swisscargo()
    timeout_s: max seconds to spend in the model call (router limit is 30s total, so keep this small)
    """
    lang = _pick_lang(language)
    system = f"You are an LCA assistant. Respond in {LANG_NAMES[lang]}. Use only provided numbers. Output strict JSON."
    # Trim payload for speed
    slim_payload = _filter_essentials(veh_payload)

    # Adaptive token cap: more vehicles → slightly more tokens
    vcount = max(1, len(slim_payload))
    max_tok = 500 if vcount <= 3 else 700

    payload_str = json.dumps(slim_payload, ensure_ascii=False, separators=(",", ":"))

    result = _call_openai(system, PROMPT_TMPL_COMPACT.format(veh_payload=payload_str),
                          max_tokens=max_tok, temp=0.2, timeout_s=timeout_s)

    if result.get("_error"):
        # return a minimal deterministic result AND the error so you can debug
        items = sorted(((vid, d.get("total", float("inf"))) for vid, d in slim_payload.items()), key=lambda x: x[1])
        ranking = [{"id": vid, "total": tot} for vid, tot in items]
        spread = {}
        if ranking:
            best, worst = ranking[0], ranking[-1]
            spread = {"best_id": best["id"], "best_total": best["total"],
                      "worst_id": worst["id"], "worst_total": worst["total"],
                      "range_abs": (worst["total"] - best["total"]) if isinstance(worst["total"],
                                                                                  (int, float)) and isinstance(
                          best["total"], (int, float)) else None}
        result = {"summary": "Time-limited comparison.", "ranking": ranking, "spread": spread,
                  "drivers": [], "capacity_and_range": [], "recommendations": [], "_error": result["_error"]}
    return {"language": lang, "comparison": result}
