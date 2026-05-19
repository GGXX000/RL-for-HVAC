# 严格 Spawn/FMU 复现环境设置

当前项目默认使用 surrogate 后端运行，因为本机尚未提供 EnergyPlus 9.6.0、Spawn、OpenModelica、Buildings 9.0.0、`pyfmi`、`gymnasium` 或 `stable-baselines3`。

若要运行与论文一致的严格后端，需要准备：

1. 安装 EnergyPlus 9.6.0。
2. 安装与 EnergyPlus 9.6.0 兼容的 Spawn of EnergyPlus。
3. 安装 OpenModelica。
4. 安装 Modelica Buildings library 9.0.0。
5. 构建与论文一致的 Modelica HVAC 模型：
   - EnergyPlus 负责建筑围护结构与内部负荷。
   - Modelica 负责 AHU、节能器、冷却盘管、风机、冷机和五个 VAV 末端箱。
   - 供热组件可以保留，但在供冷季实验中应禁用。
6. 将 Modelica 模型导出为 FMI 2.0 FMU。
7. 安装 Python 包：
   - `pyfmi`
   - `gymnasium`
   - `stable-baselines3`
8. 将 FMU 变量映射到 `configs/paper_reproduction.json` 中的 24 个观测量和 3 个动作量。
9. 在 `src/repro/fmu_backend.py` 中补充导出 FMU 对应的 `do_step`、变量读取和变量写入调用。

其余流程已经与后端解耦：控制器、replay 生成、规则提取、KPI 汇总和绘图都读取同一种轨迹表结构，因此可以直接复用 surrogate 后端已经验证过的实验主流程。

## Windows 迁移提示

- 优先使用相对路径，例如 `data/processed/asset_manifest.json`、`results/latest`。
- 如果需要写 Windows 绝对路径，建议使用正斜杠形式，例如 `C:/EnergyPlusV9-6-0/energyplus.exe`，避免反斜杠转义问题。
- 若 FMU、IDF、EPW 都放在项目目录内，配置文件无需随机器修改。
