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
SWISSCARGO_SIZE = load_yaml("swisscargo_size_mapping.yaml")
FUEL_SPECS = load_yaml("fuel_specs.yaml")
TCS_IMPACTS_MAPPING = load_yaml("tcs_impacts_mapping.yaml")
BAFU_EMISSSION_FACTORS = load_yaml("bafu_emission_factors.yaml")
CAR_POWERTRAINS = load_yaml("car/powertrain.yaml")
CAR_SIZES = load_yaml("car/size.yaml")
CAR_BATTERIES = load_yaml("car/battery.yaml")
TRUCK_POWERTRAINS = load_yaml("truck/powertrain.yaml")
TRUCK_SIZES = load_yaml("truck/size.yaml")
TRUCK_BATTERIES = load_yaml("truck/battery.yaml")
BUS_POWERTRAINS = load_yaml("bus/powertrain.yaml")
BUS_SIZES = load_yaml("bus/size.yaml")
BUS_BATTERIES = load_yaml("bus/battery.yaml")
