from flask import Blueprint, request, jsonify, Response
import time

from .input_validation import validate_input
from .lca import initialize_model
from .formatting import format_results_for_tcs, format_results_for_swisscargo
import json
import numpy as np
from collections import OrderedDict

from .ai_commentary import ai_compare_across_vehicles_swisscargo
from .ai_extract import build_compare_payload_swisscargo


main = Blueprint('main', __name__)

@main.route("/")
def home():
    return "FlaskCarculator is running!"


@main.route('/calculate-lca', methods=['POST'])
def calculate_lca():
    """
    This function receives the input data from the user, validates it, and calculates the LCA results.
    :return: JSON response
    """
    deadline = time.time() + 24.0  # leave ~6s headroom for Heroku’s 30s

    data = request.json

    ai_compare = bool((data or {}).get("ai_compare", False))
    ai_language = (data or {}).get("language") or (
        (request.headers.get("Accept-Language") or "en").split(",")[0].split("-")[0]
    )

    from pprint import pprint
    pprint(data)

    # Validate the received data
    data, validation_errors = validate_input(data)
    if len(validation_errors) > 0:
        return jsonify({"error": "Invalid input data", "details": validation_errors}), 400

    default_vehicle_parameters = [
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
        "glider base mass",
        "lightweighting",
        "suspension mass",
        "braking system mass",
        "wheels and tires mass",
        "cabin mass",
        "electrical system mass",
        "other components mass",
        "transmission mass",
        "fuel mass",
        "charger mass",
        "converter mass",
        "inverter mass",
        "power distribution unit mass",
        "combustion engine mass",
        "electric engine mass",
        "powertrain mass",
        "exhaust system mass",
        "fuel cell stack mass",
        "fuel cell ancillary BoP mass",
        "fuel cell essential BoP mass",
        "fuel cell lifetime replacements",
        "battery cell mass",
        "battery BoP mass",
        "energy battery mass",
        "fuel tank mass",
        "curb mass",
        "cargo mass",
        "total cargo mass",
        "driving mass",
        "gross mass",

    ]

    if data.get("nomenclature") == "swisscargo":
        default_vehicle_parameters.extend([
            "glider cost",
            "lightweighting cost",
            "electric powertrain cost",
            "combustion powertrain cost",
            "fuel cell cost",
            "fuel cell cost per kW",
            "power battery cost",
            "energy battery cost",
            "energy battery cost per kWh",
            "tank cost",
            "fuel tank cost per kg",
            "energy cost per kWh",
            "purchase cost",
            "energy cost",
            "amortised purchase cost",
            "maintenance cost",
            "amortised component replacement cost"
        ])

    import gc

    for vehicle in data["vehicles"]:
        model, errors = initialize_model(vehicle, data.get("nomenclature"))
        if errors:
            return jsonify({"error": "Output validation issues", "details": errors}), 500

        # --- compute results just like before ---
        if data.get("nomenclature") == "tcs":
            vehicle["results_ecoinvent"] = format_results_for_tcs(data=model, params=vehicle)
            vehicle["results_bafu"] = format_results_for_tcs(data=model, params=vehicle, bafu=True)
        elif data.get("nomenclature") == "swisscargo":
            vehicle["results"] = format_results_for_swisscargo(data=model, params=vehicle)
        else:
            vehicle["results"] = serialize_xarray(model.results)

        # harvest parameters (unchanged logic, but read from `model`)
        for p in default_vehicle_parameters:
            if p in model.array.parameter.values:
                if p in ("fuel consumption", "electricity consumption"):
                    val = model.array.sel(parameter=p).mean().values.item() * 100
                else:
                    val = model.array.sel(parameter=p).mean().values.item()
                if not np.isfinite(val):
                    val = 0.0
                vehicle[p] = val

        vehicle["battery chemistry"] = list(model.energy_storage["electric"].values())[0]
        vehicle["indicators"] = model.inventory.method
        vehicle["indicator type"] = model.inventory.indicator
        vehicle["scenario"] = model.inventory.scenario
        vehicle["functional unit"] = model.inventory.func_unit

        carculator_model_labels = {
            "truck": "carculator_truck",
            "car": "carculator",
            "bus": "carculator_bus",
            "two-wheeler": "carculator_two_wheeler"
        }
        vehicle[f"{carculator_model_labels[vehicle['vehicle_type']]} version"] = ".".join(map(str, model.version))
        vehicle["ecoinvent version"] = model.ecoinvent_version
        vehicle["country"] = data["country_code"]

        # --- free memory NOW ---
        del model
        gc.collect()

    if ai_compare and data.get("nomenclature") == "swisscargo":
        try:
            payload = build_compare_payload_swisscargo(data["vehicles"], include_stage_shares=True)
            remaining = max(3.0, deadline - time.time())  # seconds left for AI
            if remaining < 4.0:
                data["ai_comparison_note"] = "Skipped AI comparison to avoid timeout."
            else:
                data["ai_comparison"] = ai_compare_across_vehicles_swisscargo(
                    payload, language=ai_language, detail="compact", timeout_s=min(10.0, remaining - 1.0)
                )
        except Exception as e:
            data["ai_comparison_error"] = str(e)



    return Response(
        json.dumps(data, indent=2, sort_keys=False),  # Serialize using the ordered structure
        status=200,
        mimetype='application/json',
    )

def serialize_xarray(data):
    """
    Turn xarray into nested dictionary, which cna be serialized to JSON.
    :param data: xarray
    :return: dict
    """
    return data.to_dict()
