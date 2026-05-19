from __future__ import annotations

from pathlib import Path


class FMUBackendUnavailable(RuntimeError):
    pass


def check_fmu_backend(fmu_path: str | Path | None = None) -> None:
    try:
        import pyfmi  # noqa: F401
    except Exception as exc:  # pragma: no cover - 依赖本地工具链
        raise FMUBackendUnavailable(
            "未安装 pyfmi。请安装 EnergyPlus 9.6.0、Spawn、OpenModelica、"
            "Buildings 9.0.0，并将 Modelica HVAC 模型导出为 FMI 2.0 FMU，"
            "然后使用 backend='fmu' 重新运行。"
        ) from exc
    if fmu_path and not Path(fmu_path).exists():
        raise FMUBackendUnavailable(f"未找到 FMU 文件：{fmu_path}")
