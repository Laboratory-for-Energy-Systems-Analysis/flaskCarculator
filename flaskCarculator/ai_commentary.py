# ai_compare.py
import os, json, time
from openai import OpenAI

OPENAI_MODEL = os.getenv("HOSTED_MODEL", "gpt-4o-mini")
OPENAI_API_KEY = os.getenv("HOSTED_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

LANG_NAMES = {"en":"English","fr":"French","de":"German","it":"Italian"}

SYSTEM_TMPL = """You are an LCA assistant for trucks.
Compare vehicles using absolute totals for the *same indicator* ("climate change").
- Do NOT normalize; use provided totals and stage contributions as-is.
- Identify best and worst vehicles and the absolute range.
- Mention concrete absolute differences first (percentages optional).
- Consider provided attributes (e.g., powertrain, energy stored, consumption, mass, efficiency) to explain *why*.
- Keep <=140 words total.
- Respond in {lang_name}.
Return ONLY JSON with keys: summary, ranking, spread, drivers."""

PROMPT_TMPL = """
Vehicles (ID → indicator totals, stage breakdown, attributes):
{veh_payload}

Rules:
- Treat "total" as the sum of stage values (already computed).
- Do not assume units if not provided; quote numbers plainly (e.g., 0.48).
- Use attributes only for qualitative explanation (e.g., higher battery → heavier → higher road/energy chain).

Output JSON schema:
{{
  "summary": "one concise paragraph comparing all vehicles",
  "ranking": [{{"id":"...","total": number}}],  // ascending by total (best first)
  "spread": {{
     "best_id":"...","best_total":number,
     "worst_id":"...","worst_total":number,
     "range_abs":number
  }},
  "drivers": [{{"id":"...","note":"one sentence on likely driver(s)"}}]
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
        return {"summary":"","ranking":[],"spread":{},"drivers":[]}

def _call_openai(system: str, prompt: str, max_tokens=450, temp=0.2) -> dict:
    last = None
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
        except Exception as e:
            last = e; time.sleep(0.6*(i+1))
    return {"summary":"","ranking":[],"spread":{},"drivers":[]}

def _pick_lang(language: str) -> str:
    lang = (language or "en").lower()
    return lang if lang in LANG_NAMES else "en"

def ai_compare_across_vehicles_swisscargo(veh_payload: dict, language="en") -> dict:
    """
    veh_payload structure (already computed by extractor):
      {
        "BEEV001": {
          "indicator": "climate change",
          "total": 0.482,                # absolute total (sum of stages)
          "stages": {"energy chain": 0.17545, "road": 0.1588, ...},
          "attrs":  {"powertrain":"BEV","electric energy stored":725.0, ...}
        }, ...
      }
    """
    lang = _pick_lang(language)
    system = SYSTEM_TMPL.format(lang_name=LANG_NAMES[lang])
    prompt = PROMPT_TMPL.format(veh_payload=veh_payload)

    if client is None:
        # Deterministic fallback: sort by total, compute spread, add brief notes
        items = [(vid, d.get("total", float("inf"))) for vid, d in veh_payload.items()]
        items = [i for i in items if i[1] is not None]
        items.sort(key=lambda x: x[1])
        ranking = [{"id": vid, "total": val} for vid, val in items]
        spread = {}
        if ranking:
            best = ranking[0]; worst = ranking[-1]
            spread = {"best_id": best["id"], "best_total": best["total"],
                      "worst_id": worst["id"], "worst_total": worst["total"],
                      "range_abs": abs(worst["total"] - best["total"])}
        drivers = []
        for vid, _ in items[:3]:
            attrs = veh_payload[vid].get("attrs", {})
            note_bits = []
            if attrs.get("powertrain"): note_bits.append(attrs["powertrain"])
            if attrs.get("electric energy stored"): note_bits.append(f'bat {attrs["electric energy stored"]}')
            if attrs.get("electricity consumption"): note_bits.append(f'kWh/100km {attrs["electricity consumption"]}')
            if attrs.get("electricity"): note_bits.append(f'electricity type: {attrs["electricity"]}')
            if attrs.get("fuel consumption"): note_bits.append(f'liters/100km {attrs["fuel consumption"]}')
            if attrs.get("curb mass"): note_bits.append(f'curb {round(attrs["curb mass"]) }')
            if attrs.get("target range"): note_bits.append(f'range autonomy {round(attrs["target range"]) } km')
            drivers.append({"id": vid, "note": ", ".join(map(str, note_bits)) or "n/a"})
        return {"language": lang, "comparison": {"summary": "Deterministic comparison (no API key).",
                                                 "ranking": ranking, "spread": spread, "drivers": drivers}}
    return {"language": lang, "comparison": _call_openai(system, prompt)}
