"""
This module contains functions to validate the input data.
"""

import numpy as np
from scipy.interpolate import interp1d

from .data.mapping import (
    TCS_SIZE,
    TCS_PARAMETERS,
    TCS_POWERTRAIN,
    SWISSCARGO_SIZE,
    SWISSCARGO_PARAMETERS,
    FUEL_SPECS,
    CAR_POWERTRAINS,
    CAR_SIZES,
    CAR_BATTERIES,
    TRUCK_POWERTRAINS,
    TRUCK_SIZES,
    TRUCK_BATTERIES,
    BUS_POWERTRAINS,
    BUS_SIZES,
    BUS_BATTERIES,
    TWO_WHEELER_POWERTRAINS,
    TWO_WHEELER_SIZES,
    TWO_WHEELER_BATTERIES,
)


def get_mapping(vehicle_type: str) -> dict:
    """
    Returns the mapping for the given vehicle type.
    :param vehicle_type: vehicle type
    :return: mapping
    """
    mappings = {
        "car": {
            "powertrain": CAR_POWERTRAINS["powertrain"],
            "size": CAR_SIZES["size"],
            "battery": CAR_BATTERIES["battery"],
        },
        "truck": {
            "powertrain": TRUCK_POWERTRAINS["powertrain"],
            "size": TRUCK_SIZES["size"],
            "battery": TRUCK_BATTERIES["battery"],
        },
        "bus": {
            "powertrain": BUS_POWERTRAINS["powertrain"],
            "size": BUS_SIZES["size"],
            "battery": BUS_BATTERIES["battery"],
        },
        "two-wheeler": {
            "powertrain": TWO_WHEELER_POWERTRAINS["powertrain"],
            "size": TWO_WHEELER_SIZES["size"],
            "battery": TWO_WHEELER_BATTERIES["battery"],
        },
    }

    return mappings[vehicle_type]


