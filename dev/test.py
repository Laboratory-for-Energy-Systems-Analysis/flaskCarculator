import requests

# Define the URL for the Flask endpoint
url = "http://127.0.0.1:5000/calculate-lca"

# Create the data payload to send to the server
data = {
    "nomenclature": "tcs",
    "country_code": "CH",
    "vehicles": [
        {
            "car_id": "001",
            "vehicle_type": "car",
            "tsa": "E",
            "fzklasse": 30008,
            "leer": 1500,
            "nutz": 500,
            "driving_mass": 2000,
            "primary_engine_power": 100,
            "total_engine_power": 150,
            "fuel_tank_mass": 50,
            "ver_abs": 7.5
        }
    ],
}

# Send the POST request
response = requests.post(url, json=data)

# Check if the request was successful
if response.status_code == 200:
    # Parse the JSON response
    result = response.json()
    print("LCA Results:", result)
else:
    print(f"Failed to get LCA results. Status code: {response.status_code}")
    print("Error:", response.text)
