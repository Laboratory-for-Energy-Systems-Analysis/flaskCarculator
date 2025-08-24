# ai_compare.py (replace the previous content if you like)
import os, json, time
from openai import OpenAI

OPENAI_MODEL = os.getenv("HOSTED_MODEL", "gpt-4o-mini")
OPENAI_API_KEY = os.getenv("HOSTED_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

LANG_NAMES = {"en":"English","fr":"French","de":"German","it":"Italian"}

SYSTEM_TMPL = """You are an LCA assistant for trucks.
Compare vehicles on absolute totals for the same indicator ("climate change").
Use provided stage totals, raw attributes (attrs), and derived features (feats).
- No normalization across vehicles.
- Prefer concrete absolute differences first; percentages optional.
- Keep reasoning short but specific.
- Respond in {lang_name}.
Return ONLY JSON with keys: summary, ranking, spread, drivers, recommendations."""

PROMPT_TMPL = """
Vehicles (id → {{indicator, total, stages, stage_shares_pct?, attrs, feats}}):
{veh_payload}

Instructions:
- Rank vehicles by TOTAL (ascending = best).
- Quantify spread: best, worst, absolute range (worst - best).
- Explain "drivers" concisely, tying stages to plausible attributes/features:
  e.g., higher energy chain ↔ higher electricity consumption or lower TTW efficiency;
        higher road ↔ heavier curb/driving mass or lower payload utilization.
- If two vehicles are close (|Δ| < {close_threshold}), note they are similar.

For each vehicle, give 1–2 targeted "recommendations" grounded in attrs/feats
(e.g., reduce kWh/100km via aero/tires; optimize route/payload; lighter spec if feasible).

Output JSON schema:
{{
  "summary": "≤160 words",
  "ranking": [{{"id":"...","total": number}}],
  "spread": {{"best_id":"...","best_total":number,"worst_id":"...","worst_total":number,"range_abs":number}},
  "drivers": [{{"id":"...","note":"one sentence citing attributes/features and stages"}}],
  "recommendations": [{{"id":"...","actions":["...","..."]}}]
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
        return {"summary":"","ranking":[],"spread":{},"drivers":[],"recommendations":[]}

def _call_openai(system: str, prompt: str, max_tokens=650, temp=0.2) -> dict:
    for i in range(3):
        try:
            resp = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[{"role":"system","content":system},
                          {"role":"user","content":prompt}],
                temperature=temp,
                max_tokens=max_tokens,
                response_format={"type":"json_object"},
            )
            return _extract_json(resp.choices[0].message.content)
        except Exception:
            time.sleep(0.6*(i+1))
    return {"summary":"","ranking":[],"spread":{},"drivers":[],"recommendations":[]}

def _pick_lang(language: str) -> str:
    lang = (language or "en").lower()
    return lang if lang in LANG_NAMES else "en"

def ai_compare_across_vehicles_swisscargo(veh_payload: dict, language="en", detail="detailed") -> dict:
    """
    veh_payload: dict from build_compare_payload_swisscargo()
    """
    lang = _pick_lang(language)
    system = SYSTEM_TMPL.format(lang_name=LANG_NAMES[lang])
    prompt = PROMPT_TMPL.format(veh_payload=veh_payload, close_threshold=0.02)  # tweak threshold to your units/scale
    if client is None:
        # deterministic fallback (no API key)
        items = sorted(((vid, d.get("total", float("inf"))) for vid, d in veh_payload.items()), key=lambda x: x[1])
        ranking = [{"id": vid, "total": tot} for vid, tot in items]
        spread = {}
        if ranking:
            best, worst = ranking[0], ranking[-1]
            spread = {"best_id": best["id"], "best_total": best["total"],
                      "worst_id": worst["id"], "worst_total": worst["total"],
                      "range_abs": worst["total"] - best["total"]}
        drivers = []
        for vid, _ in items[:3]:
            d = veh_payload[vid]
            feats = d.get("feats", {})
            notes = []
            if feats.get("energy_intensity_kwh_per_km"): notes.append(f'energy/km={round(feats["energy_intensity_kwh_per_km"],3)}')
            if feats.get("mass_fraction_curb_vs_gross"): notes.append(f'mass_frac={round(feats["mass_fraction_curb_vs_gross"],2)}')
            if feats.get("power_to_mass_kw_per_t"): notes.append(f'P/M={round(feats["power_to_mass_kw_per_t"],2)}')
            drivers.append({"id": vid, "note": ", ".join(notes) or "n/a"})
        recs = [{"id": vid, "actions": ["Optimize routing/payload", "Reduce energy intensity"]} for vid, _ in items[:3]]
        return {"language": lang, "comparison": {"summary": "Deterministic comparison (no API key).",
                                                 "ranking": ranking, "spread": spread,
                                                 "drivers": drivers, "recommendations": recs}}
    return {"language": lang, "comparison": _call_openai(system, prompt)}
