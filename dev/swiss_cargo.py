import requests
import xarray as xr
from pprint import pprint

# Define the URL for the Flask endpoint
url = "https://flaskcarculator-489d75c1c463.herokuapp.com/calculate-lca"
# url = "http://127.0.0.1:5000/calculate-lca"
#url = "http://129.129.162.211:2001/calculate-lca"

# Create the data payload to send to the server
data = {
    "nomenclature": "ecoinvent",
    "country_code": "CH",
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
             "battery lifetime replacement": 0
        }
    ],
}

# Send the POST request
response = requests.post(url, json=data)

# Check if the request was successful
if response.status_code == 200:
    # Parse the JSON response
    result = response.json()

    array = xr.DataArray.from_dict(result["vehicles"][0]["results"])
    print(array.coords["impact"].values)
    #pprint(result)
    print(array.sel(impact_category="climate change"))

else:
    print(f"Failed to get LCA results. Status code: {response.status_code}")
    print("Error:", response.text)
