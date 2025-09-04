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
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    return s.strip().lower()

def _parse_tonnes(size) -> Optional[float]:
    """Accepts '40t', '40 t', 40, 40.0 → tonnes as float. Returns None if not parseable."""
    if size is None:
        return None
    if isinstance(size, (int, float)):
        return float(size)
    s = str(size).lower().replace(" ", "")
    if s.endswith("t"):
        s = s[:-1]
    try:
        return float(s.replace(",", "."))  # support '7,5'
    except ValueError:
        return None

def _years_owned_inclusive(purchase_year: int, resale_year: int) -> int:
    return int(resale_year) - int(purchase_year) + 1

def _infer_euro_truck(year: int, euro_class: Optional[str] = None) -> str:
    if euro_class:
        return euro_class
    return "Euro 6" if year >= 2014 else "Euro 5"


def _parse_original_class(original: str) -> Optional[Tuple[str, Optional[float], Optional[float]]]:
    """
    Returns (vehicle_type, min_t, max_t) where vehicle_type in {'rigid','articulated'}.
    min_t/max_t in tonnes; max_t may be None if open-ended (>32t).
    """
    if not original:
        return None
    s = original.strip().lower().replace(" ", "")
    vehicle_type = "articulated" if s.startswith("lz/sz") or s.startswith("lzsz") else "rigid" if s.startswith("lkw") else None
    if vehicle_type is None:
        return None

    # Normalize decimal comma in numbers
    s = s.replace(",", ".")
    # Patterns:
    #   =7.5t
    m_eq = re.search(r"=(\d+(?:\.\d+)?)t", s)
    if m_eq:
        val = float(m_eq.group(1))
        return (vehicle_type, val, val)

    #   >7.5-12t   OR   >7.5t-14t  (allow optional 't' after first number)
    m_range = re.search(r">(\d+(?:\.\d+)?)(?:t)?-(\d+(?:\.\d+)?)t", s)
    if m_range:
        lo = float(m_range.group(1))
        hi = float(m_range.group(2))
        return (vehicle_type, lo, hi)

    #   >32t   (open-ended)
    m_open = re.search(r">(\d+(?:\.\d+)?)t$", s)
    if m_open:
        lo = float(m_open.group(1))
        return (vehicle_type, lo, None)

    return None

def _estimate_tonnes_from_band(min_t: Optional[float], max_t: Optional[float], strategy: str = "midpoint") -> Optional[float]:
    """
    strategy ∈ {'midpoint','upper','lower'}; for open-ended, fallback to min_t.
    """
    if min_t is None and max_t is None:
        return None
    if max_t is None:
        # open-ended, e.g., >32 t → use min bound (conservative) or allow override later
        return float(min_t)
    if strategy == "upper":
        return float(max_t)
    if strategy == "lower":
        return float(min_t)
    # midpoint
    return (float(min_t) + float(max_t)) / 2.0

# ---------- canton formulas (annual, same as before) ----------
def _zurich_annual(weight_kg: int, euro: Optional[str], powertrain: str) -> float:
    base = 254.0
    if weight_kg > 4000:
        steps = math.ceil((weight_kg - 4000) / 500)
        base += 35.0 * steps
    if powertrain.upper() in {"BEV", "FCEV"}:
        surcharge = 300.0
    else:
        e = (euro or "").lower()
        surcharge = 300.0 if ("6" in e or "vii" in e or "7" in e) else 900.0
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
    if powertrain.upper() in {"BEV", "FCEV"} and year >= 2025:
        amt *= 0.5
    return amt

def _vaud_annual(weight_kg: int, powertrain: str, euro: Optional[str]) -> float:
    amt = 450.0
    if weight_kg > 4000:
        steps = math.ceil((weight_kg - 4000) / 1000)
        amt += 78.0 * steps
    if powertrain.upper() == "BEV":
        amt *= 0.10
    else:
        e = (euro or "").lower()
        if "6" in e or "7" in e or "vii" in e:
            amt *= 0.65
    return amt

def _ticino_annual(power_kw: float) -> float:
    return 105.0 + 10.0 * float(power_kw)

def _gr_category2(weight_kg: int) -> float:
    amt = 450.50
    if weight_kg > 2000:
        up_to = min(16000, weight_kg)
        amt += 15.10 * math.ceil((up_to - 2000) / 100)
    if weight_kg > 16000:
        amt += 11.30 * math.ceil((weight_kg - 16000) / 100)
    return amt

