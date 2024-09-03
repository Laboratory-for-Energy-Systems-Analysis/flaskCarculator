from flask import Blueprint, request, jsonify
from .validation import validate_input
from .lca import initialize_model


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

    print(models)

    # set_vehicle_properties(car_model, vehicle_params)
    #
    # lca_results = calculate_lca_results(car_model, vehicle_params)
    #
    # response = format_response(lca_results)
    #
    # return jsonify(response)

    # return basic OK
    return jsonify({"message": "OK"}), 200


