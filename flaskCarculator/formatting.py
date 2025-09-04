from flaskCarculator.data.mapping import TCS_IMPACTS_MAPPING, BAFU_EMISSSION_FACTORS
import xarray as xr
import re


def format_results_for_tcs(data: xr.DataArray, params: dict, bafu: bool = False) -> dict:
    """
    Format the results for TCS.
    """

    if bafu:
        lca_results = data.bafu_results
    else:
        lca_results = data.results

    for powertrain in data.array.coords["powertrain"].values:
        for size in data.array.coords["size"].values:
            for year in data.array.coords["year"].values:
                fuel_consumption = data.array.sel(powertrain=powertrain, size=size, parameter="fuel consumption",
                                                  year=year).values

                electricity_consumption = data.array.sel(powertrain=powertrain, size=size,
                                                         parameter="electricity consumption", year=year).values

                if powertrain not in ("PHEV-p", "PHEV-d"):
                    emission_factor = BAFU_EMISSSION_FACTORS[powertrain]

                    for impact, value in emission_factor.items():
                        lca_results.loc[dict(
                            powertrain=powertrain,
                            size=size,
                            year=year,
                            impact_category=impact,
                            impact="energy chain",
                        )] = float((fuel_consumption * value) + (electricity_consumption * value))

                else:
                    electricity_emission_factor = BAFU_EMISSSION_FACTORS["PHEV-e"]

                    if powertrain == "PHEV-d":
                        fuel_emission_factor = BAFU_EMISSSION_FACTORS["PHEV-c-d"]
                    else:
                        fuel_emission_factor = BAFU_EMISSSION_FACTORS["PHEV-c-p"]

                    for impact, value in electricity_emission_factor.items():
                        lca_results.loc[dict(
                            powertrain=powertrain,
                            size=size,
                            year=year,
                            impact_category=impact,
                            impact="energy chain"
                        )] = float(
                            electricity_consumption * value
                        )

                    for impact, value in fuel_emission_factor.items():
                        lca_results.loc[dict(
                            powertrain=powertrain,
                            size=size,
                            year=year,
                            impact_category=impact,
                            impact="energy chain"
                        )] += float(
                            fuel_consumption * value
                        )

    results = {}

    # climate change results need to be in grams CO2-eq., not kg
    lca_results.loc[dict(impact_category="climate change")] *= 1000

    # direct exhaust emission is passed directly. it should override the value calculated.
    if "direct_co2" in params:
        lca_results.loc[dict(impact_category="climate change", impact="direct - exhaust")] = params["direct_co2"]

    if "fuel_co2" in params:
        lca_results.loc[dict(impact_category="climate change", impact="energy chain")] = params["fuel_co2"]

    for field, subfield in TCS_IMPACTS_MAPPING.items():
        results[field] = lca_results.sel(
            impact_category=subfield["impact_category"],
            impact=subfield["impact"]
        ).sum().item()

    return results



