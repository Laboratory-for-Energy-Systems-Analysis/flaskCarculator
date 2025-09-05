# ai_commentary.py
import os, json, time as _t
from openai import OpenAI
from openai import OpenAI
from httpx import Timeout
import os, json

OPENAI_MODEL = os.getenv("HOSTED_MODEL", "gpt-4o-mini")
OPENAI_API_KEY = os.getenv("HOSTED_API_KEY")


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



# Strict output schema via function calling
# ai_commentary.py – add near the top
COMPARE_TOOL = {
    "type": "function",
    "function": {
        "name": "emit_swisscargo_compare",
        "description": "Emit a structured comparison summary for SwissCargo.",
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "required": ["summary", "capacity_and_range"],
            "properties": {
                "summary": {"type": "string"},
                "capacity_and_range": {
                    "type": "array",
                    "maxItems": 2,  # <= keep tiny to avoid truncation
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["id","capacity_utilization","utilization_value","range_km_est","note"],
                        "properties": {
                            "id": {"type":"string"},
                            "capacity_utilization": {"type":"string","enum":["low","medium","high","unknown"]},
                            "utilization_value": {"type":["number","null"]},
                            "range_km_est": {"type":["integer","null"]},
                            "note": {"type":"string"}
                        }
                    }
                }
            }
        }
    }
}





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
# comment_ai.py

# (Optional) keep APPENDIX_JSON_CLAUSE for other modes, but don't use it in compact.
# APPENDIX_JSON_CLAUSE = ...  # leave as-is

PROMPT_TMPL_COMPACT = """
Vehicles (id → {{indicator, total, total_2dp,
  attrs:{{capacity_utilization, target_range_km, electricity_consumption_kwh_per_100km, fuel_consumption_l_per_100km, electricity_type, hydrogen_type, powertrain, top_stages, func_unit}},
  feats:{{capacity_utilization_label, energy_intensity_kwh_per_km, ttw_energy_mj_per_fu, available_payload_kg}},
  cost:{{currency, per_fu, total, components}},
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
- When assessing carrying capacity, use feats["available_payload_kg"] (gross mass − curb mass) if present. Ignore any payload utilization ratio fields.

- Summary (≤{word_limit} words):
    - Open with BEST and WORST by total GHG (use total_2dp, kgCO2-eq per FU).
    - Add ONE concise cost sentence (CHF per {fu_code}).
    - Interpret stage drivers ("energy chain", "road infrastructure construction & upkeep (embodied)").
    - Discuss tank-to-wheel energy (MJ per {fu_code}) where relevant.
    - Explain capacity utilization as a logistics load factor (%, no decimals).
    - Note mixed functional units if present; avoid cross-unit comparisons.

Output policy:
- Output **only** a JSON object with exactly these two keys: "summary" and "capacity_and_range".
- If a value is unknown, use null. Never write placeholders like number|null or "...".
- Keep all numbers as numbers (no strings for numbers).

Return ONLY this JSON:
{{
  "summary": "text",
  "capacity_and_range": [
    {{"id":"vehicle-id","capacity_utilization":"low","utilization_value":0.5,"range_km_est":120,"note":"short"}}
  ]
}}
"""

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




_OPENAI_CLIENT = None

def _get_openai_client():
    global _OPENAI_CLIENT
    if not OPENAI_API_KEY:
        raise RuntimeError("OpenAI API key not configured")
    if _OPENAI_CLIENT is None:
        # Generous default; retries OFF to avoid hidden delays
        _OPENAI_CLIENT = OpenAI(
            api_key=OPENAI_API_KEY,
            timeout=Timeout(connect=3.0, read=30.0, write=10.0, pool=3.0),  # large defaults
            max_retries=0,
        )
    return _OPENAI_CLIENT

def _call_openai(*, system, prompt, max_tokens, temp, timeout_s):
    def _valid(data: dict) -> bool:
        return (
            isinstance(data, dict)
            and isinstance(data.get("summary"), str) and data.get("summary", "").strip() != ""
            and isinstance(data.get("capacity_and_range"), list)
        )

    try:
        client = _get_openai_client()
    except Exception as e:
        return {"_error": f"ClientInitError: {e}"}

    # Ensure enough room to print valid JSON arguments (too small => truncation)
    max_tokens = max(220, min(int(max_tokens or 300), 360))

    # ---------- Attempt 1: function-call route ----------
    try:
        resp = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            tools=[COMPARE_TOOL],
            tool_choice={"type": "function", "function": {"name": "emit_swisscargo_compare"}},  # forced tool
            temperature=float(temp) if temp is not None else 0.0,  # use caller's temp
            max_tokens=max_tokens,
            timeout=float(timeout_s),
            n=1,
        )

        choice = resp.choices[0]
        tcalls = getattr(choice.message, "tool_calls", None)
        data = {}

        if tcalls:
            args = tcalls[0].function.arguments or ""
            try:
                data = json.loads(args)
            except json.JSONDecodeError:
                data = _extract_json(args)  # salvage inner {...}

        # Fallback to content if the model ignored tools
        if (not tcalls or not _valid(data)):
            content = (getattr(choice.message, "content", "") or "").strip()
            if content:
                try:
                    data = json.loads(content)
                except json.JSONDecodeError:
                    data = _extract_json(content)

        if _valid(data):
            return data
        # else fall through to Attempt 2

    except json.JSONDecodeError as e:
        # continue to Attempt 2
        pass
    except Exception as e:
        # continue to Attempt 2
        pass

    # ---------- Attempt 2: plain JSON response (no tools) ----------
    try:
        resp2 = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            response_format={"type": "json_object"},  # force strict JSON body
            temperature=float(temp) if temp is not None else 0.0,
            max_tokens=max_tokens,
            timeout=float(timeout_s),
            n=1,
        )
        content = (resp2.choices[0].message.content or "").strip()
        data = _extract_json(content)
        if _valid(data):
            return data
        return {"_error": "Model returned invalid/empty JSON after two attempts."}

    except Exception as e:
        return {"_error": f"{type(e).__name__}: {e}"}


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


