import requests
import xarray as xr
from pprint import pprint

# Define the URL for the Flask endpoint
url = "https://flaskcarculator-489d75c1c463.herokuapp.com/calculate-lca"
# url = "http://127.0.0.1:5000/calculate-lca"

# Create the data payload to send to the server
data = {
    "nomenclature": "swisscargo",
    "country_code": "CH",
    "vehicles": [
         {
             "id": "ICEV001",
             "vehicle_type": "car",
             "year": 2020,
             "size": "Medium",
             "powertrain": "ICEV-d",
        }
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
