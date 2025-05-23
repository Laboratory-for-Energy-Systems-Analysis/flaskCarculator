from flaskCarculator.data.mapping import TCS_IMPACTS_MAPPING, BAFU_EMISSSION_FACTORS
import xarray as xr


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

def format_results_for_swisscargo(data: xr.DataArray) -> list:
    """
    Format the results for SwissCargo.
    """

    results = []

    for impact_category in data.results.coords["impact_category"].values:
        result = {"category": impact_category}
        result.update(
            {
                i: data.results.sel(impact_category=impact_category, impact=i).sum().item()
                for i in data.results.coords["impact"].values
            }
        )
        results.append(result)

    return results