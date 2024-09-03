from flask import Blueprint, request, jsonify
from .validation import validate
# from .lca import (
#     extract_vehicle_parameters,
#     initialize_car_model,
#     set_vehicle_properties,
#     calculate_lca_results,
#     format_response
# )
from .validation import validate_input_data

main = Blueprint('main', __name__)


@main.route('/calculate-lca', methods=['POST'])
def calculate_lca():
    """
    This function receives the input data from the user, validates it, and calculates the LCA results.
    :return: JSON response
    """
    data = request.json

    # Validate the received data
    data, validation_errors = validate(data)
    if validation_errors:
        return jsonify({"error": "Invalid input data", "details": validation_errors}), 400

    # vehicle_params = extract_vehicle_parameters(data)
    #
    # car_model = initialize_car_model(vehicle_params)
    # set_vehicle_properties(car_model, vehicle_params)
    #
    # lca_results = calculate_lca_results(car_model, vehicle_params)
    #
    # response = format_response(lca_results)
    #
    # return jsonify(response)

    # return basic OK
    return jsonify({"message": "OK"}), 200


