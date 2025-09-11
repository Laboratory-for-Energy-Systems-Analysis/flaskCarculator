import requests
import xarray as xr
from pprint import pprint

# Define the URL for the Flask endpoint
url = "https://flaskcarculator-489d75c1c463.herokuapp.com/calculate-lca"
# url = "http://127.0.0.1:5000/calculate-lca"
#url = "http://129.129.162.211:2001/calculate-lca"

# Create the data payload to send to the server
data = {
    "nomenclature": "swisscargo",
    "country_code": "CH",
    "ai_compare": True,
    "language": "en",
    "vehicles": [
         {
             "id": "BEEV001",
             "vehicle_type": "truck",
             "year": 2023,
             "size": "32t",
             "powertrain": "BEV",
             "battery technology": "NMC-622",
             "electric energy stored": 725.0,
             "lifetime kilometers": 710000.0,
             "kilometers per year": 107000.0,
             "electricity consumption": 145,
             "battery lifetime replacement": 0,
             "func_unit": "tkm",
             "purchase_year": 2023,
             "resale_year": 2028,
             "canton": "Bern",
             "interest rate": 0.0
        },
        {
             "id": "BEEV002",
             "vehicle_type": "truck",
             "year": 2023,
             "size": "32t",
             "powertrain": "BEV",
             "battery technology": "NMC-811",
             "electric energy stored": 300.0,
             "lifetime kilometers": 500000.0,
             "kilometers per year": 107000.0,
             "electricity consumption": 125,
             "battery lifetime replacement": 0,
             "func_unit": "tkm",
            "purchase_year": 2023,
            "resale_year": 2028,
            "cargo mass": 20000,
            "canton": "Basel-Landschaft",
        },
        # {
        #      "id": "FCEV001",
        #      "vehicle_type": "truck",
        #      "year": 2023,
        #      "size": "32t",
        #      "powertrain": "FCEV",
        #      "battery technology": "NMC-622",
        #      #"electric energy stored": 300.0,
        #      "lifetime kilometers": 710000.0,
        #      "kilometers per year": 107000.0,
        #      #"electricity consumption": 145,
        #     "hydrogen consumption": 8.5,
        #     "hydrogen": "hydrogen - smr - natural gas",
        #      "fuel cell lifetime replacement": 0,
        # },
        # {
        #       "id": "ICEV001",
        #       "vehicle_type": "truck",
        #       "year": 2023,
        #       "size": "32t",
        #       "powertrain": "ICEV-d",
        #         "power": 235,
        # #      #"battery technology": "NMC-811",
        # #      #"electric energy stored": 300.0,
        #       "lifetime kilometers": 300000.0,
        #       "kilometers per year": 107000.0,
        # #      #"electricity consumption": 125,
        #       "fuel consumption": 32,
        # #      #"battery lifetime replacement": 0,
        #        "func_unit": "tkm",
        #         "fuel cost": 1.8,
        #     "purchase_year": 2023,
        #     "resale_year": 2028,
        #     "payload": 20000,
        #     "canton": "Aargau",
        #     "share tolled roads": 0.0
        # },
        # {
        #      "id": "ICEV002",
        #      "vehicle_type": "truck",
        #      "year": 2023,
        #      "size": "32t",
        #      "powertrain": "ICEV-g",
        #      #"battery technology": "NMC-811",
        #      #"electric energy stored": 300.0,
        #      "lifetime kilometers": 1000000.0,
        #      "kilometers per year": 107000.0,
        #      #"electricity consumption": 125,
        #      "fuel consumption": 36,
        #      #"battery lifetime replacement": 0,
        # }
    ],
}

# Send the POST request
response = requests.post(url, json=data)

# Check if the request was successful
if response.status_code == 200:
    # Parse the JSON response
    result = response.json()

    #array = xr.DataArray.from_dict(result["vehicles"][0]["results"])
    #print(array.coords["impact"].values)
    pprint(result)

else:
    print(f"Failed to get LCA results. Status code: {response.status_code}")
    print("Error:", response.text)

