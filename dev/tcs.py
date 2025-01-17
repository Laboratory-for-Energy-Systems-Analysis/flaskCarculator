import requests
import xarray as xr
from pprint import pprint

# Define the URL for the Flask endpoint
url = "https://flaskcarculator-489d75c1c463.herokuapp.com/calculate-lca"
#url = "http://127.0.0.1:5000/calculate-lca"

# Create the data payload to send to the server
data = {
    "nomenclature": "tcs",
    "country_code": "CH",
    "vehicles": [
         {
             "id": "ICEV001",
             "vehicle_type": "car",
             "tsa": "B",
             "year": 2020,
             "fzklasse": 30008,
             "leer": 1400,
             "nutz": 500,
             "gesamt": 1900,
             "kw": 110,
             "kw_sl": 110,
             "tank": 45,
             "ver_abs": 7.8,
             "ver": 7.8,
             "bat_km_tcs": 650,
             "bat_km_WLTP": 0,
             "direct_co2": 120
        },
        {
             "id": "ICEV002",
             "vehicle_type": "car",
             "tsa": "D",
             "year": 2020,
             "fzklasse": 30008,
             "leer": 1400,
             "nutz": 500,
             "gesamt": 1900,
             "kw": 110,
             "kw_sl": 110,
             "tank": 45,
             "ver_abs": 7.8,
             "ver": 7.8,
             "bat_km_tcs": 650,
             "bat_km_WLTP": 0,
            "direct_co2": 1800
        },
{
             "id": "ICEV003",
             "vehicle_type": "car",
             "tsa": "X",
             "year": 2020,
             "fzklasse": 30008,
             "leer": 1400,
             "nutz": 500,
             "gesamt": 1900,
             "kw": 110,
             "kw_sl": 110,
             "tank": 45,
             "ver_abs": 7.8,
             "ver": 7.8,
             "bat_km_tcs": 650,
             "bat_km_WLTP": 0,
             "direct_co2": 200
        },
{
             "id": "ICEV004",
             "vehicle_type": "car",
             "tsa": "Z",
             "year": 2020,
             "fzklasse": 30008,
             "leer": 1400,
             "nutz": 500,
             "gesamt": 1900,
             "kw": 110,
             "kw_sl": 110,
             "tank": 45,
             "ver_abs": 7.8,
             "ver": 7.8,
             "bat_km_tcs": 650,
             "bat_km_WLTP": 0,
             "direct_co2": 300
        },
        {
            "id": "BEV001",
            "vehicle_type": "car",
            "year": 2024,
            "tsa": "E",
            "fzklasse": 30004,
            "leer": 1836,
            "nutz": 313,
            "gesamt": 2149,
            "kw": 208,
            "kw_sl": 208,
            "tank": 0,
            #"ver_abs": 15.5,
            "bat_km_tcs": 400,
            "bat_cap": 75,
            "bat_typ": "LFP",
            "bat_km_WLTP": 513,
            "ver_strom": 13,
            "direct_co2": 0
        },
        # {
        #     "id": "PHEV001",
        #     "vehicle_type": "car",
        #     "year": 2025,
        #     "tsa": "C1",
        #     "fzklasse": 30002,
        #     "leer": 1700,
        #     "nutz": 400,
        #     "gesamt": 2100,
        #     "kw": 90,
        #     "kw_sl": 160,
        #     "tank": 40,
        #     "ver_abs": 5.2,
        #     "bat_km_tcs": 600,
        #     "bat_cap": 15,
        #     "bat_typ": "NMC-811",
        #     "bat_km_WLTP": 50,
        #     "ver_strom": 10,
        #     "ver": 5.0,
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
    pprint(result)

else:
    print(f"Failed to get LCA results. Status code: {response.status_code}")
    print("Error:", response.text)
