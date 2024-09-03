"""
This module contains functions to validate the input data.
"""

from .data.mapping import TCS_FUEL_BLEND, TCS_SIZE, TCS_PARAMETERS, TCS_POWERTRAIN, CAR_POWERTRAINS, CAR_SIZES, \
    CAR_BATTERIES


def get_mapping(vehicle_type: str) -> dict:
    """
    Returns the mapping for the given vehicle type.
    :param vehicle_type: vehicle type
    :return: mapping
    """
    mappings = {
        "car": {
            "powertrain": CAR_POWERTRAINS,
            "size": CAR_SIZES,
            "battery": CAR_BATTERIES,
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
        "car_id",
        "vehicle_type",
        "powertrain",
        "year",
        "size"
    ]

    errors = []

    for vehicle in data["vehicles"]:
        vehicle_errors = []
        for field in required_fields:
            if field not in vehicle:
                vehicle_errors.append(f"Missing required field: {field}")

        vehicle_mapping = get_mapping(vehicle["vehicle_type"])

        # Check if 'size' is valid
        if vehicle.get("size") not in vehicle_mapping["size"]:
            vehicle_errors.append(
                f"Invalid size value: {vehicle['size']}. Should be one of {vehicle_mapping['size'].keys()}"
            )

        # Check if 'powertrain' is valid
        if vehicle.get("powertrain") not in vehicle_mapping["powertrain"]:
            vehicle_errors.append(
                f"Invalid powertrain value: {vehicle['powertrain']}. Should be one of {vehicle_mapping['powertrain'].keys()}"
            )

        # Check if 'curb mass' is a positive number
        if "curb mass" in vehicle and not isinstance(vehicle["curb mass"], (int, float)):
            errors.append(f"Invalid curb mass value: {vehicle['curb mass']} (must be a number)")
        elif "curb mass" in vehicle and vehicle["curb mass"] <= 0:
            errors.append(f"curb must be greater than 0.")

        # Check if 'cargo mass' is a positive number
        if "cargo mass" in vehicle and not isinstance(vehicle["cargo mass"], (int, float)):
            errors.append(f"Invalid cargo mass value: {vehicle['cargo mass']} (must be a number)")
        elif "cargo mass" in vehicle and vehicle["cargo mass"] <= 0:
            errors.append(f"cargo mass must be greater than 0.")

        # Check if 'driving mass' is a positive number
        if "driving mass" in vehicle and not isinstance(vehicle["driving_mass"], (int, float)):
            errors.append(f"Invalid driving mass value: {vehicle['driving mass']} (must be a number)")
        elif "driving mass" in vehicle and vehicle["driving mass"] <= 0:
            errors.append(f"driving mass must be greater than 0.")

        # Check if engine powers are valid numbers
        if "engine power" in vehicle and not isinstance(vehicle["engine power"], (int, float)):
            errors.append(f"Invalid engine power value: {vehicle['engine power']} (must be a number)")

        if "total engine power" in vehicle and not isinstance(vehicle["total engine power"], (int, float)):
            errors.append(f"Invalid total engine power value: {vehicle['total engine power']} (must be a number)")

        # Check if 'fuel_tank_mass' is a valid number
        if "fuel tank mass" in vehicle and not isinstance(vehicle["fuel tank mass"], (int, float)):
            errors.append(f"Invalid fuel tank mass value: {vehicle['fuel tank mass']} (must be a number)")

        # Check if `battery type` is valid
        if "battery type" in vehicle and vehicle["battery type"] not in vehicle_mapping["battery"]:
            errors.append(
                f"Invalid battery type value: {vehicle['battery type']}. Should be one of {vehicle_mapping['battery'].keys()}"
            )

        # Check if 'battery capacity' is a valid number
        if "battery capacity" in vehicle and not isinstance(vehicle["battery capacity"], (int, float)):
            errors.append(f"Invalid battery capacity value: {vehicle['battery capacity']} (must be a number)")
        elif "battery capacity" in vehicle and vehicle["battery capacity"] <= 0:
            errors.append(f"battery capacity must be greater than 0.")

        # Check if 'range' is a valid number
        if "range" in vehicle and not isinstance(vehicle["range"], (int, float)):
            errors.append(f"Invalid range value: {vehicle['range']} (must be a number)")
        elif "range" in vehicle and vehicle["range"] <= 0:
            errors.append(f"range must be greater than 0.")

        # Check if 'TtW energy' (energy use, in kj) is a valid number
        if "TtW energy" in vehicle and not isinstance(vehicle["TtW energy"], (int, float)):
            errors.append(f"Invalid TtW energy value: {vehicle['TtW energy']} (must be a number)")
        elif "TtW energy" in vehicle and vehicle["TtW energy"] <= 0:
            errors.append(f"TtW energy must be greater than 0.")

    return errors


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

        # add other entries not in the mapping
        for k, v in vehicle.items():
            if k not in TCS_PARAMETERS:
                new_vehicle[k] = v

        translated_data.append(new_vehicle)

        print(translated_data)

    data["vehicles"] = translated_data

    return data


def validate(data: dict) -> [list, list]:
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

    errors = validate_input_data(data)

    return data, errors