def validate_input_data(data: dict) -> list:
    """
    Validates the received data against the TCS nomenclature.
    :param data: data to validate
    :return: list of errors
    """

    # Check if required fields are present
    required_fields = [
        "id",
        "vehicle_type",
        "powertrain",
        "year",
        "size"
    ]

    list_parameters = [
        "id",
        "vehicle_type",
        "cycle",
        "lifetime kilometers",
        "kilometers per year",
        "TtW energy",
        "payload",
        "cargo mass",
        "driving mass",
        "range",
        "electric utility factor",
        "power",
        "curb mass",
        "powertrain",
        "size",
        "year",
        "battery technology",
        "electric energy stored",
        "battery lifetime replacement",
        "target_range",
        "country",
        "func_unit",
        "scenario",
        "method",
        "indicator",
        "diesel",
        "petrol",
        "methane",
        "hydrogen",
        "electricity",
        "average passengers",
        # TCS nomenclature
        "fuel consumption",
        "electricity consumption",
        "fuel tank volume",
        "primary power",
        "direct_co2",
        "fuel_co2",
        "electric utility factor (wltp)",
        # Swisscargo nomenclature
        "interest rate",
        "fuel cost",
        "daily charger",
        "occasional charger",
        "electricity cost (daily charger)",
        "electricity cost (occasional charger)",
        "share km occasional charger",
        "trucks using daily charger",
        "hydrogen consumption",
        "hydrogen cost"
    ]



    errors = []


    for v, vehicle in enumerate(data["vehicles"]):
        for field in required_fields:
            if field not in vehicle:
                errors.append(f"Vehicle {vehicle['id']} missing required field: {field}")

        for key in vehicle:
            if key not in list_parameters:
                errors.append(f"Vehicle {vehicle['id']} has invalid field: {key}")

        vehicle_mapping = get_mapping(vehicle["vehicle_type"])

        # Check if 'size' is valid
        if vehicle.get("size") not in vehicle_mapping["size"]:
            errors.append(
                f"Vehicle {vehicle['id']} has invalid size value: {vehicle.get('size')}. Should be one of {vehicle_mapping['size']}"
            )

        # Check if 'powertrain' is valid
        if vehicle.get("powertrain") not in vehicle_mapping["powertrain"]:
            errors.append(
                f"Vehicle {vehicle['id']} has invalid powertrain value: {vehicle.get('powertrain')}. Should be one of {vehicle_mapping['powertrain']}"
            )

        # Check if 'curb mass' is a positive number
        if "curb mass" in vehicle and not isinstance(vehicle["curb mass"], (int, float)):
            errors.append(f"Vehicle {vehicle['id']} has invalid curb mass value: {vehicle['curb mass']} (must be a number)")
        elif "curb mass" in vehicle and vehicle["curb mass"] <= 0:
            errors.append(f"Vehicle {vehicle['id']} has: curb mass must be greater than 0.")

        # Check if 'cargo mass' is a positive number
        if "cargo mass" in vehicle and not isinstance(vehicle["cargo mass"], (int, float)):
            errors.append(f"Vehicle {vehicle['id']} has invalid cargo mass value: {vehicle['cargo mass']} (must be a number)")
        elif "cargo mass" in vehicle and vehicle["cargo mass"] <= 0:
            errors.append(f"Vehicle {vehicle['id']}: cargo mass must be greater than 0.")

        # Check if 'driving mass' is a positive number
        if "driving mass" in vehicle and not isinstance(vehicle["driving mass"], (int, float)):
            errors.append(f"Vehicle {vehicle['id']} has has invalid driving mass value: {vehicle['driving mass']} (must be a number)")
        elif "driving mass" in vehicle and vehicle["driving mass"] <= 0:
            errors.append(f"Vehicle {vehicle['id']}: driving mass must be greater than 0.")

        # Check if engine powers are valid numbers
        if "engine power" in vehicle and not isinstance(vehicle["engine power"], (int, float)):
            errors.append(f"Vehicle {vehicle['id']} has invalid engine power value: {vehicle['engine power']} (must be a number)")

        if "total engine power" in vehicle and not isinstance(vehicle["total engine power"], (int, float)):
            errors.append(f"Vehicle {vehicle['id']} has invalid total engine power value: {vehicle['total engine power']} (must be a number)")

        # Check if 'fuel tank volume' is a valid number
        if "fuel tank volume" in vehicle and not isinstance(vehicle["fuel tank volume"], (int, float)):
            errors.append(f"Vehicle {vehicle['id']} has invalid fuel tank mass value: {vehicle['fuel tank volume']} (must be a number)")

        # Check if `battery type` is valid
        if "battery technology" in vehicle and vehicle["battery technology"] not in vehicle_mapping["battery"]:
            errors.append(
                f"Vehicle {vehicle['id']} has invalid battery type value: {vehicle['battery technology']}. Should be one of {vehicle_mapping['battery']}"
            )

        # Check if 'electric energy stored' is a valid number
        if "electric energy stored" in vehicle and not isinstance(vehicle["electric energy stored"], (int, float)):
            errors.append(f"Vehicle {v} has invalid battery capacity value: {vehicle['electric energy stored']} (must be a number)")
        elif "electric energy stored" in vehicle and vehicle["electric energy stored"] <= 0:
            errors.append(f"Vehicle {vehicle['id']}: electric energy stored must be greater than 0.")

        # Check if 'range' is a valid number
        if "range" in vehicle and not isinstance(vehicle["range"], (int, float)):
            errors.append(f"Vehicle {v} has invalid range value: {vehicle['range']} (must be a number)")
        elif "range" in vehicle and vehicle["range"] <= 0:
            errors.append(f"Vehicle {v}: range must be greater than 0.")

        # Check if 'TtW energy' (energy use, in kj) is a valid number
        if "TtW energy" in vehicle and not isinstance(vehicle["TtW energy"], (int, float)):
            errors.append(f"Vehicle {v} has invalid TtW energy value: {vehicle['TtW energy']} (must be a number)")
        elif "TtW energy" in vehicle and vehicle["TtW energy"] <= 0:
            errors.append(f"Vehicle {v}: TtW energy must be greater than 0.")


    return errors

def calculate_utility_factor(ev_range):
    """
    Return the electric utility factor from teh all-electric WLTP vehicle range.
    From https://theicct.org/wp-content/uploads/2022/06/ICCT_PHEV_webinar_EN_2.pdf
    :param ev_range:
    :return: utility factor
    """

    range = [
        0,
        20,
        40,
        60,
        80,
        100,
        120
    ]

    real_uf = [
        0,
        13,
        23,
        32,
        39,
        45,
        50
    ]

    wltp_uf = [
        0,
        46,
        68.6,
        80,
        86.4,
        90.2,
        92.6
    ]

    # create a 1d interpolation model
    f_real = interp1d(range, real_uf, kind='linear', fill_value='extrapolate')
    f_wltp = interp1d(range, wltp_uf, kind='linear', fill_value='extrapolate')

    return float(f_real(ev_range)), float(f_wltp(ev_range))

def translate_swisscargo_to_carculator(data: dict) -> dict:
    """
    Translates the SwissCargo nomenclature to the Carculator nomenclature.
    :param data: data to translate
    :return: translated data
    """

    translated_data = []

    for vehicle in data["vehicles"]:
        new_vehicle = {}

        if "size" in vehicle:
            if vehicle["size"] in SWISSCARGO_SIZE:
                new_vehicle["size"] = SWISSCARGO_SIZE[vehicle["size"]]

        for k, v in SWISSCARGO_PARAMETERS.items():
            if k in vehicle:
                new_vehicle[v] = vehicle[k]

        # add other entries not in the mapping
        for k, v in vehicle.items():
            if k not in SWISSCARGO_PARAMETERS:
                if k not in new_vehicle:
                    new_vehicle[k] = v

        translated_data.append(new_vehicle)

    data["vehicles"] = translated_data

    return data



