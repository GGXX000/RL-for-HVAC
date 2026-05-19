from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MPL_CACHE = PROJECT_ROOT / ".cache" / "matplotlib"
os.environ.setdefault("MPLCONFIGDIR", str(DEFAULT_MPL_CACHE))
DEFAULT_MPL_CACHE.mkdir(parents=True, exist_ok=True)

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
import pandas as pd


def configure_chinese_font() -> None:
    candidates = [
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/Supplemental/Songti.ttc",
        "/Library/Fonts/Arial Unicode.ttf",
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simhei.ttf",
        "C:/Windows/Fonts/simsun.ttc",
    ]
    for font_path in candidates:
        if Path(font_path).exists():
            font_manager.fontManager.addfont(font_path)
            name = font_manager.FontProperties(fname=font_path).get_name()
            plt.rcParams["font.sans-serif"] = [name]
            plt.rcParams["axes.unicode_minus"] = False
            return


def plot_outputs(traces: dict[str, pd.DataFrame], kpis: pd.DataFrame, output_dir: Path) -> None:
    configure_chinese_font()
    output_dir.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.bar(kpis["controller"], kpis["electric_kwh"], label="总电耗", color="#3b6ea8")
    ax.bar(kpis["controller"], kpis["fan_kwh"], label="风机电耗", color="#d08742")
    ax.set_ylabel("电耗 [kWh]")
    ax.set_title("不同控制器的电耗对比")
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_dir / "energy_kpi.png", dpi=180)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.bar(kpis["controller"], kpis["zat_violation_c"], color="#9b4d55")
    ax.set_ylabel("ZAT 违规量 [C]")
    ax.set_title("区域温度违规量")
    fig.tight_layout()
    fig.savefig(output_dir / "zat_violations.png", dpi=180)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4.5))
    data = [df["cop"].dropna().to_numpy() for df in traces.values()]
    ax.boxplot(data, labels=list(traces.keys()), showfliers=False)
    ax.set_ylabel("冷机 COP [-]")
    ax.set_title("冷机 COP 分布")
    fig.tight_layout()
    fig.savefig(output_dir / "cop_boxplot.png", dpi=180)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(9, 4.5))
    for name, df in traces.items():
        daily = df.set_index("timestamp")["electric_kwh"].cumsum()
        ax.plot(daily.index, daily.values, label=name)
    ax.set_ylabel("累计电耗 [surrogate 原始 kWh]")
    ax.set_title("7 月累计电耗")
    ax.legend()
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(output_dir / "cumulative_energy_raw.png", dpi=180)
    plt.close(fig)