def _graubuenden_annual(weight_kg: int, powertrain: str) -> float:
    if powertrain.upper() in {"BEV", "HEV-D", "PHEV-D"}:
        return 0.20 * _gr_category2(weight_kg)
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

# ---------- public function ----------
def canton_truck_tax(vehicle_data: Dict[str, Any], *, band_estimation: str = "midpoint") -> Dict[str, Any]:
    """
    Compute the cantonal annual truck road tax for ONE canton, total it over the
    inclusive ownership window, and normalize per km.

    Required keys:
      - canton
      - purchase_year, resale_year
      - kilometers per year
      - year  (manufacture year; used to infer Euro class if 'euro_class' not given)
      - EITHER:
          - size (e.g., '40t' or numeric tonnes)
        OR
          - original class name (e.g., 'LKW >20-26t', 'LZ/SZ >34-40t')

    Extra (recommended for accuracy):
      - euro_class (e.g., 'Euro 6d')
      - power (kW)  # required for Ticino

    band_estimation: how to estimate tonnes from a class band:
        'midpoint' (default), 'upper', or 'lower'.
    """
    # inputs
    canton_raw = str(vehicle_data["canton"])
    canton = _normalize_canton(canton_raw)
    pt = str(vehicle_data["powertrain"]).strip()
    made_year = int(vehicle_data["year"])
    euro = _infer_euro_truck(made_year, vehicle_data.get("euro_class"))
    y0, y1 = int(vehicle_data["purchase_year"]), int(vehicle_data["resale_year"])
    km_per_year = float(vehicle_data["kilometers per year"])

    # weight: prefer explicit 'size'
    tonnes = _parse_tonnes(vehicle_data.get("size"))
    vehicle_type = None
    weight_source = "size"

    if tonnes is None:
        parsed = _parse_original_class(vehicle_data.get("original class name", ""))
        if parsed:
            vehicle_type, min_t, max_t = parsed
            tonnes = _estimate_tonnes_from_band(min_t, max_t, band_estimation)
            weight_source = "original class name"
        else:
            raise ValueError("Provide either 'size' (e.g., '40t') or a parseable 'original class name'.")

    weight_kg = int(round(tonnes * 1000))
    years = _years_owned_inclusive(y0, y1)
    total_km = km_per_year * years

    # compute per canton
    annual = None
    per_year = None
    notes = []

    if canton in {"zurich", "zh", "zuerich", "zurich city"}:
        annual = _zurich_annual(weight_kg, euro, pt)

    elif canton in {"geneve", "geneva", "ge"}:
        per_year = []
        total = 0.0
        for yr in range(y0, y1 + 1):
            a = _geneva_annual(weight_kg, yr, pt)
            per_year.append({"year": yr, "annual_tax_chf": round(a, 2)})
            total += a
        annual = total / years if years > 0 else 0.0
        notes.append("Genève: BEV/FCEV 50% rebate applied from 2025, year-by-year.")

    elif canton in {"vaud", "vd"}:
        annual = _vaud_annual(weight_kg, pt, euro)

    elif canton in {"ticino", "ti"}:
        if "power" not in vehicle_data:
            raise ValueError("For Ticino, please provide 'power' (kW) in vehicle_data.")
        annual = _ticino_annual(float(vehicle_data["power"]))
        notes.append("Ticino formula: 105 + 10 × power_kW.")

    elif canton in {"graubuenden", "graubunden", "gr"}:
        annual = _graubuenden_annual(weight_kg, pt)
        notes.append("Graubünden: EV/(H)EV trucks taxed at 20% of Category-2 weight tariff.")

    elif canton in {"valais", "vs"}:
        annual = _valais_annual(weight_kg)

    else:
        raise ValueError(f"Unsupported/unknown canton '{canton_raw}'.")

    total_tax = annual * years
    chf_per_km = (total_tax / total_km) if total_km > 0 else 0.0

    return {
        "canton": canton_raw,
        "vehicle_type_inferred": vehicle_type,          # 'rigid' or 'articulated' if from class name
        "tonnes_used": round(tonnes, 3),
        "weight_source": weight_source,                 # 'size' or 'original class name'
        "annual_tax_chf": round(annual, 2),
        "years": years,
        "total_tax_chf": round(total_tax, 2),
        "total_km": int(total_km),
        "chf_per_km": round(chf_per_km, 6),
        **({"per_year": per_year} if per_year else {}),
        "notes": [
            f"Euro class: {euro} (manufacture year {made_year}).",
            f"Weight estimation strategy: {band_estimation}.",
            "Ownership window treated as calendar-year inclusive.",
        ] + notes,
    }
