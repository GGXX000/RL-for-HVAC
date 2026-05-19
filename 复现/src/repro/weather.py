from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .config import resolve_path


def load_weather(config: dict) -> pd.DataFrame:
    manifest_path = resolve_path(config, config["asset_manifest"])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    weather_path = resolve_path(config, manifest["july_weather_csv"])
    hourly = pd.read_csv(weather_path)

    year = int(config["simulation"]["year"])
    hourly["timestamp"] = pd.to_datetime(
        {
            "year": year,
            "month": hourly["month"].astype(int),
            "day": hourly["day"].astype(int),
            "hour": hourly["hour"].astype(int).clip(1, 24) - 1,
            "minute": hourly["minute"].astype(int),
        }
    )
    hourly = hourly.drop_duplicates("timestamp").set_index("timestamp").sort_index()

    start = pd.Timestamp(config["simulation"]["start"])
    end = pd.Timestamp(config["simulation"]["end"])
    step = f"{config['simulation']['timestep_minutes']}min"
    index = pd.date_range(start, end, freq=step)
    weather = hourly.reindex(index.union(hourly.index)).interpolate("time").reindex(index)
    weather["dry_bulb_c"] = weather["dry_bulb_c"].astype(float)

    for hours in (1, 2, 3, 4):
        shift_steps = int(hours * 60 / config["simulation"]["timestep_minutes"])
        weather[f"Tout_{hours}h"] = weather["dry_bulb_c"].shift(-shift_steps)
        weather[f"Tout_{hours}h"] = weather[f"Tout_{hours}h"].bfill().ffill()

    weather["hour_float"] = weather.index.hour + weather.index.minute / 60.0
    weather["weekday"] = weather.index.weekday
    weather["is_workday"] = weather["weekday"].isin(config["schedule"]["working_days"])
    weather["is_occupied"] = (
        weather["is_workday"]
        & (weather["hour_float"] >= config["schedule"]["occupancy_start_hour"])
        & (weather["hour_float"] < config["schedule"]["operation_end_hour"])
    )
    weather["is_operational"] = (
        weather["is_workday"]
        & (weather["hour_float"] >= config["schedule"]["operation_start_hour"])
        & (weather["hour_float"] < config["schedule"]["operation_end_hour"])
    )
    weather["solar_proxy"] = np.maximum(0.0, np.sin((weather["hour_float"] - 6.0) / 13.0 * np.pi))
    return weather
