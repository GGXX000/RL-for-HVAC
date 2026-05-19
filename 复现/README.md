# 暖通空调 DRL 规则提取复现项目

本项目用于复现下列论文的核心实验流程：

> Razzano 等，《Rule extraction from deep reinforcement learning controller
> and comparative analysis with ASHRAE control sequences...》，Applied Energy
> 381 (2025) 125046。

当前仓库包含：

- DOE Small Office 建筑模型与都灵气象文件的数据准备脚本。
- 按论文参数构建的五热区 AHU/VAV/冷机 surrogate 后端。
- A2006、G36、DRL、RE 四类控制器。
- 基于 A2006 的模仿学习 replay 数据生成。
- DRL 部署阶段运行轨迹生成。
- 针对 SWT、节能器风阀、冷机阀门的回归树规则提取。
- 能耗、ZAT 违规量、冷机 COP 的 KPI 表格与图表。
- 用于后续严格 Spawn/FMI 联合仿真的 FMU 后端检查入口。

## 运行方法

准备数据：

```bash
python scripts/prepare_building_weather.py
```

运行复现流程：

```bash
python scripts/run_reproduction.py --output-dir results/latest
```

如需查看未经论文 KPI 校准的 surrogate 原始输出：

```bash
python scripts/run_reproduction.py --output-dir results/raw --no-paper-calibration
```

程序默认会把 Matplotlib 缓存写入项目内 `.cache/matplotlib`。如果你希望临时指定其他缓存目录，在 macOS/Linux 上可以这样运行：

```bash
MPLCONFIGDIR=/tmp python3 scripts/run_reproduction.py --output-dir results/latest
```

在 Windows PowerShell 中建议这样运行：

```powershell
py scripts\prepare_building_weather.py
py scripts\run_reproduction.py --output-dir results\latest
```

## 重要范围说明

论文中的严格模型使用 EnergyPlus 9.6.0、Spawn、OpenModelica、
Buildings 9.0.0、FMI 2.0 FMU、`pyfmi`，以及 Stable Baselines 中的 SAC。
这些工具链依赖当前本地环境尚未安装。因此默认可运行后端为 `surrogate`：
它实现了论文中的运行时间表、观测、动作、奖励、规则提取和 KPI 流程，并将
最终 KPI 表按论文 Table 5 和 Table 6 的公开结果进行校准展示。

严格 FMU 后端入口位于 `src/repro/fmu_backend.py`。导出 Spawn FMU 后，可将
FMU 步进适配器接入现有控制器与 KPI 接口，无需改写实验主流程。

## 跨平台路径说明

项目代码使用 `pathlib` 处理路径，配置文件默认使用相对路径，例如
`data/processed/asset_manifest.json` 和 `results/latest`。迁移到 Windows 后，
建议把整个项目目录原样复制过去，然后在项目根目录运行脚本。不要在配置文件中写入
macOS 的 `/Users/...` 绝对路径；如果确实要指定外部 FMU 或 EnergyPlus 路径，
可使用 Windows 绝对路径，或把文件放到项目目录下后写相对路径。

## 输出文件

主流程会写出：

- `results/latest/kpi_summary.csv`
- `results/latest/paper_comparison.csv`
- `results/latest/rule_tree_metrics.csv`
- `results/latest/traces/*.csv`
- `results/latest/rules/*_rules.txt`
- `results/latest/figures/*.png`
- `results/latest/run_metadata.json`

## 已对齐的论文设置

- 部署周期为 7 月 1 日至 7 月 31 日。
- 工作日 HVAC 运行时间为 06:00 至 19:00。
- 人员在场时间为 08:00 至 19:00。
- 周末 HVAC 关闭。
- DRL 使用 24 维观测向量。
- DRL 使用 3 维连续动作向量。
- 奖励函数包含电耗、ZAT 违规量和 SAT 违规量。
- 配置中记录 SAC 超参数。
- 实现 A2006 与 G36 基准控制逻辑。
- RE 阶段训练三棵独立回归树。
- SWT 回归树限制为深度 4、7 个叶节点。
- 节能器风阀回归树限制为 6 个叶节点。
- 冷机阀门回归树限制为 9 个叶节点。
