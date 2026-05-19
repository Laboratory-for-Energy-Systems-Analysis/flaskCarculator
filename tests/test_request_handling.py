from app import create_app
from flaskCarculator.input_validation import validate_input


def make_client(**config):
    app = create_app()
    app.config.update(TESTING=True)
    app.config.update(config)
    return app.test_client()


def test_malformed_json_returns_400():
    client = make_client()

    response = client.post(
        "/calculate-lca",
        data="{",
        content_type="application/json",
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "Invalid JSON payload"


def test_too_many_vehicles_returns_413_before_validation():
    client = make_client(MAX_VEHICLES_PER_REQUEST=2)

    response = client.post(
        "/calculate-lca",
        json={
            "nomenclature": "tcs",
            "country_code": "CH",
            "vehicles": [{}, {}, {}],
        },
    )

    assert response.status_code == 413
    assert response.get_json()["error"] == "Too many vehicles"


def test_invalid_tcs_powertrain_is_rejected_without_model_initialization():
    client = make_client()

    response = client.post(
        "/calculate-lca",
        json={
            "nomenclature": "tcs",
            "country_code": "CH",
            "vehicles": [
                {
                    "id": "bad-tsa",
                    "vehicle_type": "car",
                    "tsa": "UNKNOWN",
                    "year": 2025,
                    "fzklasse": 30004,
                    "leer": 1500,
                    "nutz": 400,
                    "gesamt": 1900,
                    "ver": 6.5,
                }
            ],
        },
    )

    assert response.status_code == 400
    details = response.get_json()["details"]
    assert any("invalid tsa value" in detail for detail in details)


def test_validate_input_returns_errors_for_missing_mandatory_terms():
    _, errors = validate_input({"nomenclature": "tcs"})

    assert errors == [
        "Missing mandatory term: country_code",
        "Missing mandatory term: vehicles",
    ]


def test_validate_input_rejects_non_object_vehicle():
    _, errors = validate_input(
        {
            "nomenclature": "carculator",
            "country_code": "CH",
            "vehicles": ["not-a-vehicle"],
        }
    )

    assert errors == ["Vehicle 0 must be a JSON object."]
