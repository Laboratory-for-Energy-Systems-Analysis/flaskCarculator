"""
Load all the mapping data from the YAML files in teh same folder
as this module.
"""

from pathlib import Path
import yaml

DATA_DIR: Path = Path(__file__).resolve().parent


def load_yaml(file_name: str) -> dict:
    with open(DATA_DIR / file_name, "r") as file:
        return yaml.safe_load(file)


TCS_FUEL_BLEND = load_yaml("tcs_fuel_blend.yaml")
TCS_PARAMETERS = load_yaml("tcs_parameters_mapping.yaml")
TCS_POWERTRAIN = load_yaml("tcs_powertrain_mapping.yaml")
TCS_SIZE = load_yaml("tcs_size_mapping.yaml")
CAR_POWERTRAINS = load_yaml("car/powertrain.yaml")
CAR_SIZES = load_yaml("car/size.yaml")
CAR_BATTERIES = load_yaml("car/battery.yaml")
