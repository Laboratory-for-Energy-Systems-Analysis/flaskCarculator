from flask import Blueprint, current_app, request, jsonify, Response
from .input_validation import validate_input
from .lca import initialize_model
from .formatting import format_results_for_tcs, format_results_for_swisscargo
import json
import numpy as np

main = Blueprint('main', __name__)


@main.route('/calculate-lca', methods=['POST'])
def calculate_lca():
    """
    This function receives the input data from the user, validates it, and calculates the LCA results.
    :return: JSON response
    """
    data = request.get_json(silent=True)

    if data is None:
        return jsonify(
            {
                "error": "Invalid JSON payload",
                "details": [
                    "Request body must be valid JSON with Content-Type application/json."
                ],
            }
        ), 400

    vehicles = data.get("vehicles") if isinstance(data, dict) else None
    max_vehicles = current_app.config.get("MAX_VEHICLES_PER_REQUEST")
    if isinstance(vehicles, list) and max_vehicles and len(vehicles) > max_vehicles:
        return jsonify(
            {
                "error": "Too many vehicles",
                "details": [
                    f"At most {max_vehicles} vehicles can be processed in one request."
                ],
            }
        ), 413

    # Validate the received data
    data, validation_errors = validate_input(data)
    if len(validation_errors) > 0:
        return jsonify({"error": "Invalid input data", "details": validation_errors}), 400

    try:
        for vehicle in data["vehicles"]:
            model = initialize_model(vehicle, data.get("nomenclature"))

            if data.get("nomenclature") == "tcs":
                vehicle["results_ecoinvent"] = format_results_for_tcs(
                    data=model,
                    params=vehicle
                )
                vehicle["results_bafu"] = format_results_for_tcs(
                    data=model,
                    params=vehicle,
                    bafu=True
                )
            elif data.get("nomenclature") == "swisscargo":
                vehicle["results"] = format_results_for_swisscargo(
                    data=model,
                )
            else:
                vehicle["results"] = serialize_xarray(model.results)

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

            for p in default_vehicle_parameters:
                if p in model.array.parameter.values:
                    val = model.array.sel(parameter=p).mean().values.item()
                    if not np.isfinite(val):  # Detects NaN, inf, -inf
                        val = 0.0
                    vehicle[p] = val


            vehicle["battery chemistry"] = list(model.energy_storage["electric"].values())[0]
            vehicle["indicators"] = model.inventory.method
            vehicle["indicator type"] = model.inventory.indicator
            vehicle["scenario"] = model.inventory.scenario
            vehicle["functional unit"] = model.inventory.func_unit
            vehicle["scenario"] = model.inventory.scenario
            vehicle["carculator version"] = ".".join(map(str, model.version))
            vehicle["ecoinvent version"] = model.ecoinvent_version

            del model

    except Exception as e:
        return jsonify({"error": "An error occurred", "details": str(e)}), 500


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
