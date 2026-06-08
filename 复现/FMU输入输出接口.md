# FMU 输入/输出接口说明

> 目标：把**建筑、EnergyPlus、HVAC、AHU、冷机、VAV boxes** 全部整合成一个 FMU。  
> 这个 FMU 对外暴露下面这些输入/输出接口。  
> Python 控制器负责读取 FMU 输出、计算动作，再把动作写回 FMU。

## 1. FMU 建模边界

这个 FMU 可以被视为一个黑箱：

```text
控制器动作 inputs  -->  [整栋建筑 + HVAC 系统 FMU]  -->  状态/能耗 outputs
```

FMU 内部应至少包含：

- 5 个热区：south、east、north、west、core
- 建筑围护结构、内部负荷、占用日程、天气
- AHU：economizer、cooling coil、fan
- Chiller：冷冻水供水/回水
- 5 个 VAV boxes：每个热区一个
- 冷却季运行逻辑，仿真步长 30 min

FMU 不需要内置 DRL 或规则抽取算法；控制算法在 Python 外部实现。

## 2. FMU 必须提供的输入接口

这些变量由 Python 控制器写入 FMU。建议全部作为 FMI `input` 暴露。

| 建议变量名 | 单位 | 范围 | 中文说明 |
|---|---|---:|---|
| `E_damper_position` | - | 0-1 | Economizer damper 开度控制信号。用于调节新风/回风混合比例。0 可理解为最小新风开度，1 为最大开度。 |
| `C_valve_position` | - | 0-1 | Cooling coil / chiller valve 开度控制信号。0 为关闭，1 为全开。论文中动作步长为 0.1。 |
| `SWT_setpoint` | degC | 4-15 | 冷冻水供水温度设定值，Supply Water Temperature setpoint。 |
| `rpmsignal` | - | 0-1 | 送风机转速/风机控制信号。 |
| `VAVBoxsouth_damper_cmd` | - | 0-1 | 南区 VAV box damper 开度命令。 |
| `VAVBoxeast_damper_cmd` | - | 0-1 | 东区 VAV box damper 开度命令。 |
| `VAVBoxnorth_damper_cmd` | - | 0-1 | 北区 VAV box damper 开度命令。 |
| `VAVBoxwest_damper_cmd` | - | 0-1 | 西区 VAV box damper 开度命令。 |
| `VAVBoxcore_damper_cmd` | - | 0-1 | 核心区 VAV box damper 开度命令。 |

说明：

- 论文中的 DRL/RE 主要控制前三个量：`E_damper_position`、`C_valve_position`、`SWT_setpoint`。

- 风机和 VAV damper 在论文中由 ASHRAE 2006 控制序列管理，但为了完整复现和方便对比，建议也暴露为 FMU 输入，由 Python 外部控制。

  

## 3. FMU 必须提供的输出接口

这些变量由 Python 控制器从 FMU 读取。建议全部作为 FMI `output` 暴露。

### 3.1 送风与 AHU 状态

| 建议变量名 | 单位 | 中文说明 |
|---|---|---|
| `SAT` | degC | Supply Air Temperature，AHU 送风温度。 |
| `Vflow_air` | m3/s | 总送风体积流量。 |
| `Vflow_outdoor_air` | m3/s | 新风体积流量。 |
| `Tmix` | degC | Mixed air temperature，新风和回风混合后的空气温度。 |
| `rpmsignal_actual` | - | 实际送风机控制信号/转速反馈。如果输入 `rpmsignal` 能直接代表实际值，也可以输出同名 `rpmsignal`。 |

### 3.2 五个热区空气温度

| 建议变量名 | 单位 | 中文说明 |
|---|---|---|
| `ZATsouth` | degC | 南区空气温度。 |
| `ZATeast` | degC | 东区空气温度。 |
| `ZATnorth` | degC | 北区空气温度。 |
| `ZATwest` | degC | 西区空气温度。 |
| `ZATcore` | degC | 核心区空气温度。 |

### 3.3 五个 VAV box 实际开度

| 建议变量名 | 单位 | 中文说明 |
|---|---|---|
| `VAVBoxsouth_damper` | - | 南区 VAV damper 实际开度。 |
| `VAVBoxeast_damper` | - | 东区 VAV damper 实际开度。 |
| `VAVBoxnorth_damper` | - | 北区 VAV damper 实际开度。 |
| `VAVBoxwest_damper` | - | 西区 VAV damper 实际开度。 |
| `VAVBoxcore_damper` | - | 核心区 VAV damper 实际开度。 |

