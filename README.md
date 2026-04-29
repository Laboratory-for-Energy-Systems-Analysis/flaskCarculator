API for ``carculator``

Use the API to calculate the environmental impacts of vehicles and their components.

## Installation

To install the validated TCS branch directly from GitHub:

```bash
python3.11 -m pip install "git+https://github.com/Laboratory-for-Energy-Systems-Analysis/flaskCarculator.git@TCS"
```

This installs the app plus the validated Git commits of `carculator`, `carculator_utils`, and the other carculator packages.

For editable development, clone this repository and install the dependencies.

```bash
git clone --branch TCS https://github.com/Laboratory-for-Energy-Systems-Analysis/flaskCarculator.git
cd flaskCarculator
python -m pip install -r requirements.txt
python -m pip install -e .
```

To run the API using Flask's development server, you can use the following command:

```bash
  
    flask --app flaskCarculator:create_app run --host 0.0.0.0 --port 5000
    
```

or using `gunicorn`:

```bash
  
    gunicorn --workers 3 "flaskCarculator:create_app()"
  
```

## TCS validation

The TCS branch includes two local validation scripts:

```bash
PYTHONPATH=. python dev/test_latest_carculator_compatibility.py
PYTHONPATH=. python dev/compare_tcs_lca_results.py generate --output dev/lca_results_after_latest.xlsx
```

`dev/test_latest_carculator_compatibility.py` exercises `dev/tcs.py`, all rows in `dev/feed_2025_02_10_example.csv`, and a small set of non-TCS smoke payloads against the installed carculator stack. `dev/compare_tcs_lca_results.py` can generate Excel result workbooks from the TCS feed and compare two workbooks with numeric deltas.

## Usage

```python

    import requests
    import xarray as xr
    
    # Define the URL for the Flask endpoint
    url = "http://127.0.0.1:8000/calculate-lca"
    
    # Create the data payload to send to the server
    data = {
        "nomenclature": "tcs", # if using TCS terms, otherwise use "carculator"
        "country_code": "CH", # two-digit ISO country code
        "vehicles": [
            {
                "id": "ICEV001",
                "vehicle_type": "car", # mandatory
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
                "bat_km_WLTP": 0
            },
            {
                "id": "BEV001",
                "vehicle_type": "car",
                "year": 2023,
                "tsa": "E",
                "fzklasse": 30024,
                "leer": 2200,
                "nutz": 450,
                "gesamt": 2650,
                "kw": 150,
                "kw_sl": 150,
                "tank": 0,
                "ver_abs": 15.5,
                "bat_km_tcs": 400,
                "bat_cap": 80,
                "bat_typ": "NMC-622",
                "bat_km_WLTP": 450,
                "ver_strom": 17,
            },
            {
                "id": "PHEV001",
                "vehicle_type": "car",
                "year": 2025,
                "tsa": "C1",
                "fzklasse": 30002,
                "leer": 1700,
                "nutz": 400,
                "gesamt": 2100,
                "kw": 90,
                "kw_sl": 160,
                "tank": 40,
                "ver_abs": 5.2,
                "bat_km_tcs": 600,
                "bat_cap": 15,
                "bat_typ": "NMC-811",
                "bat_km_WLTP": 50,
                "ver_strom": 10,
                "ver": 5.0,
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
        print(array)
    
    else:
        print(f"Failed to get LCA results. Status code: {response.status_code}")
        print("Error:", response.text)
```
