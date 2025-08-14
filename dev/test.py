import requests
import xarray as xr
from pprint import pprint

# Define the URL for the Flask endpoint
#url = "https://flaskcarculator-489d75c1c463.herokuapp.com/calculate-lca"
# url = "http://127.0.0.1:5000/calculate-lca"
# url = "http://129.129.162.211:2001/calculate-lca"
url = "https://carculator-api-test.psi.ch/calculate-lca"


# Create the data payload to send to the server
data = {
    #"nomenclature": "tcs",
    "country_code": "CH",
    "nomenclature": "ecoinvent",
    "vehicles": [
         {
             "id": "336773",
             "vehicle_type": "car",

             "powertrain": "BEV",
             "size": "Small",
             #"tsa": "E",
             "year": 2025,
             #"fzklasse": 30005,
             #"leer": 2780,
             #"nutz": 530,
             #"gesamt": 3310,
             #"kw": 0,
             #"kw_sl": 250,
             #"tank": 0,
             #"bat_cap":92,
             #"bat_typ": "NMC-622",
             #"bat_km_WLTP": 473,
             #"ver_strom": 20,
             #"direct_co2": 0,
             #"fuel_co2": 22
        },
        # {
        #      "id": "337604",
        #      "vehicle_type": "car",
        #      "tsa": "C",
        #      "year": 2025,
        #      "fzklasse": 30005,
        #      "leer": 2345,
        #      "nutz": 605,
        #      "gesamt": 2950,
        #      "kw": 118,
        #      "kw_sl": 165,
        #      "tank": 65,
        #      "ver": 7.6,
        #      "bat_cap":1,
        #      "bat_typ": "NMC-622",
        #      "direct_co2": 172,
        #      "fuel_co2": 35
        # },
        # {
        #      "id": "335478",
        #      "id": "335246",
        #      "vehicle_type": "car",
        #      "tsa": "C1",
        #      "year": 2025,
        #      "fzklasse": 30003,
        #      "leer": 1649,
        #      "nutz": 431,
        #      "gesamt": 2080,
        #      "kw": 110,
        #      "kw_sl": 150,
        #      "tank": 40,
        #      "ver": 0.3,
        #      "bat_cap": 15,
        #      "bat_typ": "NMC-622",
        #      #"bat_km_WLTP": "63",
        #      "ver_strom": 14,
        #      "direct_co2": 4,
        #      "fuel_co2": 18
        # },
 #         {
 #              "id": "ICEV002",
 #              "vehicle_type": "car",
 #              "tsa": "D",
 #              "year": 2020,
 #              "fzklasse": 30008,
 #              "leer": 1400,
 #              "nutz": 500,
 #              "gesamt": 1900,
 #              "kw": 110,
 #              "kw_sl": 110,
 #              "tank": 45,
 #              "ver": 7.8,
 #              "bat_km_WLTP": 700,
 #              "direct_co2": 1800,
 #              "fuel_co2": 80
 #         },
 # {
 #              "id": "FCEV003",
 #              "vehicle_type": "car",
 #              "tsa": "X",
 #              "year": 2020,
 #              "fzklasse": 30008,
 #              "leer": 1400,
 #              "nutz": 500,
 #              "gesamt": 1900,
 #              "kw": 110,
 #              "kw_sl": 110,
 #              "tank": 45,
 #              "ver": 1.6,
 #              "bat_km_WLTP": 900,
 #              "direct_co2": 200,
 #              "fuel_co2": 120
 #         },
 # {
 #              "id": "ICEVg004",
 #              "vehicle_type": "car",
 #              "tsa": "Z",
 #              "year": 2020,
 #              "fzklasse": 30008,
 #              "leer": 1400,
 #              "nutz": 500,
 #              "gesamt": 1900,
 #              "kw": 110,
 #              "kw_sl": 110,
 #              "tank": 45,
 #              "ver": 4.0,
 #              "bat_km_WLTP": 600,
 #              "direct_co2": 300,
 #              "fuel_co2": 20
 #         },
 #         {
 #             "id": "BEV001",
 #             "vehicle_type": "car",
 #             "year": 2024,
 #             "tsa": "E",
 #             "fzklasse": 30004,
 #             "leer": 1836,
 #             "nutz": 313,
 #             "gesamt": 2149,
 #             "kw": 208,
 #             "kw_sl": 208,
 #             "tank": 0,
 #             "bat_cap": 75,
 #             "bat_typ": "LFP",
 #             "bat_km_WLTP": 513,
 #             "ver_strom": 13,
 #             "direct_co2": 0,
 #             "fuel_co2": 120
 #         },

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