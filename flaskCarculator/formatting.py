from flaskCarculator.data.mapping import FUEL_SPECS, TCS_IMPACTS_MAPPING
import xarray as xr

def format_results_for_tcs(data: xr.DataArray) -> dict:
    """
    Format the results for TCS.
    """

    results = {}

    # climate change results need to be in grams CO2-eq., not kg
    data.loc[dict(impact_category="climate change")] *= 1000

    for field, subfield in TCS_IMPACTS_MAPPING.items():
        results[field] = data.sel(
            impact_category=subfield["impact_category"],
            impact=subfield["impact"]
        ).sum().item()

    return results