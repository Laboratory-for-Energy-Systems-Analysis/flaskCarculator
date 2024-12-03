from flask import Blueprint, request, jsonify
from .input_validation import validate_input
from .lca import initialize_model
from .formatting import format_results_for_tcs

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

    models = {params["id"]: initialize_model(params) for params in data["vehicles"]}

    for vehicle in data["vehicles"]:
        if data.get("nomenclature") == "tcs":
            vehicle["results"] = format_results_for_tcs(models[vehicle["id"]].results)
        else:
            vehicle["results"] = serialize_xarray(models[vehicle["id"]].results)

    return jsonify(data), 200

def serialize_xarray(data):
    """
    Turn xarray into nested dictionary, which cna be serialized to JSON.
    :param data: xarray
    :return: dict
    """
    return data.to_dict()
