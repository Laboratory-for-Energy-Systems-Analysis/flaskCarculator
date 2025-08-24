# ai_extract.py (or routes.py)
def _sum_numeric(d: dict, exclude=("category",)):
    s = 0.0
    for k, v in d.items():
        if k in exclude:
            continue
        try:
            s += float(v)
        except Exception:
            pass
    return s

def build_compare_payload_swisscargo(vehicles: list, include_stage_shares=True) -> dict:
    """
    Returns a dict keyed by vehicle id with:
      - total (absolute)
      - stages (absolute)
      - (optional) stage_shares_pct
      - attrs (raw) and feats (derived)
    """
    out = {}
    for v in vehicles:
        vid = v.get("id")
        if not vid:
            continue
        # find climate change block
        cc = None
        for r in (v.get("results") or []):
            if r.get("category") == "climate change":
                cc = r; break
        if not cc:
            continue

        # totals & stages
        total = _sum_numeric(cc, exclude=("category",))
        stages = {k: float(val) for k, val in cc.items() if k != "category" and isinstance(val, (int, float))}

        payload = {
            "indicator": "climate change",
            "total": float(total),
            "stages": stages,
            "attrs": {
                # a compact subset of raw attrs the model might mention verbatim
                "powertrain": v.get("powertrain"),
                "size": v.get("size"),
                "electric energy stored": v.get("electric energy stored"),
                "electricity consumption": v.get("electricity consumption"),
                "fuel consumption": v.get("fuel consumption"),
                "curb mass": v.get("curb mass"),
                "driving mass": v.get("driving mass"),
                "gross mass": v.get("gross mass"),
                "capacity utilization": v.get("capacity utilization"),
                "TtW efficiency": v.get("TtW efficiency"),
            },
            "feats": derive_features_from_vehicle(v),
        }

        if include_stage_shares and stages:
            s = sum(stages.values())
            if s > 0:
                payload["stage_shares_pct"] = {k: 100.0 * v / s for k, v in stages.items()}

        out[vid] = payload
    return out


def _safe_float(x, default=None):
    try:
        return float(x)
    except Exception:
        return default

def derive_features_from_vehicle(v: dict) -> dict:
    """
    Build compact, numeric features the model can reason about.
    Everything is best-effort; missing inputs are okay.
    """
    feats = {}

    # Basic identity
    feats["powertrain"] = v.get("powertrain")
    feats["size"] = v.get("size")
    feats["country"] = v.get("country")
    feats["year"] = v.get("year")

    # Energy/efficiency
    feats["electricity_consumption_kwh_per_100km"] = _safe_float(v.get("electricity consumption"))
    feats["fuel_consumption_l_per_100km"] = _safe_float(v.get("fuel consumption"))
    feats["ttw_efficiency"] = _safe_float(v.get("TtW efficiency"))
    feats["ttw_energy_kwh"] = _safe_float(v.get("TtW energy"))
    feats["ttw_energy_electric_kwh"] = _safe_float(v.get("TtW energy, electric mode"))
    feats["ttw_energy_combustion_kwh"] = _safe_float(v.get("TtW energy, combustion mode"))

    # Masses & packaging
    feats["battery_energy_kwh"] = _safe_float(v.get("electric energy stored"))
    feats["curb_mass_kg"] = _safe_float(v.get("curb mass"))
    feats["driving_mass_kg"] = _safe_float(v.get("driving mass"))
    feats["gross_mass_kg"] = _safe_float(v.get("gross mass"))
    feats["cargo_mass_kg"] = _safe_float(v.get("cargo mass"))
    feats["capacity_utilization"] = _safe_float(v.get("capacity utilization"))
    feats["battery_cell_energy_density_kwh_per_kg"] = _safe_float(v.get("battery cell energy density"))

    # Power / performance
    feats["power_kw"] = _safe_float(v.get("power") or v.get("electric power"))

    # Derived metrics (safe guards against None/zero)
    cm = feats.get("curb_mass_kg")
    gm = feats.get("gross_mass_kg")
    dm = feats.get("driving_mass_kg")
    bat = feats.get("battery_energy_kwh")
    cons_el = feats.get("electricity_consumption_kwh_per_100km")
    cons_f = feats.get("fuel_consumption_l_per_100km")
    capu = feats.get("capacity_utilization") or 0.0
    pwr = feats.get("power_kw") or 0.0

    if gm and gm > 0 and cm is not None:
        feats["mass_fraction_curb_vs_gross"] = cm / gm
    if dm and dm > 0 and pwr:
        feats["power_to_mass_kw_per_t"] = pwr / (dm / 1000.0)
    if cons_el is not None:
        feats["energy_intensity_kwh_per_km"] = cons_el / 100.0  # convert /100km → /km
    if cons_f is not None:
        feats["fuel_intensity_l_per_km"] = cons_f / 100.0
    if bat and dm and dm > 0:
        feats["battery_specific_energy_kwh_per_t_vehicle"] = bat / (dm / 1000.0)
    if capu and capu > 0 and gm:
        feats["payload_utilization_ratio"] = capu  # already a ratio in your data

    return {k: v for k, v in feats.items() if v is not None}

