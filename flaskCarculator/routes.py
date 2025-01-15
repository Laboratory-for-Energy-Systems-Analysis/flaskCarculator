from flask import Blueprint, request, jsonify, after_this_request, Response
from .input_validation import validate_input
from .lca import initialize_model
from .formatting import format_results_for_tcs, format_results_for_swisscargo
import json

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
            elif data.get("nomenclature") == "swiss-cargo":
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
                "oxidation energy stored",

            ]

            for p in default_vehicle_parameters:
                if p in models[vehicle["id"]].array.parameter.values:
                    vehicle[p] = models[vehicle["id"]].array.sel(parameter=p).values.item()

            vehicle["indicators"] = models[vehicle["id"]].inventory.method
            vehicle["indicator type"] = models[vehicle["id"]].inventory.indicator
            vehicle["scenario"] = models[vehicle["id"]].inventory.scenario
            vehicle["functional unit"] = models[vehicle["id"]].inventory.func_unit
            vehicle["scenario"] = models[vehicle["id"]].inventory.scenario
            vehicle["carculator version"] = models[vehicle["id"]].version
            vehicle["ecoinvent version"] = models[vehicle["id"]].ecoinvent_version

            # Move "results" key to the end of the dictionary
            results = vehicle.pop("results", None)
            if results is not None:
                vehicle["results"] = results


        # Clean up memory after the response is sent
        @after_this_request
        def cleanup(response):
            nonlocal models
            models.clear()  # Clear the dictionary to release memory
            del models  # Explicitly delete the variable
            return response

    except Exception as e:
        return jsonify({"error": "An error occurred", "details": str(e)}), 500

    # Custom JSON serialization to ensure key order
    def custom_json_encoder(obj):
        if isinstance(obj, dict):
            # Ensure "results" key is the last key
            if "results" in obj:
                reordered = {k: v for k, v in obj.items() if k != "results"}
                reordered["results"] = obj["results"]
                return reordered
        return obj

    # Use the custom encoder for the response
    response_data = json.dumps(data, default=custom_json_encoder)
    return Response(response_data, status=200, mimetype='application/json')

def serialize_xarray(data):
    """
    Turn xarray into nested dictionary, which cna be serialized to JSON.
    :param data: xarray
    :return: dict
    """
    return data.to_dict()
