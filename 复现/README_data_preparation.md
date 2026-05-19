# 数据准备说明

本仓库首先根据 `gemini-code-1779151233724.md` 的要求，准备论文复现所需的建筑模型与气象文件。

## 脚本

运行：

```bash
python scripts/prepare_building_weather.py
```

也可以指定 DOE Small Office IDF 的气候区版本：

```bash
python scripts/prepare_building_weather.py --climate-zone 4A
```

Windows PowerShell 可使用：

```powershell
py scripts\prepare_building_weather.py --climate-zone 4A
```

默认值为 `4A`，作为意大利北部气候的保守代理选择。也可以选择 DOE 包中的其他版本，例如 `3C`、`5A` 或 `1A`。

## 输出

- `data/raw/doe_small_office_reference_building.zip`：下载得到的 DOE Small Office 参考建筑压缩包。
- `data/interim/doe_small_office_reference_building/`：解压后的 DOE 建筑模型目录。
- `data/processed/turin_italy.epw`：都灵 Caselle 气象文件。
- `data/processed/turin_italy_july_weather.csv`：仅包含 7 月逐小时天气的表格，用于控制器特征与完美未来温度预测。
- `data/processed/asset_manifest.json`：后续基准控制、DRL 与规则提取脚本使用的统一路径和元数据清单。

## 注意事项

- 脚本只依赖 Python 标准库。
- DOE 下载会优先尝试页面发现链接；若页面未公开 ZIP 链接，则使用历史归档路径作为回退。
- 气象文件会优先尝试当前 Climate.OneBuilding 的 Turin-Caselle TMYx 文件，再尝试较旧的 EnergyPlus 风格候选路径。
- 若需要严格使用 EnergyPlus 9.6.0 IDF，请安装 EnergyPlus 9.6.0，并在导出 Spawn/FMUs 前用官方 transition 工具转换所选 IDF。
- manifest 默认写入相对路径，便于在 macOS 与 Windows 之间迁移项目目录。
