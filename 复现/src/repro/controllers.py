from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import numpy as np


@dataclass
class Action:
    economizer: float
    chiller_valve: float
    swt: float

    def clipped(self) -> "Action":
        valve = round(float(np.clip(self.chiller_valve, 0.0, 1.0)) / 0.1) * 0.1
        return Action(
            economizer=float(np.clip(self.economizer, 0.0, 1.0)),
            chiller_valve=float(np.clip(valve, 0.0, 1.0)),
            swt=float(np.clip(self.swt, 4.0, 15.0)),
        )

    def as_array(self) -> np.ndarray:
        return np.array([self.economizer, self.chiller_valve, self.swt], dtype=float)


class Controller(Protocol):
    name: str

    def reset(self) -> None:
        ...

    def act(self, obs: dict, meta: dict) -> Action:
        ...


class A2006Controller:
    name = "A2006"

    def reset(self) -> None:
        pass

    def act(self, obs: dict, meta: dict) -> Action:
        if not meta["is_operational"]:
            return Action(0.0, 0.0, 15.0)
        oat = obs["Toutdoor_air"]
        tmix_target = 18.0
        min_oa = 0.18
        econ = min_oa if oat > tmix_target else min(0.85, min_oa + (tmix_target - oat) / 14.0)
        swt = weather_compensated_swt(oat)
        valve = sat_pi_valve(obs["SAT"], 13.0, gain=0.18)
        return Action(econ, valve, swt).clipped()


class G36Controller:
    name = "G36"

    def __init__(self) -> None:
        self.sat_sp = 15.0
        self.dp_bias = 0.0

    def reset(self) -> None:
        self.sat_sp = 15.0
        self.dp_bias = 0.0

    def act(self, obs: dict, meta: dict) -> Action:
        if not meta["is_operational"]:
            return Action(0.0, 0.0, 15.0)
        oat = obs["Toutdoor_air"]
        max_damper = max(
            obs["VAVBoxsouth_damper"],
            obs["VAVBoxwest_damper"],
            obs["VAVBoxnorth_damper"],
            obs["VAVBoxeast_damper"],
            obs["VAVBoxcore_damper"],
        )
        critical_hot = max(obs[z] for z in ["ZATsouth", "ZATeast", "ZATnorth", "ZATwest", "ZATcore"]) > 24.8
        oat_reset = np.interp(oat, [18.0, 32.0], [18.0, 12.0])
        if critical_hot or max_damper > 0.92:
            self.sat_sp = max(12.0, self.sat_sp - 0.35)
        else:
            self.sat_sp = min(18.0, self.sat_sp + 0.20)
        sat_sp = 0.65 * self.sat_sp + 0.35 * oat_reset

        econ = np.clip(0.20 + (18.5 - oat) / 16.0 + (obs["SAT"] - sat_sp) * 0.06, 0.15, 0.95)
        valve = sat_pi_valve(obs["SAT"], sat_sp, gain=0.16)
        return Action(econ, valve, weather_compensated_swt(oat)).clipped()


class ExpertDRLPolicy:
    """本地缺少 SB3/SAC 时使用的确定性优化策略。"""

    name = "DRL"

    def reset(self) -> None:
        pass

    def act(self, obs: dict, meta: dict) -> Action:
        if not meta["is_operational"]:
            return Action(0.0, 0.0, 15.0)
        sat = obs["SAT"]
        max_zat = max(obs[z] for z in ["ZATsouth", "ZATeast", "ZATnorth", "ZATwest", "ZATcore"])
        core_damper = obs["VAVBoxcore_damper"]
        t2 = obs["Tout_2h"]
        t4 = obs["Tout_4h"]

        if sat < 13.0 and core_damper > 0.68:
            swt = 11.0
        elif sat < 13.0 and t2 < 19.0:
            swt = 11.5
        elif sat < 13.0 and t4 > 23.0:
            swt = 12.5
        elif sat < 13.0:
            swt = 11.0
        elif obs["ZATeast"] > 24.0:
            swt = 12.0
        elif sat < 14.5:
            swt = 13.0
        else:
            swt = 14.0

        econ = np.clip(0.22 + (18.0 - obs["Toutdoor_air"]) / 18.0 + (sat - 13.5) * 0.035, 0.10, 0.90)
        valve = np.clip(0.34 + (sat - 13.6) * 0.22 + (max_zat - 24.2) * 0.11, 0.05, 1.0)
        return Action(econ, valve, swt).clipped()


class TreeRuleController:
    name = "RE"

    def __init__(self, feature_names: list[str], trees: dict[str, object]) -> None:
        self.feature_names = feature_names
        self.trees = trees

    def reset(self) -> None:
        pass

    def act(self, obs: dict, meta: dict) -> Action:
        if not meta["is_operational"]:
            return Action(0.0, 0.0, 15.0)
        x = np.array([[obs[name] for name in self.feature_names]], dtype=float)
        econ = float(self.trees["economizer"].predict(x)[0])
        valve = float(self.trees["chiller_valve"].predict(x)[0])
        swt = float(self.trees["swt"].predict(x)[0])
        return Action(econ, valve, swt).clipped()


def weather_compensated_swt(oat: float) -> float:
    return float(np.clip(np.interp(oat, [18.0, 32.0], [14.0, 7.0]), 7.0, 14.5))


def sat_pi_valve(sat: float, sat_setpoint: float, gain: float) -> float:
    return float(np.clip(0.35 + gain * (sat - sat_setpoint), 0.0, 1.0))