def format_results_for_swisscargo(data: xr.DataArray, params: dict) -> list:
    """
    Format the results for SwissCargo.

    Supports params["electricity"] being:
      - "grid" (default)
      - "<X>_own_<Y>_grid"  (e.g., "30_own_70_grid"), meaning X% on-site PV, Y% grid.
        X and Y need not sum to 100; if not, they are normalized.
    """

    lca_results = data.bafu_results

    electricity_param = params.get("electricity", "grid")
    has_average_h2 = params.get("hydrogen", "hydrogen - electrolysis - PEM") == "hydrogen - electrolysis - PEM"

    # --- Helpers -------------------------------------------------------------
    def _get_number(d, key, subkey="climate change"):
        """Fetch emission factor number d[key][subkey] with graceful fallbacks."""
        if key in d and isinstance(d[key], dict) and subkey in d[key]:
            return float(d[key][subkey])
        return None

    def _electricity_grid_ef():
        """
        Try reasonable keys that should contain an electricity grid EF per kWh.
        Adjust if your keys differ.
        """
        for k in ("PHEV-e", "BEV", "electricity-grid", "grid-electricity"):
            v = _get_number(BAFU_EMISSSION_FACTORS, k)
            if v is not None:
                return v
        raise KeyError("Can't find grid electricity EF in BAFU_EMISSSION_FACTORS.")

    def _electricity_pv_ef():
        """
        Return GHG emission factors for on-site PV electricity generation.
        """
        return 0.04  # kg CO2e/kWh

    def _parse_pv_grid_mix(s: str):
        """
        Parse strings like '30_own_70_grid' -> (pv_share, grid_share) as decimals.
        Normalizes if they don't sum to 100.
        """
        m = re.fullmatch(r"\s*(\d{1,3})_own_(\d{1,3})_grid\s*", s)
        if not m:
            return None
        x, y = int(m.group(1)), int(m.group(2))
        total = x + y if (x + y) > 0 else 100
        return (x / total, y / total)

    def _blended_electricity_ef():
        """Return the electricity EF to use (kg CO2e/kWh) after blending, if needed."""
        pv_grid = _parse_pv_grid_mix(electricity_param)
        grid_ef = _electricity_grid_ef()
        if pv_grid is None:  # "grid" or any other legacy value -> treat as pure grid
            return grid_ef
        pv_share, grid_share = pv_grid
        pv_ef = _electricity_pv_ef()
        return (pv_share * pv_ef) + (grid_share * grid_ef)
    # ------------------------------------------------------------------------

    blended_elec_ef = _blended_electricity_ef()

    factor = 1
    if "func_unit" in params and params["func_unit"] == "tkm":
        factor = 1 / (data.array.sel(parameter="cargo mass").values.item() / 1000)

    for powertrain in data.array.coords["powertrain"].values:
        for size in data.array.coords["size"].values:
            for year in data.array.coords["year"].values:
                fuel_consumption = data.array.sel(
                    powertrain=powertrain, size=size,
                    parameter="fuel consumption", year=year
                ).values

                electricity_consumption = data.array.sel(
                    powertrain=powertrain, size=size,
                    parameter="electricity consumption", year=year
                ).values

                if powertrain not in ("PHEV-p", "PHEV-d"):
                    # Base EF set by powertrain for fuel portion
                    emission_factor = BAFU_EMISSSION_FACTORS[powertrain]

                    # Special case: non-average hydrogen for FCEV
                    if has_average_h2 is False and powertrain == "FCEV":
                        emission_factor = {"climate change": 11.4}

                    for impact_cat, value in emission_factor.items():
                        if impact_cat == "climate change":
                            # Fuel part uses the powertrain EF.
                            fuel_part = float(fuel_consumption * value)

                            # Electricity part (e.g., BEV, auxiliaries) uses blended electricity EF.
                            elec_part = float(electricity_consumption * blended_elec_ef)

                            lca_results.loc[dict(
                                powertrain=powertrain, size=size, year=year,
                                impact_category=impact_cat, impact="energy chain",
                            )] = (fuel_part + elec_part) * factor

                else:
                    # PHEV: electricity portion (use blended EF) + fuel portion (PHEV-specific EF)
                    # Electricity EF for PHEV-e gets overridden by blended_elec_ef
                    if powertrain == "PHEV-d":
                        fuel_emission_factor = BAFU_EMISSSION_FACTORS["PHEV-c-d"]
                    else:
                        fuel_emission_factor = BAFU_EMISSSION_FACTORS["PHEV-c-p"]

                    # Electricity part
                    lca_results.loc[dict(
                        powertrain=powertrain, size=size, year=year,
                        impact_category="climate change", impact="energy chain"
                    )] = float(electricity_consumption * blended_elec_ef) * factor

                    # Fuel part
                    fuel_value = _get_number(fuel_emission_factor, "climate change")
                    if fuel_value is None:
                        raise KeyError("Can't find 'climate change' EF for PHEV fuel in BAFU_EMISSSION_FACTORS.")
                    lca_results.loc[dict(
                        powertrain=powertrain, size=size, year=year,
                        impact_category="climate change", impact="energy chain"
                    )] += float(fuel_consumption * fuel_value) * factor

    results = []
    for impact_category in lca_results.coords["impact_category"].values:
        result = {"category": impact_category}
        result.update({
            i: lca_results.sel(impact_category=impact_category, impact=i).sum().item()
            for i in lca_results.coords["impact"].values
        })
        results.append(result)

    return results