def translate_tcs_to_carculator(data: dict, errors: list) -> [dict, list]:
    """
    Translates the TCS nomenclature to the Carculator nomenclature.
    :param data: data to translate
    :return: translated data
    """

    translated_data = []

    for vehicle in data["vehicles"]:
        new_vehicle = {}

        for k, v in TCS_PARAMETERS.items():
            if k in vehicle:
                new_vehicle[v] = vehicle[k]

        if "fzklasse" in vehicle:
            if vehicle["fzklasse"] in TCS_SIZE:
                new_vehicle["size"] = TCS_SIZE[vehicle["fzklasse"]]

        if "tsa" in vehicle:
            if vehicle["tsa"] in TCS_POWERTRAIN:
                new_vehicle["powertrain"] = TCS_POWERTRAIN[vehicle["tsa"]]

            if "bat_km_WLTP" in vehicle:
                if TCS_POWERTRAIN[vehicle["tsa"]] not in ["BEV", "FCEV"]:
                    if TCS_POWERTRAIN.get(vehicle["tsa"]) in ["PHEV-p", "PHEV-d"]:
                        real_uf, wltp_uf = calculate_utility_factor(vehicle["bat_km_WLTP"])
                        new_vehicle["electric utility factor"] = real_uf / 100
                        new_vehicle["electric utility factor (wltp)"] = wltp_uf / 100
                    else:
                        errors.append(f"Vehicle {vehicle['id']} has a battery range but is not one of BEV, .")


        new_vehicle["TtW energy"] = 0
        # fuel consumption, in L/100 km
        if "ver" in vehicle:
            if new_vehicle["powertrain"] not in ("PHEV-p", "PHEV-d"):
                if new_vehicle["powertrain"] == "FCEV":
                    new_vehicle["fuel consumption"] = vehicle["ver"] * 11123 # converts kg to liters at ambient pressure
                else:
                    new_vehicle["fuel consumption"] = vehicle["ver"]
                new_vehicle["TtW energy"] += int(new_vehicle["fuel consumption"] * FUEL_SPECS[new_vehicle["powertrain"]]["lhv"] * 1000 / 100)
            else:
                new_vehicle["fuel consumption"] = vehicle["ver"] * ((1 - new_vehicle["electric utility factor"]) / (1 - new_vehicle["electric utility factor (wltp)"]))
                new_vehicle["TtW energy"] += int(new_vehicle["fuel consumption"] * FUEL_SPECS["ICEV-p"]["lhv"] * 1000 / 100)
                new_vehicle["direct_co2"] = vehicle.get("direct_co2") * (
                    (1 - new_vehicle["electric utility factor"]) / (1 - new_vehicle["electric utility factor (wltp)"])
                )

        if "ver_strom" in vehicle:
            if new_vehicle["powertrain"] not in ("PHEV-p", "PHEV-d"):
                new_vehicle["electricity consumption"] = vehicle["ver_strom"]
                new_vehicle["TtW energy"] += int(new_vehicle["electricity consumption"] * 3.6 * 1000 / 100)
            else:
                new_vehicle["electricity consumption"] = vehicle["ver_strom"] * (new_vehicle["electric utility factor"] / new_vehicle["electric utility factor (wltp)"])
                new_vehicle["TtW energy"] += int(new_vehicle["electricity consumption"] * 3.6 * 1000 / 100)

        # add other entries not in the mapping
        for k, v in vehicle.items():
            if k not in TCS_PARAMETERS:
                if k not in new_vehicle:
                    new_vehicle[k] = v

        for k, v in new_vehicle.items():
            if k in [
                "range",
                "curb mass",
                "cargo mass",
                "driving mass",
                "primary power",
                "power",
                "fuel tank volume",
                "electric energy stored",
                "fuel consumption",
                "electricity consumption",
            ]:
                new_vehicle[k] = float(v)

        translated_data.append(new_vehicle)

    data["vehicles"] = translated_data

    return data, errors


def validate_input(data: dict) -> [list, list]:
    """
    Validates the received data. Checks for required fields and valid values.
    Returns a list of errors, or an empty list if the data is valid.
    """
    errors = []

    MANDATORY_TERMS = [
        "nomenclature",
        "country_code",
        "vehicles",
    ]

    for term in MANDATORY_TERMS:
        if term not in data:
            errors.append(f"Missing mandatory term: {term}")

    if data.get("nomenclature") == "tcs":
        data, errors = translate_tcs_to_carculator(data, errors)

    if data.get("nomenclature") == "swisscargo":
        data = translate_swisscargo_to_carculator(data)

    errors.extend(validate_input_data(data))

    return data, errors
