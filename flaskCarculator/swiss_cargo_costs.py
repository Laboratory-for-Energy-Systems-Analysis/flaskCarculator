"""
This module calculates road and CO2 charges for trucks according to Swiss regulations.
"""

import re
from typing import Dict, Any, List

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