def ai_compare_across_vehicles_swisscargo(
    veh_payload: dict, language="en", detail="compact", timeout_s=10.0
) -> dict:

    if not veh_payload or not isinstance(veh_payload, dict):
        return {"language": "en", "comparison": {"summary": "No vehicles to compare.", "capacity_and_range": []}}

    # ---- hard guard: never accept <= 0 or tiny budgets
    budget = float(timeout_s) if timeout_s and timeout_s > 0 else 6.0
    # Use (almost) the full slice the route gave us; cap to something sane if you want.
    api_budget = max(1.8, min(budget - 0.3, 12.0))  # e.g., 7.2s when budget=7.5

    cfg = DETAIL_CONFIG.get(detail, DETAIL_CONFIG["compact"]).copy()
    lang = _pick_lang(language)

    # Dynamically clamp tokens if little time remains
    # Aggressive clamping for speed
    if api_budget <= 3.0:
        cfg["max_tokens"] = 200
        cfg["word_limit"] = 90
    elif api_budget <= 5.0:
        cfg["max_tokens"] = 260
        cfg["word_limit"] = 110
    else:
        cfg["max_tokens"] = 320  # was 220
        cfg["word_limit"] = 120

    system = (
        f"You are an LCA assistant. Respond in {LANG_NAMES[lang]}. "
        "Use only provided numbers. Output strict JSON. "
        "Do not conflate capacity utilization with mechanical efficiency. "
        "When reporting costs, use CHF per FU exactly as provided."
    )

    slim_payload = _filter_essentials(veh_payload)
    for vid, d in slim_payload.items():
        # round totals to 2 dp; remove None entries
        d["total"] = _round_or_none(d.get("total"), nd=2)
        d["attrs"] = {k: v for k, v in d.get("attrs", {}).items() if v not in (None, "", [], {})}
        d["feats"] = {k: v for k, v in d.get("feats", {}).items() if v not in (None, "", [], {})}
        if "cost" in d:
            # keep only totals + top 2 components if present
            c = d["cost"]
            keep = {"currency": c.get("currency"), "total": c.get("total"), "per_fu": c.get("per_fu")}
            comps = c.get("components") or {}
            # keep top 2 biggest components if you have shares
            if c.get("shares_pct"):
                top2 = sorted(c["shares_pct"].items(), key=lambda it: it[1], reverse=True)[:2]
                keep["components"] = {k: comps.get(k) for k, _ in top2 if k in comps}
            else:
                keep["components"] = comps  # or prune by a fixed list
            d["cost"] = keep

    fu_code, fu_mixed = _resolve_fu_from_payload(slim_payload, fallback="vkm")
    fu_label = FU_NAME_MAP.get(fu_code, "vehicle-kilometer")

    # Keep payload compact; avoid pretty printing and ASCII escaping

    sanitized_payload = _sanitize_numbers(slim_payload)
    payload_str = json.dumps(
        sanitized_payload,
        ensure_ascii=True,  # keep it plain ASCII
        separators=(",", ":"),
        allow_nan=False  # hard fail if NaN/Inf slipped through
    )
    appendix_clause = "" if not cfg.get("include_appendix") else APPENDIX_JSON_CLAUSE.format(fu_code=fu_code)

    include_glossary = api_budget >= 4.0
    prompt = PROMPT_TMPL_COMPACT.format(
        veh_payload=payload_str,
        close_band=0.02,
        stage_glossary=STAGE_GLOSSARY.strip() if include_glossary else "",
        capacity_utilization_note=CAPACITY_UTILIZATION_NOTE.strip() if include_glossary else "",
        cost_policy=COST_POLICY.strip(),
        word_limit=cfg["word_limit"],
        fu_code=fu_code,
        appendix_clause=""  # omit appendix under tight budgets
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

        if not result or result.get("_error"):
            return {
                "language": lang,
                "comparison": {"summary": f"AI error: {result.get('_error', 'Empty response')}",
                               "capacity_and_range": []},
                "_error": result.get("_error", "Empty response"),
            }

    except Exception as e:
        return {
            "language": lang,
            "comparison": {"summary": "Time-limited comparison.", "capacity_and_range": []},
            "_error": f"{type(e).__name__}: {e}",
        }

    if not result:
        return {"language": lang, "comparison": {"summary": "Empty response from AI.", "capacity_and_range": []}}

    if result.get("_error"):
        return {
            "language": lang,
            "comparison": {
                "summary": f"AI error: {result['_error']}",
                "capacity_and_range": []
            },
            "_error": result["_error"],
        }

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
    return {"language": lang, "comparison": cleaned}



