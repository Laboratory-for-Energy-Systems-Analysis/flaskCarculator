"""Generate and compare TCS-feed LCA result workbooks.

The script is intentionally executable with different Python environments.
Run it once with the pinned carculator stack, once with the latest stack, then
compare the two generated workbooks.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

from app import create_app


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FEED = ROOT / "dev" / "feed_2025_02_10_example.csv"
RESULT_COLUMNS = ("results_ecoinvent", "results_bafu")
TOLERANCE = 1e-9


def build_vehicle(row: pd.Series, year: int) -> dict[str, Any]:
    vehicle = {
        "id": row["FahrzeugId"],
        "vehicle_type": "car",
        "tsa": row["MotorartcodeCH"],
        "year": year,
        "fzklasse": 30004,
        "leer": row["LeergewichtKg"],
        "nutz": row["ZuladungKg"],
        "gesamt": row["GesamtgewichtKg"],
    }

    optional_fields = [
        ("LeistungVerbrennerKw", "kw", False),
        ("LeistungKw", "kw_sl", False),
        ("TankgroessseKraftstoffart", "tank", False),
        ("WltpKombiniertKraftstoffart", "ver", False),
        ("AntriebsbatterieKapazitaetBruttoKwh", "bat_cap", True),
        ("AntriebsbatterieArt", "bat_typ", False),
        ("ReichweiteWltpEMotor", "bat_km_WLTP", True),
        ("WltpKombiniertEfahrzeugeKwh", "ver_strom", True),
        ("WltpCo2KombiniertG", "direct_co2", True),
        ("CO2Herstellung", "fuel_co2", True),
    ]

    for source, target, require_positive in optional_fields:
        value = row.get(source)
        if pd.isna(value):
            continue
        if require_positive and float(value) <= 0:
            continue
        vehicle[target] = value

    return {key: value for key, value in vehicle.items() if pd.notna(value)}


def iter_payloads(feed_path: Path, year: int) -> list[tuple[int, pd.Series, dict[str, Any]]]:
    dataframe = pd.read_csv(feed_path, sep=";", low_memory=False, encoding="latin1")
    payloads = []

    for index, row in dataframe.iterrows():
        payloads.append(
            (
                index,
                row,
                {
                    "nomenclature": "tcs",
                    "country_code": row.get("country_code", "CH"),
                    "vehicles": [build_vehicle(row, year)],
                },
            )
        )

    return payloads


def flatten_vehicle(vehicle: dict[str, Any], source_index: int, source_row: pd.Series) -> dict[str, Any]:
    result = {
        "source_row": source_index,
        "Model": source_row.get("Fahrzeugbezeichnung"),
    }
    result.update(
        {
            key: value
            for key, value in vehicle.items()
            if key not in RESULT_COLUMNS
        }
    )

    for result_column in RESULT_COLUMNS:
        suffix = result_column.removeprefix("results_")
        result.update(
            {
                f"{key}_{suffix}": value
                for key, value in vehicle.get(result_column, {}).items()
            }
        )

    return result


def package_metadata() -> pd.DataFrame:
    records = []
    for module_name in [
        "carculator",
        "carculator_utils",
        "carculator_truck",
        "carculator_bus",
        "carculator_two_wheeler",
    ]:
        module = __import__(module_name)
        records.append(
            {
                "package": module_name,
                "version": getattr(module, "__version__", "unknown"),
                "path": getattr(module, "__file__", "unknown"),
            }
        )
    return pd.DataFrame(records)


def generate_results(feed_path: Path, output_path: Path, year: int) -> pd.DataFrame:
    app = create_app()
    app.testing = True
    rows = []

    with app.test_client() as client:
        for source_index, source_row, payload in iter_payloads(feed_path, year):
            response = client.post(
                "/calculate-lca",
                data=json.dumps(payload),
                content_type="application/json",
            )
            if response.status_code != 200:
                raise RuntimeError(
                    f"Row {source_index} failed with HTTP {response.status_code}: "
                    f"{response.get_data(as_text=True)[:1000]}"
                )

            data = response.get_json()
            for vehicle in data["vehicles"]:
                rows.append(flatten_vehicle(vehicle, source_index, source_row))
            print(f"row {source_index}: ok")

    results = pd.DataFrame(rows)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(output_path) as writer:
        results.to_excel(writer, sheet_name="results", index=False)
        results.T.to_excel(writer, sheet_name="lca_results_transposed", index=True)
        package_metadata().to_excel(writer, sheet_name="packages", index=False)

    print(f"Wrote {len(results)} rows to {output_path}")
    return results


def read_results(path: Path) -> pd.DataFrame:
    excel_file = pd.ExcelFile(path)
    if "results" in excel_file.sheet_names:
        return pd.read_excel(path, sheet_name="results")
    return pd.read_excel(path, sheet_name=excel_file.sheet_names[0]).T.reset_index(drop=True)


def compare_results(before_path: Path, after_path: Path, output_path: Path) -> pd.DataFrame:
    before = read_results(before_path).copy()
    after = read_results(after_path).copy()

    key_columns = [column for column in ["source_row", "id", "Model"] if column in before.columns and column in after.columns]
    if not key_columns:
        raise ValueError("No shared key columns found; expected at least one of source_row, id, Model")

    merged = before.merge(
        after,
        on=key_columns,
        how="outer",
        suffixes=("_before", "_after"),
        indicator=True,
    )

    records = []
    shared_columns = sorted((set(before.columns) & set(after.columns)) - set(key_columns))
    for column in shared_columns:
        before_column = f"{column}_before"
        after_column = f"{column}_after"
        if before_column not in merged.columns or after_column not in merged.columns:
            continue

        before_values = pd.to_numeric(merged[before_column], errors="coerce")
        after_values = pd.to_numeric(merged[after_column], errors="coerce")
        numeric_mask = before_values.notna() | after_values.notna()
        if not numeric_mask.any():
            continue

        deltas = after_values - before_values
        pct_deltas = deltas.where(before_values != 0) / before_values.where(before_values != 0) * 100

        for idx in merged.index[numeric_mask]:
            record = {key: merged.loc[idx, key] for key in key_columns}
            record.update(
                {
                    "metric": column,
                    "before": before_values.loc[idx],
                    "after": after_values.loc[idx],
                    "absolute_change": deltas.loc[idx],
                    "percent_change": pct_deltas.loc[idx],
                    "changed": abs(deltas.loc[idx]) > TOLERANCE,
                }
            )
            records.append(record)

    comparison = pd.DataFrame(records)
    changed = comparison[comparison["changed"]].copy()
    if not changed.empty:
        changed["absolute_percent_change"] = changed["percent_change"].abs()

    summary = (
        comparison.groupby("metric", dropna=False)
        .agg(
            compared_values=("metric", "size"),
            changed_values=("changed", "sum"),
            max_absolute_change=("absolute_change", lambda values: values.abs().max()),
            mean_absolute_change=("absolute_change", lambda values: values.abs().mean()),
            max_percent_change=("percent_change", lambda values: values.abs().max()),
            mean_percent_change=("percent_change", lambda values: values.abs().mean()),
        )
        .reset_index()
        .sort_values(["changed_values", "max_absolute_change"], ascending=[False, False])
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(output_path) as writer:
        comparison.to_excel(writer, sheet_name="numeric_comparison", index=False)
        changed.sort_values("absolute_change", key=lambda col: col.abs(), ascending=False).to_excel(
            writer,
            sheet_name="changed_only",
            index=False,
        )
        summary.to_excel(writer, sheet_name="summary_by_metric", index=False)
        before.to_excel(writer, sheet_name="before", index=False)
        after.to_excel(writer, sheet_name="after", index=False)

    print(f"Wrote comparison to {output_path}")
    print(f"Compared {len(comparison)} numeric values; changed {int(comparison['changed'].sum())}.")
    if not changed.empty:
        print("\nLargest absolute changes:")
        print(
            changed.sort_values("absolute_change", key=lambda col: col.abs(), ascending=False)
            .head(20)[key_columns + ["metric", "before", "after", "absolute_change", "percent_change"]]
            .to_string(index=False)
        )

    return comparison


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate_parser = subparsers.add_parser("generate")
    generate_parser.add_argument("--feed", type=Path, default=DEFAULT_FEED)
    generate_parser.add_argument("--output", type=Path, required=True)
    generate_parser.add_argument("--year", type=int, default=2025)

    compare_parser = subparsers.add_parser("compare")
    compare_parser.add_argument("--before", type=Path, required=True)
    compare_parser.add_argument("--after", type=Path, required=True)
    compare_parser.add_argument("--output", type=Path, required=True)

    args = parser.parse_args()
    if args.command == "generate":
        generate_results(args.feed, args.output, args.year)
    elif args.command == "compare":
        compare_results(args.before, args.after, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