### 3.4 冷冻水与冷机状态

| 建议变量名 | 单位 | 中文说明 |
|---|---|---|
| `mflow_water` | m3/s | 冷冻水流量。论文表中单位为 m3/s。 |
| `SWT` | degC | 实际冷冻水供水温度。注意它不是设定值，设定值输入为 `SWT_setpoint`。 |
| `RWT` | degC | 冷冻水回水温度。 |

### 3.5 天气、时间、占用

| 建议变量名 | 单位 | 中文说明 |
|---|---|---|
| `Toutdoor_air` | degC | 当前室外干球温度。 |
| `hour` | h | 当前小时，例如 0-23。 |
| `occupancy` | - | 建筑占用状态或占用强度。简单复现可用 0/1。 |
| `Tout_1h` | degC | 未来 1 小时室外温度。 |
| `Tout_2h` | degC | 未来 2 小时室外温度。 |
| `Tout_3h` | degC | 未来 3 小时室外温度。 |
| `Tout_4h` | degC | 未来 4 小时室外温度。 |

说明：

- 论文假设未来 1-4 小时室外温度是 perfect prediction。
- 这些未来天气量可以由 FMU 输出，也可以由 Python 从同一个天气文件读取生成。为了接口最清楚，建议 FMU 直接输出。

### 3.6 能耗输出

为了计算论文中的 reward 和 KPI，FMU 必须让 Python 获得风机和冷机能耗。可以用“功率输出”或“每步能耗输出”二选一；推荐两类都给。

| 建议变量名 | 单位 | 中文说明 |
|---|---|---|
| `P_fan` | kW | 送风机瞬时电功率。 |
| `P_chiller` | kW | 冷机瞬时电功率。 |
| `E_fan_step` | kWh | 当前 30 min 控制步内送风机耗电量。 |
| `E_chiller_step` | kWh | 当前 30 min 控制步内冷机耗电量。 |

如果只能提供一组，优先提供：

| 优先级 | 变量 | 原因 |
|---:|---|---|
| 1 | `E_fan_step`, `E_chiller_step` | Python 可直接累计能耗，最方便复现 reward 和 KPI。 |
| 2 | `P_fan`, `P_chiller` | Python 需要按仿真步长积分成 kWh。 |

## 4. 推荐额外输出接口

这些不是 DRL observation 表中的硬性变量，但有助于检查 FMU 是否正确、复现论文图表和排查问题。

| 建议变量名 | 单位 | 中文说明 |
|---|---|---|
| `Tret_air` | degC | AHU 回风温度。 |
| `Texh_air` | degC | 排风温度。 |
| `mflow_outdoor_air` | kg/s | 新风质量流量。 |
| `mflow_return_air` | kg/s | 回风质量流量。 |
| `mflow_total_air` | kg/s | AHU 总空气质量流量。 |
| `Tdis_south` | degC | 南区 VAV box 出风温度。 |
| `Tdis_east` | degC | 东区 VAV box 出风温度。 |
| `Tdis_north` | degC | 北区 VAV box 出风温度。 |
| `Tdis_west` | degC | 西区 VAV box 出风温度。 |
| `Tdis_core` | degC | 核心区 VAV box 出风温度。 |
| `mflow_dis_south` | kg/s | 南区送风质量流量。 |
| `mflow_dis_east` | kg/s | 东区送风质量流量。 |
| `mflow_dis_north` | kg/s | 北区送风质量流量。 |
| `mflow_dis_west` | kg/s | 西区送风质量流量。 |
| `mflow_dis_core` | kg/s | 核心区送风质量流量。 |
| `COP_chiller` | - | 冷机 COP，用于复现论文中冷机性能分析。 |

## 5. 最终一句话版本

请做一个包含整栋五区办公室建筑和完整 HVAC 系统的 FMU。  
FMU 输入为：economizer damper、cooling/chiller valve、SWT setpoint、fan rpm、五个 VAV damper 命令。  
FMU 输出为：送风状态、五区温度、五个 VAV damper 实际开度、冷冻水供回水状态、天气/时间/占用、风机和冷机能耗。  
控制器不需要内置在 FMU 中，Python 会在外部根据这些输出计算控制动作。
