from flask import Blueprint, request, jsonify, Response
import time

from .input_validation import validate_input
from .lca import initialize_model
from .formatting import format_results_for_tcs, format_results_for_swisscargo
from .swiss_cargo_costs import calculate_lsva_charge_period, canton_truck_tax
import json
import numpy as np

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
    start = time.monotonic()
    deadline = start + 28.0

    data = request.json

    ai_compare = bool((data or {}).get("ai_compare", False))
    ai_language = (data or {}).get("language") or (
        (request.headers.get("Accept-Language") or "en").split(",")[0].split("-")[0]
    )

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

    cost_results_parameters = [
        "energy cost",
        "energy infrastructure cost",
        "amortised purchase cost",
        "maintenance cost",
        "insurance cost",
        "toll cost",
        "CO2 tax cost",
        "amortised component replacement cost",
        "amortised residual credit",
    ]

    if data.get("nomenclature") == "swisscargo":
        default_vehicle_parameters.extend([
            "energy cost per kWh (depot)",
            "energy cost per kWh (public)",
            "share depot charging",
            "interest rate",
            "battery onboard charging infrastructure cost",
            "combustion exhaust treatment cost",
            "combustion powertrain cost",
            "electric powertrain cost",
            "energy battery cost",
            "fuel cell cost",
            "fuel tank cost",
            "glider cost",
            "heat pump cost",
            "lightweighting cost",
            "power battery cost",
            "purchase cost",
        ])

    import gc

    for vehicle in data["vehicles"]:
        model, errors = initialize_model(vehicle, data.get("nomenclature"))
        if errors:
            return jsonify({"error": "Output validation issues", "details": errors}), 500

        # --- compute results just like before ---
        if data.get("nomenclature") == "tcs":
            vehicle["results_ecoinvent"] = format_results_for_tcs(data=model, params=vehicle)
            for k, v in vehicle["results_ecoinvent"].items():
                if not np.isfinite(v):
                    vehicle["results_ecoinvent"][k] = 0.0
            vehicle["results_bafu"] = format_results_for_tcs(data=model, params=vehicle, bafu=True)
            for k, v in vehicle["results_bafu"].items():
                if not np.isfinite(v):
                    vehicle["results_bafu"][k] = 0.0

        elif data.get("nomenclature") == "swisscargo":
            vehicle["results"] = format_results_for_swisscargo(data=model, params=vehicle)
            # add cost results
            factor = 1 if model.inventory.func_unit == "vkm" else (1 / (model.array.sel(parameter="cargo mass").values.item() / 1000))

            vehicle["cost_results"] = {
                p: model.array.sel(parameter=p).mean().values.item() * factor for p in cost_results_parameters
            }

            # we need to figure out what was provided by the user (in CHF)
            # and what need to be converted from EUR to CHF
            eur_to_chf = 0.94
            for cost_type in cost_results_parameters:
                if cost_type == "energy cost":
                    continue
                if cost_type == "amortised purchase cost":
                    if "purchase cost" in vehicle and vehicle["purchase cost"] > 0:
                        continue
                    else:
                        eu_to_ch_price_levels_difference = 1.3  # EUR prices are lower than CHF prices
                        vehicle["cost_results"][cost_type] *= eur_to_chf
                        vehicle["cost_results"][cost_type] *= eu_to_ch_price_levels_difference

                        costs = [
                            "battery onboard charging infrastructure cost",
                            "combustion exhaust treatment cost",
                            "combustion powertrain cost",
                            "electric powertrain cost",
                            "energy battery cost",
                            "fuel cell cost",
                            "fuel tank cost",
                            "glider cost",
                            "heat pump cost",
                            "lightweighting cost",
                            "power battery cost",
                            "purchase cost"
                        ]
                        model.array.loc[dict(parameter=costs)] *= eu_to_ch_price_levels_difference
                        model.array.loc[dict(parameter=costs)] *= eur_to_chf

                if cost_type == "maintenance cost":
                    if "maintenance cost" in vehicle and vehicle["maintenance cost"] > 0:
                        continue
                    else:
                        eu_to_ch_price_levels_difference = 1.3  # EUR prices are lower than CHF prices
                        vehicle["cost_results"][cost_type] *= eur_to_chf
                        vehicle["cost_results"][cost_type] *= eu_to_ch_price_levels_difference
                        model.array.loc[dict(parameter="maintenance cost")] *= eu_to_ch_price_levels_difference
                        model.array.loc[dict(parameter="maintenance cost")] *= eur_to_chf

                if cost_type == "insurance cost":
                    if "insurance cost" in vehicle and vehicle["insurance cost"] > 0:
                        continue
                    else:
                        eu_to_ch_price_levels_difference = 1.3  # EUR prices are lower than CHF prices
                        vehicle["cost_results"][cost_type] *= eur_to_chf
                        vehicle["cost_results"][cost_type] *= eu_to_ch_price_levels_difference
                        model.array.loc[dict(parameter="insurance cost")] *= eu_to_ch_price_levels_difference
                        model.array.loc[dict(parameter="insurance cost")] *= eur_to_chf

                if cost_type == "amortised component replacement cost":
                    if vehicle["powertrain"] in ("BEV", "FCEV"):
                        if vehicle.get("replacement_cost_included", False) is False:
                            # we assume the components replacement cost is borne by the next owner
                            # hence we zero it out here
                            vehicle["cost_results"][cost_type] = 0.0

            lsva_costs = calculate_lsva_charge_period(vehicle)

            # add LSVA/RPLP road charge calculation
            vehicle["cost_results"]["CO2 tax cost"] =  lsva_costs["cost_per_km_chf"] * factor
            vehicle["road charge details"] = lsva_costs

            # add cantonal road charge
            canton_road_charge = canton_truck_tax(vehicle)
            vehicle["cost_results"]["canton road charge cost"] = canton_road_charge["chf_per_km"] * factor
            vehicle["canton tax details"] = canton_road_charge

        else:
            vehicle["results"] = serialize_xarray(model.results)

        # harvest parameters
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

        if data.get("nomenclature", "carculator") in ("swisscargo", "tcs"):
            vehicle["LCA background database"] = "UVEK 2022"
        else:
            vehicle["LCA background database"] = f"ecoinvent - cutoff - {model.ecoinvent_version}"
        vehicle["country"] = data["country_code"]

        # --- free memory NOW ---
        del model
        gc.collect()

    if ai_compare and data.get("nomenclature") == "swisscargo":
        payload = build_compare_payload_swisscargo(data["vehicles"], include_stage_shares=False)

        RESPONSE_BUFFER = 8.0  # time to JSON, send, jitter
        MIN_AI_BUDGET = 4.0  # won't call AI unless we can give this much
        remaining = deadline - time.monotonic()
        ai_budget = remaining - RESPONSE_BUFFER

        if ai_budget >= MIN_AI_BUDGET:
            ai_timeout = min(7.5, ai_budget)  # allow up to ~7.5 s
            data["ai_comparison"] = ai_compare_across_vehicles_swisscargo(
                payload, language=ai_language, detail="compact", timeout_s=ai_timeout
            )
            data["ai_timing"] = {
                "remaining_before_ai_s": round(remaining, 2),
                "ai_budget_s": round(ai_timeout, 2)
            }  # keep while debugging
        else:
            data["ai_comparison_note"] = (
                f"Skipped AI (remaining={remaining:.2f}s, needs ≥{MIN_AI_BUDGET + RESPONSE_BUFFER:.1f}s)."
            )

    return Response(
        json.dumps(data, indent=2, sort_keys=False),  # Serialize using the ordered structure
        status=200,
        mimetype='application/json',
    )

def serialize_xarray(data):
    """
    Turn xarray into a nested dictionary, which can be serialized to JSON.
    :param data: xarray
    :return: dict
    """
    return data.to_dict()
