from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .controllers import Action, Controller


ZONE_NAMES = ["south", "east", "north", "west", "core"]
OBS_KEYS = [
    "SAT",
    "Vflow_air",
    "Vflow_outdoor_air",
    "ZATsouth",
    "ZATeast",
    "ZATnorth",
    "ZATwest",
    "ZATcore",
    "Toutdoor_air",
    "VAVBoxsouth_damper",
    "VAVBoxwest_damper",
    "VAVBoxnorth_damper",
    "VAVBoxeast_damper",
    "VAVBoxcore_damper",
    "rpmsignal",
    "Tmix",
    "mflow_water",
    "SWT",
    "RWT",
    "hour",
    "occupancy",
    "Tout_1h",
    "Tout_2h",
    "Tout_3h",
    "Tout_4h",
]


@dataclass
class SimState:
    zat: np.ndarray
    sat: float = 18.0
    swt: float = 14.0
    rwt: float = 17.0
    rpm: float = 0.0
    vav: np.ndarray | None = None
    vflow: float = 0.0
    mflow_water: float = 0.0
    tmix: float = 22.0


class SurrogateHVACEnv:
    """按论文参数构建的五热区 AHU/VAV surrogate。

    它不能替代 Spawn 高保真仿真；它的作用是在未安装
    EnergyPlus/OpenModelica/FMUs 的环境中跑通完整算法流程。
    """

    def __init__(self, config: dict, weather: pd.DataFrame, seed: int = 46) -> None:
        self.config = config
        self.weather = weather
        self.rng = np.random.default_rng(seed)
        self.dt_h = config["simulation"]["timestep_minutes"] / 60.0
        self.zone_bias = np.array([0.35, 0.55, 0.10, 0.20, -0.10])
        self.state = self.initial_state()

    def initial_state(self) -> SimState:
        return SimState(zat=np.array([24.0, 24.0, 24.0, 24.0, 24.0]), vav=np.zeros(5))

    def reset(self, jitter: float = 0.0) -> dict:
        self.state = self.initial_state()
        if jitter:
            self.state.zat += self.rng.normal(0.0, jitter, size=5)
        return self.observe(self.weather.index[0])

    def run(self, controller: Controller, jitter: float = 0.0) -> pd.DataFrame:
        controller.reset()
        self.reset(jitter=jitter)
        rows: list[dict] = []
        for ts, row in self.weather.iterrows():
            obs = self.observe(ts)
            meta = {
                "timestamp": ts,
                "is_operational": bool(row["is_operational"]),
                "is_occupied": bool(row["is_occupied"]),
            }
            action = controller.act(obs, meta).clipped()
            metrics = self.step(ts, action)
            out = {"timestamp": ts, "controller": controller.name, **obs}
            out.update(
                {
                    "action_economizer": action.economizer,
                    "action_chiller_valve": action.chiller_valve,
                    "action_swt": action.swt,
                    **metrics,
                }
            )
            rows.append(out)
        return pd.DataFrame(rows)

    def observe(self, ts: pd.Timestamp) -> dict:
        w = self.weather.loc[ts]
        s = self.state
        vav = s.vav if s.vav is not None else np.zeros(5)
        values = {
            "SAT": s.sat,
            "Vflow_air": s.vflow,
            "Vflow_outdoor_air": s.vflow * max(0.0, min(1.0, (s.tmix - s.sat + 4.0) / 10.0)),
            "ZATsouth": s.zat[0],
            "ZATeast": s.zat[1],
            "ZATnorth": s.zat[2],
            "ZATwest": s.zat[3],
            "ZATcore": s.zat[4],
            "Toutdoor_air": float(w["dry_bulb_c"]),
            "VAVBoxsouth_damper": vav[0],
            "VAVBoxwest_damper": vav[3],
            "VAVBoxnorth_damper": vav[2],
            "VAVBoxeast_damper": vav[1],
            "VAVBoxcore_damper": vav[4],
            "rpmsignal": s.rpm,
            "Tmix": s.tmix,
            "mflow_water": s.mflow_water,
            "SWT": s.swt,
            "RWT": s.rwt,
            "hour": float(w["hour_float"]),
            "occupancy": 1.0 if bool(w["is_occupied"]) else 0.0,
            "Tout_1h": float(w["Tout_1h"]),
            "Tout_2h": float(w["Tout_2h"]),
            "Tout_3h": float(w["Tout_3h"]),
            "Tout_4h": float(w["Tout_4h"]),
        }
        return values

    def step(self, ts: pd.Timestamp, action: Action) -> dict:
        w = self.weather.loc[ts]
        s = self.state
        oat = float(w["dry_bulb_c"])
        operational = bool(w["is_operational"])
        occupied = bool(w["is_occupied"])
        solar = float(w["solar_proxy"])

        if not operational:
            free_float = oat + np.array([0.5, 0.9, 0.1, 0.4, 0.0])
            s.zat += 0.045 * (free_float - s.zat)
            s.sat = oat
            s.swt = action.swt
            s.rwt = action.swt
            s.rpm = 0.0
            s.vav = np.zeros(5)
            s.vflow = 0.0
            s.mflow_water = 0.0
            s.tmix = oat
            return self.metrics(action, operational=False)

        internal = (0.25 if occupied else 0.05) + solar * np.array([0.25, 0.30, 0.16, 0.20, 0.06])
        load = np.maximum(0.0, (s.zat - 24.0) * 0.45 + (oat - 23.0) * 0.035 + internal + self.zone_bias * 0.03)
        vav = np.clip(0.25 + load * 0.42 + np.maximum(0.0, s.zat - 24.0) * 0.16, 0.18, 1.0)
        max_damper = float(vav.max())
        target_rpm = np.clip(0.25 + 0.72 * max_damper, 0.25, 1.0)
        s.rpm += 0.45 * (target_rpm - s.rpm)
        s.vflow = 2.7 * s.rpm

        ret = float(np.mean(s.zat))
        s.tmix = action.economizer * oat + (1.0 - action.economizer) * ret
        coil_effect = action.chiller_valve * np.clip((16.0 - action.swt) / 8.0, 0.0, 1.35) * 6.3
        s.sat = float(np.clip(s.tmix - coil_effect, 10.5, 24.0))
        s.swt = action.swt
        s.rwt = action.swt + 2.2 + 3.8 * action.chiller_valve
        s.mflow_water = 0.85 * action.chiller_valve

        cooling_power = np.maximum(0.0, (s.zat - s.sat) * vav * 0.115)
        envelope_gain = 0.040 * (oat - s.zat)
        s.zat += envelope_gain + internal * 0.16 - cooling_power
        s.zat += self.rng.normal(0.0, 0.015, size=5)
        s.vav = vav
        return self.metrics(action, operational=True)

    def metrics(self, action: Action, operational: bool) -> dict:
        s = self.state
        if not operational:
            return {
                "fan_kwh": 0.0,
                "chiller_kwh": 0.0,
                "electric_kwh": 0.0,
                "zat_violation_c": 0.0,
                "sat_violation_c": 0.0,
                "reward": 0.0,
                "cop": np.nan,
            }

        fan_kw = 0.43 * (s.rpm**3) + 0.02
        lift = max(3.0, 30.0 - action.swt)
        cop = float(np.clip(5.8 - 0.075 * lift + 0.55 * (action.swt - 10.0) / 6.0, 2.1, 6.1))
        cooling_kw = 5.9 * action.chiller_valve * np.clip((16.0 - action.swt) / 7.0, 0.18, 1.5)
        chiller_kw = cooling_kw / cop + 0.04 * action.chiller_valve
        fan_kwh = fan_kw * self.dt_h
        chiller_kwh = chiller_kw * self.dt_h
        zat_low = np.maximum(0.0, 23.0 - s.zat)
        zat_high = np.maximum(0.0, s.zat - 25.0)
        zat_penalty = float((zat_low.sum() + (zat_high**2).sum()) * self.dt_h)
        sat_violation = 0.0
        if s.sat < 12.0 or s.sat > 18.0:
            sat_violation = float(min(s.sat - 12.0, 18.0 - s.sat) ** 2 * self.dt_h)
        reward = -(fan_kwh + chiller_kwh + zat_penalty + sat_violation)
        return {
            "fan_kwh": fan_kwh,
            "chiller_kwh": chiller_kwh,
            "electric_kwh": fan_kwh + chiller_kwh,
            "zat_violation_c": zat_penalty,
            "sat_violation_c": sat_violation,
            "reward": reward,
            "cop": cop,
        }
