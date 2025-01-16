"""
This module contains functions to validate the input data.
"""

from .data.mapping import (
    TCS_SIZE,
    TCS_PARAMETERS,
    TCS_POWERTRAIN,
    SWISSCARGO_SIZE,
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
        "electric utility factor",
        "power",
        "curb mass",
        "powertrain",
        "size",
        "year",
        "battery technology",
        "electric energy stored",
        "target_range",
        "country",
        "func_unit",
        "scenario",
        "method",
        "indicator"
    ]

    errors = []

    for v, vehicle in enumerate(data["vehicles"]):
        for field in required_fields:
            if field not in vehicle:
                errors.append(f"Vehicle {v} missing required field: {field}")

        for key in vehicle:
            if key not in list_parameters:
                errors.append(f"Vehicle {v} has invalid field: {key}")

        vehicle_mapping = get_mapping(vehicle["vehicle_type"])

        # Check if 'size' is valid
        if vehicle.get("size") not in vehicle_mapping["size"]:
            errors.append(
                f"Vehicle {v} has invalid size value: {vehicle.get('size')}. Should be one of {vehicle_mapping['size']}"
            )

        # Check if 'powertrain' is valid
        if vehicle.get("powertrain") not in vehicle_mapping["powertrain"]:
            errors.append(
                f"Vehicle {v} has invalid powertrain value: {vehicle.get('powertrain')}. Should be one of {vehicle_mapping['powertrain']}"
            )

        # Check if 'curb mass' is a positive number
        if "curb mass" in vehicle and not isinstance(vehicle["curb mass"], (int, float)):
            errors.append(f"Vehicle {v} has invalid curb mass value: {vehicle['curb mass']} (must be a number)")
        elif "curb mass" in vehicle and vehicle["curb mass"] <= 0:
            errors.append(f"Vehicle {v} has: curb mass must be greater than 0.")

        # Check if 'cargo mass' is a positive number
        if "cargo mass" in vehicle and not isinstance(vehicle["cargo mass"], (int, float)):
            errors.append(f"Vehicle {v} has invalid cargo mass value: {vehicle['cargo mass']} (must be a number)")
        elif "cargo mass" in vehicle and vehicle["cargo mass"] <= 0:
            errors.append(f"Vehicle {v}: cargo mass must be greater than 0.")

        # Check if 'driving mass' is a positive number
        if "driving mass" in vehicle and not isinstance(vehicle["driving mass"], (int, float)):
            errors.append(f"Vehicle {v} has has invalid driving mass value: {vehicle['driving mass']} (must be a number)")
        elif "driving mass" in vehicle and vehicle["driving mass"] <= 0:
            errors.append(f"Vehicle {v}: driving mass must be greater than 0.")

        # Check if engine powers are valid numbers
        if "engine power" in vehicle and not isinstance(vehicle["engine power"], (int, float)):
            errors.append(f"Vehicle {v} has invalid engine power value: {vehicle['engine power']} (must be a number)")

        if "total engine power" in vehicle and not isinstance(vehicle["total engine power"], (int, float)):
            errors.append(f"Vehicle {v} has invalid total engine power value: {vehicle['total engine power']} (must be a number)")

        # Check if 'fuel tank volume' is a valid number
        if "fuel tank volume" in vehicle and not isinstance(vehicle["fuel tank volume"], (int, float)):
            errors.append(f"Vehicle {v} has invalid fuel tank mass value: {vehicle['fuel tank volume']} (must be a number)")

        # Check if `battery type` is valid
        if "battery technology" in vehicle and vehicle["battery technology"] not in vehicle_mapping["battery"]:
            errors.append(
                f"Vehicle {v} has invalid battery type value: {vehicle['battery technology']}. Should be one of {vehicle_mapping['battery']}"
            )

        # Check if 'battery capacity' is a valid number
        if "battery capacity" in vehicle and not isinstance(vehicle["battery capacity"], (int, float)):
            errors.append(f"Vehicle {v} has invalid battery capacity value: {vehicle['battery capacity']} (must be a number)")
        elif "battery capacity" in vehicle and vehicle["battery capacity"] <= 0:
            errors.append(f"Vehicle {v}: battery capacity must be greater than 0.")

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

def translate_swisscargo_to_carculator(data: dict) -> dict:
    """
    Translates the SwissCargo nomenclature to the Carculator nomenclature.
    :param data: data to translate
    :return: translated data
    """

    for vehicle in data["vehicles"]:
        if "size" in vehicle:
            if vehicle["size"] in SWISSCARGO_SIZE:
                vehicle["size"] = SWISSCARGO_SIZE[vehicle["size"]]

    return data



def translate_tcs_to_carculator(data: dict) -> dict:
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

        new_vehicle["TtW energy"] = 0
        # fuel consumption, in L/100 km
        if "ver" in vehicle:
            new_vehicle["fuel consumption"] = vehicle["ver"]
            new_vehicle["TtW energy"] += int(new_vehicle["fuel consumption"] * FUEL_SPECS[new_vehicle["powertrain"]]["lhv"] * 1000 / 100)

        if "ver_strom" in vehicle:
            new_vehicle["electricity consumption"] = vehicle["ver_strom"]
            new_vehicle["TtW energy"] += int(new_vehicle["electricity consumption"] * 3.6 * 1000 / 100)

        if not any(x in vehicle for x in ["ver", "ver_strom"]):
            if "ver_abs" in vehicle:
                if new_vehicle["powertrain"] == "BEV":
                    new_vehicle["electricity consumption"] = vehicle["ver_abs"]
                else:
                    new_vehicle["fuel consumption"] = vehicle["ver_abs"]

                if new_vehicle["powertrain"] == "BEV":
                    new_vehicle["TtW energy"] = int(new_vehicle["fuel consumption"] * 3.6 * 1000 / 100)
                else:
                    new_vehicle["TtW energy"] = int(new_vehicle["fuel consumption"] * FUEL_SPECS[new_vehicle["powertrain"]]["lhv"] * 1000 / 100)

        # add other entries not in the mapping
        for k, v in vehicle.items():
            if k not in TCS_PARAMETERS:
                new_vehicle[k] = v

        translated_data.append(new_vehicle)

    data["vehicles"] = translated_data

    return data


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
        data = translate_tcs_to_carculator(data)

    if data.get("nomenclature") == "swisscargo":
        data = translate_swisscargo_to_carculator(data)

    errors = validate_input_data(data)

    return data, errors
