# AGENTS.md

Guidance for coding agents working in this repository.

## Project Overview

This repository exposes a Flask API around the `carculator` family of packages. The main endpoint is `POST /calculate-lca`, which accepts vehicle definitions, validates/translates them, runs a vehicle LCA model, and returns JSON results.

The app is organized as:

- `app.py`: primary Flask application factory used by `Procfile` and `wsgi.py`.
- `wsgi.py`: imports `create_app()` from `app.py` for WSGI servers.
- `flaskCarculator/routes.py`: Flask blueprint and `/calculate-lca` endpoint.
- `flaskCarculator/input_validation.py`: request validation plus TCS and SwissCargo translation into carculator terms.
- `flaskCarculator/lca.py`: model initialization, parameter overrides, inventory calculation, and BAFU result generation.
- `flaskCarculator/formatting.py`: response formatting for TCS and SwissCargo output shapes.
- `flaskCarculator/data/`: YAML mappings and the BAFU score workbook used at runtime.
- `dev/`: manual smoke-test scripts and exploratory notebooks.

## Environment And Dependencies

Use Python 3.11; `runtime.txt` pins `python-3.11.0` for deployment.

Install dependencies with:

```bash
python -m pip install -r requirements.txt
```

For a direct Git install:

```bash
python3.11 -m pip install "git+https://github.com/Laboratory-for-Energy-Systems-Analysis/flaskCarculator.git@TCS"
```

`setup.py` and `requirements.txt` both pin the validated Git commits of the carculator package family. This is intentional: branch installs are only reproducible when transitive Git dependencies are also pinned. Network access is required, and installs can be slow.

## Running The App

For local development:

```bash
flask --app flaskCarculator:create_app run --host 0.0.0.0 --port 5000
```

For a deployment-like run:

```bash
gunicorn "flaskCarculator:create_app()" --timeout 120
```

The README examples may reference port `8000`, while the dev scripts use port `5000`. Check the URL before running manual requests.

## Validation And Smoke Tests

There is no committed pytest suite. For now, use focused smoke tests after changes:

- Start the Flask app locally.
- Run `python dev/tcs.py` for a TCS payload against `http://127.0.0.1:5000/calculate-lca`.
- Run `python dev/tcs_feed.py` for the tracked TCS feed at `dev/feed_2025_02_10_example.csv`.
- `dev/swiss_cargo.py` currently targets the Heroku URL unless its URL is changed to localhost.

To smoke-test the package against the installed carculator stack without starting a server:

```bash
PYTHONPATH=. python dev/test_latest_carculator_compatibility.py
```

To compare TCS feed results across two Python environments:

```bash
PYTHONPATH=. python dev/compare_tcs_lca_results.py generate --output dev/lca_results_after_latest.xlsx
PYTHONPATH=. python dev/compare_tcs_lca_results.py compare --before dev/lca_results_before_pinned.xlsx --after dev/lca_results_after_latest.xlsx --output dev/lca_results_before_after_comparison.xlsx
```

The comparison script writes Excel artifacts for manual review. Treat those workbooks as generated outputs unless a task explicitly asks to version them.

When changing validation, translation, or result formatting, prefer adding focused tests rather than only relying on manual scripts.

## Request Flow

The endpoint flow in `flaskCarculator/routes.py` is:

1. Read `request.json`.
2. Call `validate_input(data)`.
3. Translate TCS or SwissCargo nomenclature if requested.
4. Build one model per vehicle with `initialize_model(vehicle, nomenclature)`.
5. Format results:
   - `nomenclature == "tcs"` returns both `results_ecoinvent` and `results_bafu`.
   - `nomenclature == "swisscargo"` returns a list of category rows under `results`.
   - Any other nomenclature serializes the raw xarray result under `results`.
6. Append selected model parameters and metadata to each vehicle response.

Model objects can be memory-heavy. The route deliberately clears the model dictionary after each request and `app.py` runs `gc.collect()` after responses.

## Data And Mapping Rules

Most API behavior is driven by mapping files in `flaskCarculator/data/`.

When adding or renaming request fields:

- Update `flaskCarculator/input_validation.py` allowed and required fields.
- Update `flaskCarculator/data/tcs_parameters_mapping.yaml` if the field comes from TCS nomenclature.
- Update vehicle-specific YAML files under `flaskCarculator/data/{car,truck,bus,two-wheeler}/` when allowed sizes, powertrains, or batteries change.
- Update `flaskCarculator/data/tcs_impacts_mapping.yaml` when changing TCS result field names or impact mappings.

BAFU-specific TCS results use:

- `flaskCarculator/data/bafu_emission_factors.yaml` for direct fuel/electricity factors used in formatting.
- `flaskCarculator/data/bafu_emission_factors/scores.xlsx` for inventory matrix replacement in `lca.py`.

Do not replace these files with generated variants unless the request explicitly asks for a data update.

## Implementation Notes

- The source of truth for the running app is `app.py`. `flaskCarculator/__init__.py` references `config.Config`, but there is no committed `config.py`; avoid using that factory unless you first fix the missing config path.
- `lca.py` registers vehicle models for `car`, `truck`, `bus`, and `two_wheeler`. Validation currently uses `two-wheeler` in its mapping helper. Check this naming mismatch before changing two-wheeler behavior.
- Keep parameter units consistent with existing code. For example, fuel and electricity consumption are passed as per-100-km values and then converted internally for carculator arrays.
- TCS PHEV logic adjusts fuel and electricity consumption with real-world and WLTP utility factors when `bat_km_WLTP` is supplied. If no WLTP electric range is available, supplied TCS `ver` and `ver_strom` values are kept unscaled.
- TCS climate change results are converted from kg to g CO2-eq. in `format_results_for_tcs()`.

## Repository Hygiene

Do not commit generated or local files such as:

- `.DS_Store`
- `.idea/`
- `__pycache__/`
- `*.egg-info/`
- ad hoc output workbooks such as `dev/lca_results.xlsx`

Before editing, check `git status --short` and preserve unrelated user changes. Keep edits scoped to the requested behavior, especially around LCA math and data mappings.
