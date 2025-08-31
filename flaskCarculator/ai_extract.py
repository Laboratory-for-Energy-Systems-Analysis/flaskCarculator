

def _top_stage_contributors(stages: dict, n=2):
    # stages is already {"energy chain": 0.175, "road": 0.159, ...}
    items = sorted(stages.items(), key=lambda kv: kv[1], reverse=True)
    return [k for k, _ in items[:n]]


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
    for veh in vehicles:
        vid = veh.get("id")
        if not vid:
            continue

        # find climate change block
        cc = None
        for r in (veh.get("results") or []):
            if r.get("category") == "climate change":
                cc = r
                break
        if not cc:
            continue

        # totals & stages
        total = _sum_numeric(cc, exclude=("category",))
        stages = {
            k: float(val)
            for k, val in cc.items()
            if k != "category" and isinstance(val, (int, float))
        }

        payload = {
            "indicator": "climate change",
            "total": float(total),
            "stages": stages,
            "attrs": {
                "powertrain": veh.get("powertrain"),
                "size": veh.get("size"),
                "electric_energy_stored_kwh": veh.get("electric energy stored"),
                "electricity_consumption_kwh_per_100km": veh.get("electricity consumption"),
                "fuel_consumption_l_per_100km": veh.get("fuel consumption"),
                "curb_mass_kg": veh.get("curb mass"),
                "driving_mass_kg": veh.get("driving mass"),
                "gross_mass_kg": veh.get("gross mass"),
                "capacity_utilization": veh.get("capacity utilization"),
                "target_range_km": veh.get("target range"),
                "func_unit": veh["func_unit"],
                "top_stages": _top_stage_contributors(stages, n=2),
            },
            "feats": derive_features_from_vehicle(veh),
        }

        if include_stage_shares and stages:
            s = sum(stages.values())
            if s > 0:
                payload["stage_shares_pct"] = {k: 100.0 * val / s for k, val in stages.items()}

        out[vid] = payload
    return out


def _safe_float(x, default=None):
    try:
        return float(x)
    except Exception:
        return default

def _kj_to_mj(x):
    try:
        return float(x) / 1000.0
    except Exception:
        return None

def derive_features_from_vehicle(v: dict) -> dict:
    feats = {}

    # Identity
    feats["powertrain"] = v.get("powertrain")
    feats["size"] = v.get("size")
    feats["country"] = v.get("country")
    feats["year"] = v.get("year")

    # Energy / efficiency
    feats["electricity_consumption_kwh_per_100km"] = _safe_float(v.get("electricity consumption"))
    feats["fuel_consumption_l_per_100km"] = _safe_float(v.get("fuel consumption"))
    feats["ttw_efficiency"] = _safe_float(v.get("TtW efficiency"))
    feats["ttw_energy_kwh"] = _safe_float(v.get("TtW energy"))
    feats["ttw_energy_electric_kwh"] = _safe_float(v.get("TtW energy, electric mode"))
    feats["ttw_energy_combustion_kwh"] = _safe_float(v.get("TtW energy, combustion mode"))
    feats["electricity_type"] = v.get("electricity")
    feats["hydrogen_type"] = v.get("hydrogen")

    # Masses & packaging
    feats["battery_energy_kwh"] = _safe_float(v.get("electric energy stored"))
    feats["curb_mass_kg"] = _safe_float(v.get("curb mass"))
    feats["driving_mass_kg"] = _safe_float(v.get("driving mass"))
    feats["gross_mass_kg"] = _safe_float(v.get("gross mass"))
    feats["cargo_mass_kg"] = _safe_float(v.get("cargo mass"))
    feats["capacity_utilization"] = _safe_float(v.get("capacity utilization"))
    feats["battery_cell_energy_density_kwh_per_kg"] = _safe_float(v.get("battery cell energy density"))

    # Power
    feats["power_kw"] = _safe_float(v.get("power") or v.get("electric power"))

    # Range (reported only)
    feats["target_range_km"] = _safe_float(v.get("target range"))

    # Derived basics
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
        feats["energy_intensity_kwh_per_km"] = cons_el / 100.0  # /100 km → /km
    if cons_f is not None:
        feats["fuel_intensity_l_per_km"] = cons_f / 100.0
    if bat and dm and dm > 0:
        feats["battery_specific_energy_kwh_per_t_vehicle"] = bat / (dm / 1000.0)

    # Capacity utilization label (deterministic)
    cu = feats.get("capacity_utilization")
    if cu is not None:
        if cu < 0.35:
            feats["capacity_utilization_label"] = "low"
        elif cu <= 0.65:
            feats["capacity_utilization_label"] = "medium"
        else:
            feats["capacity_utilization_label"] = "high"

    # No theoretical_range_km or range_headroom_km computed anymore
    if capu and capu > 0 and gm:
        feats["payload_utilization_ratio"] = capu

    # Tank-to-wheel energy is given in kJ per vkm
    ttw_energy_kj_per_vkm = _safe_float(v.get("TtW energy"))
    feats["ttw_energy_kj_per_vkm"] = ttw_energy_kj_per_vkm

    fu = (v.get("func_unit") or "vkm").lower()
    cargo_mass_kg = _safe_float(v.get("cargo mass"))

    if ttw_energy_kj_per_vkm is not None:
        if fu == "vkm":
            feats["ttw_energy_mj_per_fu"] = ttw_energy_kj_per_vkm / 1000.0
        elif fu == "tkm":
            if cargo_mass_kg and cargo_mass_kg > 0:
                cargo_mass_tons = cargo_mass_kg / 1000.0
                feats["ttw_energy_mj_per_fu"] = (ttw_energy_kj_per_vkm / cargo_mass_tons) / 1000.0

    return {k: v for k, v in feats.items() if v is not None}

