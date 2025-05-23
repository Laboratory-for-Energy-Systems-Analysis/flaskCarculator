import numpy as np
import pandas as pd
from carculator import CarInputParameters, CarModel, fill_xarray_from_input_parameters, InventoryCar
from carculator import __version__ as carculator_version
from carculator_truck import TruckInputParameters, TruckModel, InventoryTruck
from carculator_truck import __version__ as carculator_truck_version
from carculator_bus import BusInputParameters, BusModel, InventoryBus
from carculator_bus import __version__ as carculator_bus_version
from carculator_two_wheeler import TwoWheelerInputParameters, TwoWheelerModel, InventoryTwoWheeler
from carculator_two_wheeler import __version__ as carculator_two_wheeler_version

from .data.mapping import FUEL_SPECS, DATA_DIR
from .output_validation import validate_output_data


models = {
    "car": {
        "model": CarModel,
        "inventory": InventoryCar,
        "input_parameters": CarInputParameters,
        "version": carculator_version,
        "ecoinvent version": "3.10.0"
    },
    "truck": {
        "model": TruckModel,
        "inventory": InventoryTruck,
        "input_parameters": TruckInputParameters,
        "version": carculator_truck_version,
        "ecoinvent version": "3.10.0"
    },
    "bus": {
        "model": BusModel,
        "inventory": InventoryBus,
        "input_parameters": BusInputParameters,
        "version": carculator_bus_version,
        "ecoinvent version": "3.10.0"
    },
    "two_wheeler": {
        "model": TwoWheelerModel,
        "inventory": InventoryTwoWheeler,
        "input_parameters": TwoWheelerInputParameters,
        "version": carculator_two_wheeler_version,
        "ecoinvent version": "3.10.0"
    }
}

def load_bafu_emission_factors():
    """
    Load the BAFU emission factors from the CSV file.
    """
    # Assuming the CSV file is in the same directory as this script
    filepath = DATA_DIR / "bafu_emission_factors" / "scores.xlsx"

    return pd.read_excel(filepath)


def set_combustion_power_share(array, params):
    """
    Sets the combustion power share in the array based on the powertrain type.
    """
    if params["powertrain"] in ["HEV-d", "HEV-p"] and all(x in params for x in ["primary_engine_power", "total_engine_power"]):
        array.loc[dict(parameter="combustion power share")] = params["primary_engine_power"] / params["total_engine_power"]
    elif params["powertrain"] in ["ICEV-d", "ICEV-p", "ICEV-g"]:
        array.loc[dict(parameter="combustion power share")] = 1
    elif params["powertrain"] in ["BEV", "FCEV"]:
        array.loc[dict(parameter="combustion power share")] = 0

    return array


def set_vehicle_properties_before_run(model, params):
    """
    Sets various properties of the vehicle model based on the provided parameters.
    """
    if params.get("fuel tank volume", 0) > 0:
        fuel_density = FUEL_SPECS[params["powertrain"]]["density"]
        model.array.loc[dict(parameter="fuel mass")] = params["fuel tank volume"] * fuel_density

    return model


def set_vehicle_properties_after_run(model, params):
    """
    Sets various properties of the vehicle model based on the provided parameters.
    """

    if params.get("driving mass", 0) > 0:
        model.array.loc[dict(parameter="driving mass")] = params["driving mass"]

    if params.get("TtW energy", 0) > 0:
        model.array.loc[dict(parameter="TtW energy")] = params["TtW energy"]

    if params.get("fuel consumption", 0) > 0:
        model.array.loc[dict(parameter="fuel consumption")] = params["fuel consumption"] / 100
        model.array.loc[dict(parameter="TtW energy, combustion mode")] = (params["fuel consumption"] / 100) * 42600

    if params.get("electricity consumption", 0) > 0:
        model.array.loc[dict(parameter="electricity consumption")] = params["electricity consumption"] / 100
        model.array.loc[dict(parameter="TtW energy, electric mode")] = params["electricity consumption"] / 100 * 3600

    if params.get("range", 0) > 0:
        model.array.loc[dict(parameter="range")] = params["range"]

    if params.get("cargo mass", None):
        model.array.loc[dict(parameter="cargo mass")] = params["cargo mass"]
        model.array.loc[dict(parameter="total cargo mass")] = params["cargo mass"]

    return model

