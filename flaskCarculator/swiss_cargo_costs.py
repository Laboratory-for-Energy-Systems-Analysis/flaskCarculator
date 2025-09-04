"""
This module calculates road and CO2 charges for trucks according to Swiss regulations.
"""

import re
from typing import Dict, Any, List
import math
import unicodedata
import re
from typing import Dict, Any, Optional, Tuple


def calculate_lsva_charge_period(vehicle_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compute Swiss LSVA/RPLP road charges over a specified ownership period,
    and return both total CHF and normalized CHF/km.

    Required keys in vehicle_data:
      - "powertrain": one of {"BEV", "ICEV-d", "HEV-d", "PHEV-d", "FCEV", "ICEV-g"}
      - "size": gross vehicle mass as string like "40t" or "3.5 t"
      - "kilometers per year": annual mileage (km/year)
      - "purchase_year": first full calendar year of use (int)
      - "resale_year": year the vehicle is sold; not driven this year (int)

    Optional:
      - "year": manufacture year (int). If absent, purchase_year is used as a proxy.

    Returns:
      {
        "total_charge_chf": float,
        "total_km": float,
        "cost_per_km_chf": float,     # normalized cost per km
        "breakdown": [                # per-year details
          {
            "year": int,
            "km": float,
            "tonnes": float,
            "rate_chf_per_tkm": float,
            "charge_chf": float
          }, ...
        ]
      }
    """
    # ---- Validate & parse inputs ----
    required = ["powertrain", "size", "kilometers per year", "purchase_year", "resale_year"]
    missing = [k for k in required if k not in vehicle_data]
    if missing:
        raise ValueError(f"Missing required keys: {', '.join(missing)}")

    pt = str(vehicle_data["powertrain"]).strip()
    size_str = str(vehicle_data["size"]).strip().lower()
    km_per_year = float(vehicle_data["kilometers per year"])
    purchase_year = int(vehicle_data["purchase_year"])
    resale_year = int(vehicle_data["resale_year"])
    manuf_year = int(vehicle_data.get("year", purchase_year))

    if km_per_year <= 0:
        raise ValueError("'kilometers per year' must be > 0.")
    if resale_year <= purchase_year:
        raise ValueError("'resale_year' must be strictly greater than 'purchase_year'.")

    # Extract tonnes from e.g. "40t", "3.5 t"
    m = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*t", size_str)
    if not m:
        raise ValueError("Could not parse tonnes from 'size'. Expected like '40t' or '3.5 t'.")
    tonnes = float(m.group(1))
    if tonnes <= 0:
        raise ValueError("Gross mass (tonnes) must be > 0.")

    # ---- Tariffs (CHF per tonne-km) ----
    CAT_I = 0.0326   # Euro 0–V
    CAT_II = 0.0282  # Euro VI/VII from 2029
    CAT_III = 0.0239 # Euro VI/VII until 2028, BEV/FCEV from 2029

    # ---- BEV/FCEV rebate schedule (fraction) ----
    bev_fcev_rebate = {
        2029: 0.7,
        2030: 0.6,
        2031: 0.5,
        2032: 0.4,
        2033: 0.3,
        2034: 0.2,
        2035: 0.1,
    }

    # ---- Determine Euro class bucket for ICE based on manufacture year ----
    # Heuristic:
    #   manuf_year >= 2014 -> Euro VI/VII (modern)
    #   manuf_year <= 2013 -> Euro 0–V (older)
    modern_vi_vii = manuf_year >= 2014

    def rate_chf_per_tkm_for_year(y: int) -> float:
        # Zero-emission vehicles
        if pt in {"BEV", "FCEV"}:
            if y <= 2028:
                return 0.0
            if 2029 <= y <= 2035:
                rebate = bev_fcev_rebate.get(y, 0.0)
                return CAT_III * (1.0 - rebate)
            return CAT_III  # 2036+
        # Treat HEV-d and PHEV-d like ICE
        if modern_vi_vii and pt in {"ICEV-d", "ICEV-g", "HEV-d", "PHEV-d"}:
            return CAT_III if y <= 2028 else CAT_II
        # Older Euro 0–V (or any ICE assumed older)
        if pt in {"ICEV-d", "ICEV-g", "HEV-d", "PHEV-d"}:
            return CAT_I
        # Fallback: if an unknown powertrain is passed
        raise ValueError(f"Unsupported powertrain '{pt}'.")

    # ---- Iterate over years in the ownership window ----
    years = list(range(purchase_year, resale_year))  # resale year not driven
    total_km = km_per_year * len(years)
    breakdown: List[Dict[str, Any]] = []
    total_charge = 0.0

    for y in years:
        rate = rate_chf_per_tkm_for_year(y)
        km = km_per_year
        chf = rate * tonnes * km  # CHF/(t·km) * t * km
        breakdown.append({
            "year": y,
            "km": km,
            "tonnes": tonnes,
            "rate_chf_per_tkm": rate,
            "charge_chf": chf,
        })
        total_charge += chf

    cost_per_km = (total_charge / total_km) if total_km > 0 else 0.0

    return {
        "total_charge_chf": total_charge,
        "total_km": total_km,
        "cost_per_km_chf": cost_per_km,
        "breakdown": breakdown,
    }

def _normalize_canton(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii","ignore").decode("ascii")
    return s.strip().lower()

def _parse_tonnes(size) -> Optional[float]:
    if size is None:
        return None
    if isinstance(size, (int, float)):
        return float(size)
    s = str(size).lower().replace(" ", "")
    if s.endswith("t"):
        s = s[:-1]
    try:
        return float(s.replace(",", "."))
    except ValueError:
        return None

def _years_owned_inclusive(purchase_year: int, resale_year: int) -> int:
    return int(resale_year) - int(purchase_year) + 1

def _infer_euro_truck(year: int, euro_class: Optional[str] = None) -> str:
    return euro_class or ("Euro 6" if year >= 2014 else "Euro 5")

# ---------- optional parser for your "original class name" bands ----------
def _parse_original_class(original: str) -> Optional[Tuple[str, Optional[float], Optional[float]]]:
    if not original:
        return None
    s = original.strip().lower().replace(" ", "").replace(",", ".")
    vehicle_type = "articulated" if s.startswith(("lz/sz","lzsz")) else ("rigid" if s.startswith("lkw") else None)
    if vehicle_type is None:
        return None
    m_eq = re.search(r"=(\d+(?:\.\d+)?)t", s)
    if m_eq:
        v = float(m_eq.group(1))
        return (vehicle_type, v, v)
    m_range = re.search(r">(\d+(?:\.\d+)?)(?:t)?-(\d+(?:\.\d+)?)t", s)
    if m_range:
        return (vehicle_type, float(m_range.group(1)), float(m_range.group(2)))
    m_open = re.search(r">(\d+(?:\.\d+)?)t$", s)
    if m_open:
        return (vehicle_type, float(m_open.group(1)), None)
    return None

def _tonnes_from_band(min_t: Optional[float], max_t: Optional[float], strategy: str = "midpoint") -> Optional[float]:
    if min_t is None and max_t is None:
        return None
    if max_t is None:
        return float(min_t)
    if strategy == "upper":
        return float(max_t)
    if strategy == "lower":
        return float(min_t)
    return (float(min_t) + float(max_t)) / 2.0

# ---------- canton annual formulas already in your model (ZH/GE/VD/TI/GR/VS) ----------
def _zurich_annual(weight_kg: int, euro: Optional[str], powertrain: str) -> float:
    base = 254.0
    if weight_kg > 4000:
        base += 35.0 * math.ceil((weight_kg - 4000) / 500)
    if powertrain.upper() in {"BEV", "FCEV"}:
        surcharge = 300.0
    else:
        e = (euro or "").lower()
        surcharge = 300.0 if any(x in e for x in ("6","vii","7")) else 900.0
    return base + surcharge

def _geneva_annual(weight_kg: int, year: int, powertrain: str) -> float:
    brackets = [
        (4000, 651.0), (4500, 716.0), (5000, 781.0), (5500, 846.0),
        (6000, 911.0), (6500, 976.0), (7000, 1041.0), (7500, 1106.0),
        (8000, 1171.0), (8500, 1236.0), (9000, 1301.0), (9500, 1366.0),
        (10000, 1431.0), (10500, 1496.0), (11000, 1561.0), (11500, 1626.0),
        (12000, 1691.0), (12500, 1756.0), (13000, 1821.0),
    ]
    if weight_kg <= 3500:
        amt = 350.5
    elif weight_kg > 13000:
        amt = 1837.0
    else:
        amt = next(val for ub, val in brackets if weight_kg <= ub)
    if powertrain.upper() in {"BEV","FCEV"} and year >= 2025:
        amt *= 0.5
    return amt

def _vaud_annual(weight_kg: int, powertrain: str, euro: Optional[str]) -> float:
    amt = 450.0
    if weight_kg > 4000:
        amt += 78.0 * math.ceil((weight_kg - 4000) / 1000)
    if powertrain.upper() == "BEV":
        return amt * 0.10  # −90%
    e = (euro or "").lower()
    return amt * (0.65 if any(x in e for x in ("6","vii","7")) else 1.0)

def _ticino_annual(power_kw: float) -> float:
    return 105.0 + 10.0 * float(power_kw)

def _gr_cat2(weight_kg: int) -> float:
    amt = 450.50
    if weight_kg > 2000:
        up_to = min(16000, weight_kg)
        amt += 15.10 * math.ceil((up_to - 2000) / 100)
    if weight_kg > 16000:
        amt += 11.30 * math.ceil((weight_kg - 16000) / 100)
    return amt

def _graubuenden_annual(weight_kg: int, powertrain: str) -> float:
    if powertrain.upper() in {"BEV","HEV-D","PHEV-D"}:
        return 0.20 * _gr_cat2(weight_kg)
    amt = 595.80
    if weight_kg > 3500:
        add1 = min(weight_kg, 6500) - 3500
        if add1 > 0:
            amt += 12.0 * math.ceil(add1 / 100)
        if weight_kg > 6500:
            add2 = min(weight_kg, 16000) - 6500
            amt += 9.30 * math.ceil(add2 / 100)
        if weight_kg > 16000:
            add3 = weight_kg - 16000
            amt += 8.50 * math.ceil(add3 / 100)
    return amt

def _valais_annual(weight_kg: int) -> float:
    if weight_kg <= 4000:
        return 400.0
    if weight_kg <= 15000:
        return 400.0 + 57.50 * math.ceil((weight_kg - 4000) / 1000)
    if weight_kg <= 23000:
        return 1500.0
    if weight_kg <= 32000:
        return 1750.0
    return 2000.0

# ---------- NEW: Bern (BE) ----------
def _bern_annual(weight_kg: int, powertrain: str, first_reg_year: int, this_year: int) -> float:
    """
    Normal tariff: first 1000 kg = 240 CHF; each subsequent *tonne* is 14% less
    than the *previous* per-tonne step. Pro-rata by days ignored here (full year).
    For BEV: base is 120 CHF for the first 1000 kg (same geometric decay per tonne),
    and an *additional* −60% rebate for the first 4 calendar years from first registration.
    """
    def _geometric_sum(kg: int, first_1000_rate: float) -> float:
        if kg <= 0:
            return 0.0
        # full 1000 kg blocks after the first 1000
        full_tonnes_after = max(0, (kg - 1000) // 1000)
        rem_kg = max(0, (kg - 1000) % 1000)
        total = first_1000_rate
        rate = first_1000_rate * (1 - 0.14)  # next 1'000 kg
        for _ in range(int(full_tonnes_after)):
            total += rate
            rate *= (1 - 0.14)
        if rem_kg > 0:
            total += rate * (rem_kg / 1000.0)
        return total

    if powertrain.upper() == "BEV":
        base = _geometric_sum(weight_kg, 120.0)
        # 60% rebate for first registration year and next 3 years
        if this_year >= first_reg_year and this_year <= first_reg_year + 3:
            base *= 0.40
        return base

    # non-BEV/FCEV
    return _geometric_sum(weight_kg, 240.0)

# ---------- NEW: Basel-Landschaft (BL) ----------
def _baselland_annual(weight_kg: int) -> float:
    # Lastwagen ... CHF per kg
    return 0.121446 * float(weight_kg)

# ---------- NEW: Fribourg (FR) ----------
def _fribourg_annual(weight_kg: int) -> float:
    """
    2025 heavy-vehicle table (FR). Brackets (CHF) for >3.5t “voiture automobile, camion, tracteur à sellette, véhicule articulé …”
    """
    tbl = [
        (7500, 1140.0),
        (14000, 1666.0),
        (20000, 2192.0),
        (26000, 2718.0),
        (32000, 3244.0),
        (10**9, 3770.0),  # ≥32'001 kg
    ]
    if weight_kg <= 3500:
        return 0.0  # below “lourd” threshold; out of scope here
    for ub, val in tbl:
        if weight_kg <= ub:
            return val
    return tbl[-1][1]

# ---------- NEW: Aargau (AG) ----------
def _aargau_annual(payload_kg: int) -> float:
    """
    Nutzfahrzeuge über 1'000 kg Nutzlast – annual charge by payload band.
    """
    bands = [
        (1500, 348.0), (2000, 420.0), (2500, 492.0), (3000, 564.0),
        (3500, 636.0), (4000, 708.0), (4500, 780.0), (5000, 852.0),
        (5500, 936.0), (6000, 1020.0), (6500, 1104.0), (7000, 1188.0),
        (7500, 1272.0), (8000, 1356.0), (8500, 1440.0), (9000, 1524.0),
        (9500, 1608.0),
    ]
    if payload_kg < 1000:
        raise ValueError("AG expects payload >= 1'000 kg (else use the 'Motorwagen' schedule).")
    for ub, val in bands:
        if payload_kg <= ub:
            return val
    # > 9'500 kg payload – the published page stops here; assume step continues +84 CHF per 500 kg
    extra_steps = math.ceil((payload_kg - 9500) / 500)
    return 1608.0 + extra_steps * 84.0

# ---------- public API ----------
def canton_truck_tax(vehicle_data: Dict[str, Any], *, band_estimation: str = "midpoint") -> Dict[str, Any]:
    """
    Single-canton truck road tax. Returns annual CHF, total over ownership (inclusive),
    and normalized CHF/km.

    Required:
      - canton
      - powertrain
      - year (manufacture year; used for Euro/BEV timelines)
      - purchase_year, resale_year (inclusive)
      - kilometers per year
      - EITHER exact weight via 'size' (e.g. '40t') OR 'original class name' band

    Extra (if applicable):
      - power (kW)            # Ticino
      - euro_class            # if you don’t want inference
      - payload_kg            # Aargau (AG) needs Nutzlast

    Notes:
      - Genève’s BEV/H₂ 50% reduction is applied year-by-year from 2025.
      - Bern’s BEV −60% reduction is applied year-by-year for first 4 reg. years.
    """
    canton_raw = str(vehicle_data["canton"])
    canton = _normalize_canton(canton_raw)
    pt = str(vehicle_data["powertrain"]).strip()
    made_year = int(vehicle_data["year"])
    euro = _infer_euro_truck(made_year, vehicle_data.get("euro_class"))
    y0, y1 = int(vehicle_data["purchase_year"]), int(vehicle_data["resale_year"])
    km_per_year = float(vehicle_data["kilometers per year"])
    years = _years_owned_inclusive(y0, y1)
    total_km = km_per_year * years

    # weight resolution
    tonnes = _parse_tonnes(vehicle_data.get("size"))
    vehicle_type = None
    weight_source = "size"
    if tonnes is None:
        parsed = _parse_original_class(vehicle_data.get("original class name",""))
        if parsed:
            vehicle_type, lo, hi = parsed
            tonnes = _tonnes_from_band(lo, hi, band_estimation)
            weight_source = "original class name"
        else:
            tonnes = None
    if canton in {"ag", "aargau"} and "cargo mass" not in vehicle_data:
        # For AG we must use payload-based table; weight may still be useful for your other modules.
        pass
    if tonnes is None and canton not in {"ag","aargau"}:
        raise ValueError("Provide 'size' (e.g., '40t') or a parseable 'original class name'.")

    weight_kg = int(round(tonnes * 1000)) if tonnes is not None else None

    # dispatch per canton
    per_year = None
    notes = []
    if canton in {"zh","zuerich","zurich","zurich city"}:
        annual = _zurich_annual(weight_kg, euro, pt)

    elif canton in {"ge","geneve","geneva"}:
        per_year, total = [], 0.0
        for yr in range(y0, y1 + 1):
            a = _geneva_annual(weight_kg, yr, pt)
            per_year.append({"year": yr, "annual_tax_chf": round(a, 2)})
            total += a
        annual = total / years if years else 0.0
        notes.append("Genève: −50% for BEV/FCEV from 2025 applied year-by-year.")

    elif canton in {"vd","vaud"}:
        annual = _vaud_annual(weight_kg, pt, euro)

    elif canton in {"ti","ticino"}:
        if "power" not in vehicle_data:
            raise ValueError("Ticino requires 'power' (kW).")
        annual = _ticino_annual(float(vehicle_data["power"]))
        notes.append("Ticino formula: CHF 105 + 10 × kW.")

    elif canton in {"gr","graubunden","graubuenden"}:
        annual = _graubuenden_annual(weight_kg, pt)
        notes.append("Graubünden: EV/(H)EV trucks pay 20% of Category-2 weight tariff.")

    elif canton in {"vs","valais"}:
        annual = _valais_annual(weight_kg)

    # NEW ones
    elif canton in {"be","bern","berne"}:
        # apply BE year-by-year (for BEV’s 4-year rebate)
        per_year, total = [], 0.0
        # first registration year defaults to manufacture year if not given
        first_reg = int(vehicle_data.get("first_registration_year", made_year))
        for yr in range(y0, y1 + 1):
            a = _bern_annual(weight_kg, pt, first_reg, yr)
            per_year.append({"year": yr, "annual_tax_chf": round(a, 2)})
            total += a
        annual = total / years if years else 0.0
        notes.append("Bern: geometric weight tariff (−14% per extra tonne); BEV −60% for first 4 reg. years.")

    elif canton in {"bl","baselland","basel-landschaft","basel landschaft"}:
        annual = _baselland_annual(weight_kg)
        notes.append("Basel-Landschaft: Lastwagen CHF/kg weight rate (variable tax table).")

    elif canton in {"fr","fribourg","freiburg"}:
        annual = _fribourg_annual(weight_kg)
        notes.append("Fribourg: heavy-vehicle fixed weight brackets (2025 tariff).")

    elif canton in {"ag","aargau"}:
        if "cargo mass" not in vehicle_data:
            raise ValueError("Aargau requires 'cargo mass' (Nutzlast) for trucks.")
        annual = _aargau_annual(int(vehicle_data["cargo mass"]))
        notes.append("Aargau: trucks taxed by payload (Nutzlast) bands.")

    else:
        raise ValueError(f"Unsupported/unknown canton '{canton_raw}'.")

    total_tax = annual * years
    chf_per_km = (total_tax / total_km) if total_km > 0 else 0.0

    return {
        "canton": canton_raw,
        "vehicle_type_inferred": vehicle_type,                    # 'rigid' / 'articulated' if parsed
        "tonnes_used": round(tonnes, 3) if tonnes is not None else None,
        "weight_source": weight_source if tonnes is not None else None,
        "annual_tax_chf": round(annual, 2),
        "years": years,
        "total_tax_chf": round(total_tax, 2),
        "total_km": int(total_km),
        "chf_per_km": round(chf_per_km, 6),
        **({"per_year": per_year} if per_year else {}),
        "notes": notes + [
            f"Euro class: {_infer_euro_truck(made_year, vehicle_data.get('euro_class'))} (manufacture year {made_year}).",
            "Ownership window treated as calendar-year inclusive.",
        ],
    }
