"""Smoke-test flaskCarculator against the installed carculator stack."""

from __future__ import annotations

import ast
import json
import traceback
from pathlib import Path

import pandas as pd
from app import create_app


ROOT = Path(__file__).resolve().parents[1]


def package_versions() -> None:
    for module_name in [
        "carculator",
        "carculator_utils",
        "carculator_truck",
        "carculator_bus",
        "carculator_two_wheeler",
    ]:
        module = __import__(module_name)
        print(
            f"{module_name}: version={getattr(module, '__version__', 'unknown')} "
            f"path={getattr(module, '__file__', 'unknown')}"
        )


def post_payload(client, name: str, payload: dict) -> bool:
    print(f"\n=== {name} ===")
    response = client.post(
        "/calculate-lca",
        data=json.dumps(payload),
        content_type="application/json",
    )
    print("status:", response.status_code)
    try:
        data = response.get_json()
    except Exception:
        data = None
    if response.status_code != 200:
        print("response:", response.get_data(as_text=True)[:4000])
        return False

    vehicles = data.get("vehicles", [])
    print("vehicles:", len(vehicles))
    for vehicle in vehicles:
        keys = sorted(vehicle.keys())
        result_keys = [key for key in keys if key.startswith("results")]
        print(
            vehicle.get("id"),
            "powertrain=",
            vehicle.get("powertrain"),
            "result_keys=",
            result_keys,
            "carculator version=",
            vehicle.get("carculator version"),
        )
    return True


def load_tcs_py_payload() -> dict:
    module = ast.parse((ROOT / "dev" / "tcs.py").read_text())
    for node in module.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "data":
                    return ast.literal_eval(node.value)
    raise ValueError("Could not find `data` payload in dev/tcs.py")


def build_feed_payloads() -> list[tuple[str, dict]]:
    feed_path = ROOT / "dev" / "feed_2025_02_10_example.csv"
    dataframe = pd.read_csv(feed_path, sep=";", low_memory=False, encoding="latin1")
    payloads = []

    for index, row in dataframe.iterrows():
        vehicle = {
            "id": str(row["FahrzeugId"]),
            "vehicle_type": "car",
            "tsa": row["MotorartcodeCH"],
            "year": 2025,
            "fzklasse": 30004,
            "leer": row["LeergewichtKg"],
            "nutz": row["ZuladungKg"],
            "gesamt": row["GesamtgewichtKg"],
        }

        optional_fields = [
            ("LeistungVerbrennerKw", "kw"),
            ("LeistungKw", "kw_sl"),
            ("TankgroessseKraftstoffart", "tank"),
            ("WltpKombiniertKraftstoffart", "ver"),
            ("AntriebsbatterieKapazitaetBruttoKwh", "bat_cap"),
            ("AntriebsbatterieArt", "bat_typ"),
            ("ReichweiteWltpEMotor", "bat_km_WLTP"),
            ("WltpKombiniertEfahrzeugeKwh", "ver_strom"),
            ("WltpCo2KombiniertG", "direct_co2"),
            ("CO2Herstellung", "fuel_co2"),
        ]

        for source, target in optional_fields:
            value = row.get(source)
            if pd.isna(value):
                continue
            if target in {"bat_cap", "bat_km_WLTP", "ver_strom", "direct_co2", "fuel_co2"}:
                if float(value) <= 0 and target != "direct_co2":
                    continue
            vehicle[target] = value

        payloads.append(
            (
                f"feed-row-{index}-{vehicle['id']}-{vehicle['tsa']}",
                {
                    "nomenclature": "tcs",
                    "country_code": row.get("country_code", "CH"),
                    "vehicles": [
                        {key: value for key, value in vehicle.items() if pd.notna(value)}
                    ],
                },
            )
        )

    return payloads


def main() -> int:
    package_versions()
    app = create_app()
    app.testing = True

    payloads = {
        "tcs-bev": {
            "nomenclature": "tcs",
            "country_code": "CH",
            "vehicles": [
                {
                    "id": "BEV001",
                    "vehicle_type": "car",
                    "year": 2025,
                    "tsa": "E",
                    "fzklasse": 30005,
                    "leer": 2780,
                    "nutz": 530,
                    "gesamt": 3310,
                    "kw": 0,
                    "kw_sl": 250,
                    "tank": 0,
                    "bat_cap": 92,
                    "bat_typ": "NMC-622",
                    "bat_km_WLTP": 473,
                    "ver_strom": 20,
                    "direct_co2": 0,
                    "fuel_co2": 22,
                }
            ],
        },
        "tcs-phev": {
            "nomenclature": "tcs",
            "country_code": "CH",
            "vehicles": [
                {
                    "id": "PHEV001",
                    "vehicle_type": "car",
                    "year": 2025,
                    "tsa": "C1",
                    "fzklasse": 30003,
                    "leer": 1700,
                    "nutz": 400,
                    "gesamt": 2100,
                    "kw": 90,
                    "kw_sl": 160,
                    "tank": 40,
                    "bat_cap": 15,
                    "bat_typ": "NMC-811",
                    "bat_km_WLTP": 50,
                    "ver_strom": 10,
                    "ver": 5.0,
                    "direct_co2": 45,
                    "fuel_co2": 18,
                }
            ],
        },
        "native-car": {
            "nomenclature": "carculator",
            "country_code": "CH",
            "vehicles": [
                {
                    "id": "CAR001",
                    "vehicle_type": "car",
                    "powertrain": "BEV",
                    "size": "Medium",
                    "year": 2025,
                    "electric energy stored": 75,
                    "battery technology": "NMC-622",
                    "electricity consumption": 18,
                    "power": 160,
                    "curb mass": 1900,
                }
            ],
        },
        "swisscargo-truck": {
            "nomenclature": "swisscargo",
            "country_code": "CH",
            "vehicles": [
                {
                    "id": "TRUCK001",
                    "vehicle_type": "truck",
                    "year": 2025,
                    "size": "32t",
                    "powertrain": "BEV",
                    "battery technology": "Li-S",
                }
            ],
        },
    }

    ok = True
    with app.test_client() as client:
        try:
            ok = post_payload(client, "dev-tcs.py", load_tcs_py_payload()) and ok
        except Exception:
            ok = False
            print("\ndev-tcs.py raised an exception:")
            traceback.print_exc()

        for name, payload in build_feed_payloads():
            try:
                ok = post_payload(client, name, payload) and ok
            except Exception:
                ok = False
                print(f"\n{name} raised an exception:")
                traceback.print_exc()

        for name, payload in payloads.items():
            try:
                ok = post_payload(client, name, payload) and ok
            except Exception:
                ok = False
                print(f"\n{name} raised an exception:")
                traceback.print_exc()

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