def set_properties_for_plugin(model, params):
    """
    Sets various properties of the vehicle model based on the provided parameters.
    :param model:
    :param params:
    :return:
    """
    if "electricity consumption" in params:
        model.array.loc[dict(powertrain=params["powertrain"], parameter="electricity consumption")] = params["electricity consumption"] / 100
    if "fuel consumption" in params:
        model.array.loc[dict(powertrain=params["powertrain"], parameter="fuel consumption")] = params["fuel consumption"] / 100
    if "TtW energy" in params:
        model.array.loc[dict(powertrain=params["powertrain"], parameter="TtW energy")] = params["TtW energy"]
    if "electric energy stored" in params:
        model.array.loc[dict(powertrain=params["powertrain"], parameter="electric energy stored")] = params["electric energy stored"]

    if "curb mass" in params and "powertrain" in params:
        model.array.loc[dict(powertrain=params["powertrain"], parameter="glider base mass")] += (params["curb mass"] - model.array.loc[dict(powertrain=params["powertrain"], parameter="curb mass")])

    if "primary power" in params:
        model.array.loc[dict(powertrain=params["powertrain"], parameter="combustion power")] = params["primary power"]
    if "power" in params and "primary power" in params:
        model.array.loc[dict(powertrain=params["powertrain"], parameter="electric power")] = params["power"] - params["primary power"]
    if "power" in params:
        model.array.loc[dict(powertrain=params["powertrain"], parameter="power")] = params["power"]

    if "driving mass" in params:
        model.array.loc[dict(powertrain=params["powertrain"], parameter="driving mass")] = params["driving mass"]

    model.set_vehicle_mass()
    model.set_component_masses()
    if "driving mass" in params:
        model["driving mass"] = params["driving mass"]

    model.array.loc[dict(parameter="range")] = (
        model.array.loc[dict(parameter="electric energy stored")] * 3600 / model.array.loc[dict(parameter="TtW energy, electric mode")]
    ) + (
        model.array.loc[dict(parameter="oxidation energy stored")] * 3600 / model.array.loc[dict(parameter="TtW energy, combustion mode")]
    )

    return model

