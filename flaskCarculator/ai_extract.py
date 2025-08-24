def _sum_numeric(d: dict, exclude_keys=("category",)):
    s = 0.0
    for k, v in d.items():
        if k in exclude_keys: continue
        try: s += float(v)
        except Exception: pass
    return s

def build_compare_payload_swisscargo(vehicles: list) -> dict:
    """
    Build the dict expected by ai_compare_across_vehicles_swisscargo()
    from your 'swisscargo' vehicle payloads.
    """
    wanted_attrs = {
        "powertrain", "size", "electric energy stored", "electricity consumption",
        "fuel consumption", "curb mass", "cargo mass", "TtW efficiency",
        "kilometers per year", "lifetime kilometers", "country", "year"
    }
    out = {}
    for v in vehicles:
        vid = v.get("id")
        if not vid: continue
        # results is a list with one dict for climate change
        res_list = v.get("results") or []
        cc = None
        for r in res_list:
            if r.get("category") == "climate change":
                cc = r; break
        if not cc:
            continue
        total = _sum_numeric(cc, exclude_keys=("category",))
        stages = {k: float(val) for k, val in cc.items() if k != "category" and isinstance(val, (int, float))}
        attrs = {k: v.get(k) for k in wanted_attrs if k in v}
        out[vid] = {"indicator": "climate change", "total": float(total), "stages": stages, "attrs": attrs}
    return out
