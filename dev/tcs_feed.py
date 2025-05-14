import requests
import pandas as pd
from pprint import pprint

# Define the URL for the Flask endpoint
#url = "https://flaskcarculator-489d75c1c463.herokuapp.com/calculate-lca"
url = "http://127.0.0.1:5000/calculate-lca"

results_list = []

def check_results(results):
    """
    Check the results of the LCA calculations.
    """
    for vehicle in results["vehicles"]:
        # lca_GWP_karosserie must be between 10 and 150
        if vehicle["results_ecoinvent"]["lca_GWP_karosserie"] < 10 or vehicle["results_ecoinvent"]["lca_GWP_karosserie"] > 150:
            print(f"lca_GWP_karosserie: {vehicle['results_ecoinvent']['lca_GWP_karosserie']}")
            print(vehicle)
            print("#" * 50)

        if vehicle["results_bafu"]["lca_GWP_karosserie"] < 10 or vehicle["results_bafu"]["lca_GWP_karosserie"] > 150:
            print(f"lca_GWP_karosserie: {vehicle['results_bafu']['lca_GWP_karosserie']}")
            print(vehicle)
            print("#" * 50)

        # lca_GWP_speicher must be between 0 and 50
        if vehicle["results_ecoinvent"]["lca_GWP_speicher"] < 0 or vehicle["results_ecoinvent"]["lca_GWP_speicher"] > 50:
            print(f"lca_GWP_speicher: {vehicle['results_ecoinvent']['lca_GWP_speicher']}")
            print(vehicle)
            print("#" * 50)
        if vehicle["results_bafu"]["lca_GWP_speicher"] < 0 or vehicle["results_bafu"]["lca_GWP_speicher"] > 50:
            print(f"lca_GWP_speicher: {vehicle['results_bafu']['lca_GWP_speicher']}")
            print(vehicle)
            print("#" * 50)

        # lca_GWP_strasse must be between 0 and 25
        if vehicle["results_ecoinvent"]["lca_GWP_strasse"] < 0 or vehicle["results_ecoinvent"]["lca_GWP_strasse"] > 40:
            print(f"lca_GWP_strasse: {vehicle['results_ecoinvent']['lca_GWP_strasse']}")
            print(vehicle)
            print("#" * 50)
        if vehicle["results_bafu"]["lca_GWP_strasse"] < 0 or vehicle["results_bafu"]["lca_GWP_strasse"] > 40:
            print(f"lca_GWP_strasse: {vehicle['results_bafu']['lca_GWP_strasse']}")
            print(vehicle)
            print("#" * 50)

        # lca_Primärenergie_betrieb must be between 1 and 6.5
        if vehicle["results_ecoinvent"]["lca_Primärenergie_betrieb"] < 1 or vehicle["results_ecoinvent"]["lca_Primärenergie_betrieb"] > 6.5:
            print(f"lca_Primärenergie_betrieb: {vehicle['results_ecoinvent']['lca_Primärenergie_betrieb']}")
            print(vehicle)
            print("#" * 50)
        if vehicle["results_bafu"]["lca_Primärenergie_betrieb"] < 1 or vehicle["results_bafu"]["lca_Primärenergie_betrieb"] > 6.5:
            print(f"lca_Primärenergie_betrieb: {vehicle['results_bafu']['lca_Primärenergie_betrieb']}")
            print(vehicle)
            print("#" * 50)

        # check that, if "batt_cap" is non-zero, "lca_GWP_speicher" must be superior to 1
        if vehicle.get("bat_cap", 0) > 0 and vehicle["results_ecoinvent"]["lca_GWP_speicher"] <= 1:
            print(f"lca_GWP_speicher: {vehicle['results_ecoinvent']['lca_GWP_speicher']}")
            print(vehicle)
            print("#" * 50)
        if vehicle.get("bat_cap", 0) > 0 and vehicle["results_bafu"]["lca_GWP_speicher"] <= 1:
            print(f"lca_GWP_speicher: {vehicle['results_bafu']['lca_GWP_speicher']}")
            print(vehicle)
            print("#" * 50)


# Load the data from the CSV file
fp = "feed_2025_02_10_example.csv"
df = pd.read_csv(fp, sep=";", encoding="latin-1", low_memory=False)

# Loop through each row in the DataFrame
for index, row in df.iterrows():
    # Shape the JSON payload dynamically based on the DataFrame row
    data = {
        "nomenclature": "tcs",
        "country_code": row.get("country_code", "CH"),  # Default to "CH" if not present
    }

    vehicle_data = [
            {
                "id": row["FahrzeugId"],
                "vehicle_type": "car",
                "tsa": row["MotorartcodeCH"],
                "year": 2025,
                "fzklasse": 30004,
                "leer": row["LeergewichtKg"],
                "nutz": row["ZuladungKg"],
                "gesamt": row["GesamtgewichtKg"],
                "kw": row.get("LeistungVerbrennerKw", 0),
                "kw_sl": row.get("LeistungKw", 0),
                "tank": row.get("TankgroessseKraftstoffart", 0),
                "bat_cap": row.get("AntriebsbatterieKapazitaetBruttoKwh", 0),
                #"bat_typ": row.get("bat_typ", ""),
                "bat_km_WLTP": row.get("ReichweiteWltpEMotor", 0),
                "ver": row.get("WltpKombiniertKraftstoffart", 0),
                "ver_strom": row.get("WltpKombiniertEfahrzeugeKwh", 0),
                "direct_co2": row.get("WltpCo2KombiniertG", 0),
                "fuel_co2": row.get("CO2Herstellung", 0),

            }
        ]

    # remove NaN values
    vehicle_data = [dict((k, v) for k, v in d.items() if pd.notna(v)) for d in vehicle_data]
    data["vehicles"] = vehicle_data

    # Send the POST request
    response = requests.post(url, json=data)

    # Check if the request was successful
    if response.status_code == 200:
        print(f"Request for row {index} succeeded.")
        result = response.json()
        check_results(result)
        for vehicle in result["vehicles"]:
            res = {k: v for k, v in vehicle.items() if k not in ("results_ecoinvent", "results_bafu")}
            res.update({
                f"{k}_ecoinvent": v
                for k, v in vehicle["results_ecoinvent"].items()
            })
            res.update({
                f"{k}_bafu": v
                for k, v in vehicle["results_bafu"].items()
            })
            res.update({
                "Model": row["Fahrzeugbezeichnung"],
            })
            results_list.append(res)
    else:
        print(f"Request for row {index} failed with status code: {response.status_code}")
        print("Error:", response.text)
        # stop the loop if error 500
        if response.status_code == 500:
            pprint(data)
            break

# Create a DataFrame from the list of results
df_results = pd.DataFrame(results_list)
# Save the DataFrame to an Excel file
df_results.T.to_excel("lca_results.xlsx", index=True)