def initialize_model(params, nomenclature=None):
    """
    Initializes and returns a CarModel instance with the given parameters.
    """

    input_parameters = models[params["vehicle_type"]]["input_parameters"]

    ip = input_parameters()
    ip.static()

    _, array = fill_xarray_from_input_parameters(
        ip,
        scope={"powertrain": [params["powertrain"]], "size": [params["size"]]}
    )
    array = array.interp(year=[params["year"]], kwargs={'fill_value': 'extrapolate'})
    array = set_combustion_power_share(array, params)

    model = models[params["vehicle_type"]]["model"]

    if params.get("lifetime kilometers", None):
        array.loc[dict(parameter="lifetime kilometers")] = params["lifetime kilometers"]

    annual_mileage = None
    if params.get("kilometers per year", None):
        array.loc[dict(parameter="kilometers per year")] = params["kilometers per year"]
        annual_mileage = {
            (params["powertrain"], params["size"], params["year"]): params["kilometers per year"]
        }

    energy_storage = None
    if params.get("electric energy stored", 0) > 0:
        energy_storage = {
            "capacity": {
                (params["powertrain"], params["size"], params["year"]): params["electric energy stored"]
            },
        }

    if params.get("battery technology", None):
        if energy_storage is None:
            energy_storage = {}
        energy_storage["electric"] = {
            (params["powertrain"], params["size"], params["year"]): params["battery technology"]
        }

    power = None

    if params.get("power", 0) > 0:
        power = {
            (params["powertrain"], params["size"], params["year"]): params["power"]
        }

    target_mass = None
    if params.get("curb mass", 0) > 0:
        target_mass = {
            (params["powertrain"], params["size"], params["year"]): params["curb mass"]
        }

    energy_consumption = None
    if params.get("TtW energy", 0) > 0:
        energy_consumption = {
            (params["powertrain"], params["size"], params["year"]): params["TtW energy"]
        }

    payload = None
    if params.get("payload", 0) > 0:
        payload = {
            (params["powertrain"], params["size"], params["year"]): params["payload"]
        }

        if params["powertrain"] == "PHEV-d":
            payload.update(
                {
                    ("PHEV-c-d", params["size"], params["year"]): params["payload"]
                }
            )
            payload.update(
                {
                    ("PHEV-e", params["size"], params["year"]): params["payload"]
                }
            )
        if params["powertrain"] == "PHEV-p":
            payload.update(
                {
                    ("PHEV-c-p", params["size"], params["year"]): params["payload"]
                }
            )
            payload.update(
                {
                    ("PHEV-e", params["size"], params["year"]): params["payload"]
                }
            )

    target_range = None
    if params.get("target_range", 0) > 0:
        target_range = {
            (params["powertrain"], params["size"], params["year"]): params["target_range"]
        }
        if params["powertrain"] == "PHEV-d":
            target_range.update(
                {
                    ("PHEV-c-d", params["size"], params["year"]): params["target_range"]
                }
            )
            target_range.update(
                {
                    ("PHEV-e", params["size"], params["year"]): params["target_range"]
                }
            )
        if params["powertrain"] == "PHEV-p":
            payload.update(
                {
                    ("PHEV-c-p", params["size"], params["year"]): params["target_range"]
                }
            )
            payload.update(
                {
                    ("PHEV-e", params["size"], params["year"]): params["target_range"]
                }
            )


    if "average passengers" in params:
        array.loc[dict(parameter="average passengers")] = params["average passengers"]

    # build fuel blends
    fuel_blends = {}
    for fuel in [
        "diesel",
        "petrol",
        "methane",
        "hydrogen"
    ]:
        if fuel in params:
            fuel_blends[fuel] = {"primary": {"type": params[fuel], "share": [1.0, ]}}

    cycle = None
    if params.get("cycle", None):
        cycle = params["cycle"]

    uf = None
    if params.get("electric utility factor", None):
        uf = {params["year"]: params["electric utility factor"]}

    m = model(
        array,
        country=params.get("country", "CH"),
        cycle=cycle,
        energy_storage=energy_storage,
        power=power,
        target_mass=target_mass,
        energy_consumption=energy_consumption,
        drop_hybrids=True,
        payload=payload,
        target_range=target_range,
        annual_mileage=annual_mileage,
        fuel_blend=fuel_blends,
        electric_utility_factor=uf,
    )

    m = set_vehicle_properties_before_run(m, params)

    m.set_all()

    if params["powertrain"] in ["PHEV-d", "PHEV-p"]:
        m = set_properties_for_plugin(m, params)


    if params.get("electric energy stored", 0) > 0:
        m["electric energy stored"] = params["electric energy stored"]
        m["battery cell mass"] = m["electric energy stored"] / m["battery cell energy density"]
        m["energy battery mass"] = m["battery cell mass"] / m["battery cell mass share"]
        m["battery BoP mass"] = (
                m["energy battery mass"] - m["battery cell mass"]
        )
        if params["powertrain"] not in ["PHEV-d", "PHEV-p"]:
            var = "target range" if "target range" in m.array.parameter.values else "range"
            m[var] = (
                    m["electric energy stored"]
                    * 3600
                    / m["TtW energy, electric mode"]
            )
            m.set_vehicle_mass()
            m.override_battery_capacity()
            m.calculate_ttw_energy()
            m.drop_hybrid()

            if params.get("range", 0) > 0:
                m.array.loc[dict(parameter="range")] = params["range"]

    m = set_vehicle_properties_after_run(m, params)

    errors = validate_output_data(data=m, request=params)

    if errors:
        raise ValueError(f"Validation failed: {errors}")

    inventory = models[params["vehicle_type"]]["inventory"]

    func_unit = "vkm"
    if "func_unit" in params:
        func_unit = params["func_unit"]

    scenario = "static"
    if "scenario" in params:
        scenario = params["scenario"]

    method = "recipe"
    if "method" in params:
        method = params["method"]

    indicator = "midpoint"
    if "indicator" in params:
        indicator = params["indicator"]

    electricity_mix = None
    if "electricity" in params:

        technology_indices = {
            "hydro": 0,
            "nuclear": 1,
            "gas": 2,
            "solar": 3,
            "wind": 4,
            "biomass": 5,
            "coal": 6,
            "oil": 7,
            "geothermal": 8,
            "waste": 9,
            "biogas_ccs": 10,
            "biomass_ccs": 11,
            "coal_ccs": 12,
            "gas_ccs": 13,
            "wood_ccs": 14,
            "hydro_alpine": 15,
            "gas_ccgt": 16,
            "gas_chp": 17,
            "solar_thermal": 18,
            "wind_offshore": 19,
            "lignite": 20,
        }

        electricity_mix = np.zeros(21)
        electricity_mix[technology_indices[params["electricity"]]] = 1
        electricity_mix = {"custom electricity mix": [electricity_mix]}

    m.inventory = inventory(
        m,
        method=method,
        indicator=indicator,
        scenario=scenario,
        functional_unit=func_unit,
        background_configuration=electricity_mix
    )
    results = m.inventory.calculate_impacts()
    m.results = results.sel(value=0)

    # if nomenclature = "tcs", we want also to provide results
    # using the BFU LCA database

    if nomenclature == "tcs":
        df = load_bafu_emission_factors()
        m.inventory.B.values = np.zeros(m.inventory.B.shape)
        m.inventory.results = None

        for category in [
            "climate change",
            "energy resources: non-renewable",
            "energy resources: renewable",
            "total"
        ]:
            if category != "total":
                factors = df.loc[
                    df["impact"] == category
                ]
            else:
                factors = df.loc[
                    df["impact"] != "climate change"
                ]
                factors = factors.groupby("name").sum(numeric_only=True).reset_index()

            for name in factors["name"].values:
                m.inventory.B.loc[dict(activity=eval(name), category=category)] = factors.loc[factors["name"] == name, "score"].values.item(0)

        results = m.inventory.calculate_impacts()
        m.bafu_results = results.sel(value=0)

    m.version = models[params["vehicle_type"]]["version"]
    m.ecoinvent_version = models[params["vehicle_type"]]["ecoinvent version"]

    # m.inventory.export_lci(format="file", filename=f"lci_{params['id']}.xlsx")

    return m