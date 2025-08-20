"""
This module contains functions to validate the input data.
"""

import numpy as np
import xarray as xr

from .data.mapping import TCS_SIZE, TCS_PARAMETERS, TCS_POWERTRAIN, CAR_POWERTRAINS, CAR_SIZES, \
    CAR_BATTERIES


def validate_output_data(data: xr.DataArray, request: dict) -> list:
    """
    Validates the received data against the original request.
    :param data: data to validate
    :param request: original request
    :return: list of errors
    """

    errors = []

    fields = [
        "curb mass",
        "driving mass",
        "power",
        "battery capacity",
        "TtW energy",
        "fuel consumption",
        "electricity consumption",
        "range",
        "target range",
        "lifetime kilometers",
        "kilometers per year",
        "average passengers",
        "electric energy stored",
    ]

    shown_error_fields = [
        "lifetime kilometers",
        "kilometers per year",
        "average passengers",
        "capacity utilization",
        "daily distance",
        "number of trips",
        "distance per trip",
        "average speed",
        "driving mass",
        "power",
        "electric power",
        "TtW energy",
        "TtW energy, combustion mode",
        "TtW energy, electric mode",
        "TtW efficiency",
        "fuel consumption",
        "electricity consumption",
        "electric utility factor",
        "range",
        "target range",
        "battery technology",
        "electric energy stored",
        "battery lifetime kilometers",
        "battery cell energy density",
        "battery cycle life",
        "battery lifetime replacements",
        "fuel cell system efficiency",
        "fuel cell lifetime replacements",
        "oxidation energy stored",
        "fuel mass",
        "charger mass",
        "converter mass",
        "inverter mass",
        "power distribution unit mass",
        "combustion engine mass",
        "electric engine mass",
        "powertrain mass",
        "fuel cell stack mass",
        "fuel cell ancillary BoP mass",
        "fuel cell essential BoP mass",
        "battery cell mass",
        "battery BoP mass",
        "fuel tank mass",
        "curb mass",
        "cargo mass",
        "total cargo mass",
        "driving mass"
    ]

    for field in fields:
        if field in request:
            if field in ["fuel consumption", "electricity consumption"]:
                factor = 100
            else:
                factor = 1

            if not np.isclose(request[field], data.array.sel(parameter=field, value=0, powertrain=request["powertrain"]).values * factor, rtol=0.02):
                params = [p for p in shown_error_fields if p in data.array.coords['parameter'].values]
                d = {
                    k: v for k, v in zip(
                        params,
                        data.array.sel(
                            parameter=params,
                            value=0,
                            powertrain=request['powertrain'],
                            year=request['year'],
                            size=request['size'],
                        ).values
                     )
                }

                errors.append(f"Vehicle {request['id']} has invalid value for field {field}."
                              f" Expected {request[field]}, got {data.array.sel(parameter=field, value=0, powertrain=request['powertrain']).values}"
                              f"{d}")

    # check that available payload is still positive
    if "available payload" in data.array.coords['parameter'].values:
        if any(data.array.sel(parameter="available payload", value=0, powertrain=request["powertrain"]) < 0):
            errors.append(f"Vehicle {request['id']} has negative available payload for powertrain {request['powertrain']}.")

    return errors
