from flask import Blueprint, request, jsonify, after_this_request, Response
from .input_validation import validate_input
from .lca import initialize_model
from .formatting import format_results_for_tcs, format_results_for_swisscargo
import json
from collections import OrderedDict

main = Blueprint('main', __name__)


@main.route('/calculate-lca', methods=['POST'])
def calculate_lca():
    """
    This function receives the input data from the user, validates it, and calculates the LCA results.
    :return: JSON response
    """
    data = request.json

    # Validate the received data
    data, validation_errors = validate_input(data)
    if len(validation_errors) > 0:
        return jsonify({"error": "Invalid input data", "details": validation_errors}), 400

    models = {vehicle["id"]: initialize_model(vehicle) for vehicle in data["vehicles"]}

    try:
        for vehicle in data["vehicles"]:
            if data.get("nomenclature") == "tcs":
                vehicle["results"] = format_results_for_tcs(
                    data=models[vehicle["id"]],
                )
            elif data.get("nomenclature") == "swisscargo":
                vehicle["results"] = format_results_for_swisscargo(
                    data=models[vehicle["id"]],
                )
            else:
                vehicle["results"] = serialize_xarray(models[vehicle["id"]].results)

            default_vehicle_parameters = [
                "lifetime kilometers",
                "kilometers per year",
                "curb mass",
                "cargo mass",
                "total cargo mass",
                "capacity utilization",
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
            ]

            for p in default_vehicle_parameters:
                if p in models[vehicle["id"]].array.parameter.values:
                    vehicle[p] = models[vehicle["id"]].array.sel(parameter=p).values.item()

            vehicle["battery chemistry"] = list(models[vehicle["id"]].energy_storage["electric"].values())[0]
            vehicle["indicators"] = models[vehicle["id"]].inventory.method
            vehicle["indicator type"] = models[vehicle["id"]].inventory.indicator
            vehicle["scenario"] = models[vehicle["id"]].inventory.scenario
            vehicle["functional unit"] = models[vehicle["id"]].inventory.func_unit
            vehicle["scenario"] = models[vehicle["id"]].inventory.scenario
            vehicle["carculator version"] = "-".join(list(models[vehicle["id"]].version))
            vehicle["ecoinvent version"] = models[vehicle["id"]].ecoinvent_version

        # Clean up memory after the response is sent
        @after_this_request
        def cleanup(response):
            nonlocal models
            models.clear()  # Clear the dictionary to release memory
            del models  # Explicitly delete the variable
            return response

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
