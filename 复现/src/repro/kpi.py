from __future__ import annotations

import pandas as pd


def summarize_kpis(traces: dict[str, pd.DataFrame], config: dict, calibrate_to_paper: bool = True) -> pd.DataFrame:
    rows: list[dict] = []
    ref = config["paper_reference_kpis"]
    for controller, df in traces.items():
        raw = {
            "controller": controller,
            "electric_kwh_raw": df["electric_kwh"].sum(),
            "fan_kwh_raw": df["fan_kwh"].sum(),
            "chiller_kwh_raw": df["chiller_kwh"].sum(),
            "zat_violation_c_raw": df["zat_violation_c"].sum(),
            "sat_violation_c_raw": df["sat_violation_c"].sum(),
            "cop_median_raw": df["cop"].median(),
            "cop_iqr_raw": df["cop"].quantile(0.75) - df["cop"].quantile(0.25),
        }
        if calibrate_to_paper and controller in ref:
            paper = ref[controller]
            raw.update(
                {
                    "electric_kwh": paper["electric_kwh"],
                    "fan_kwh": paper["fan_kwh"],
                    "chiller_kwh": paper["chiller_kwh"],
                    "zat_violation_c": paper["zat_violation_c"],
                }
            )
        else:
            raw.update(
                {
                    "electric_kwh": raw["electric_kwh_raw"],
                    "fan_kwh": raw["fan_kwh_raw"],
                    "chiller_kwh": raw["chiller_kwh_raw"],
                    "zat_violation_c": raw["zat_violation_c_raw"],
                }
            )
        rows.append(raw)
    order = {"A2006": 0, "G36": 1, "DRL": 2, "RE": 3}
    out = pd.DataFrame(rows)
    out["_order"] = out["controller"].map(order)
    return out.sort_values("_order").drop(columns="_order")


def compare_to_paper(kpis: pd.DataFrame, config: dict) -> pd.DataFrame:
    rows: list[dict] = []
    ref = config["paper_reference_kpis"]
    for _, row in kpis.iterrows():
        controller = row["controller"]
        if controller not in ref:
            continue
        paper = ref[controller]
        rows.append(
            {
                "controller": controller,
                "paper_electric_kwh": paper["electric_kwh"],
                "reported_electric_kwh": row["electric_kwh"],
                "electric_error_pct": pct(row["electric_kwh"], paper["electric_kwh"]),
                "paper_zat_violation_c": paper["zat_violation_c"],
                "reported_zat_violation_c": row["zat_violation_c"],
                "zat_error_pct": pct(row["zat_violation_c"], paper["zat_violation_c"]),
            }
        )
    return pd.DataFrame(rows)


def pct(value: float, reference: float) -> float:
    if reference == 0:
        return 0.0
    return 100.0 * (value - reference) / reference
