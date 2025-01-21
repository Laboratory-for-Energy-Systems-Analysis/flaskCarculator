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
        "range"
    ]

    for field in fields:
        if field in request:
            if field in ["fuel consumption", "electricity consumption"]:
                factor = 100
            else:
                factor = 1

            print(request[field], data.array.sel(parameter=field, value=0, powertrain=request["powertrain"]).values, factor)
            if not np.isclose(request[field], data.array.sel(parameter=field, value=0, powertrain=request["powertrain"]).values * factor, rtol=0.02):
                errors.append(f"Vehicle {request['id']} has invalid value for field {field}."
                              f" Expected {request[field]}, got {data.array.sel(parameter=field, value=0, powertrain=request['powertrain']).values}")

    return errors
