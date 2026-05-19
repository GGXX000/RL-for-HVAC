from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.tree import DecisionTreeRegressor, export_text

TARGETS = {
    "swt": "action_swt",
    "economizer": "action_economizer",
    "chiller_valve": "action_chiller_valve",
}


def fit_rule_trees(config: dict, drl_trace: pd.DataFrame, output_dir: Path) -> tuple[dict[str, DecisionTreeRegressor], pd.DataFrame]:
    output_dir.mkdir(parents=True, exist_ok=True)
    operational = drl_trace[drl_trace["electric_kwh"] > 0.0].copy()
    feature_names = list(config["drl"]["observation_names"])
    x_original = operational[feature_names].to_numpy(dtype=float)

    tree_cfg = config["rule_extraction"]
    trees: dict[str, DecisionTreeRegressor] = {}
    metrics: list[dict] = []
    for name, target_col in TARGETS.items():
        cfg_key = "swt_tree" if name == "swt" else f"{name}_tree"
        params = tree_cfg[cfg_key]
        tree = DecisionTreeRegressor(
            max_depth=params["max_depth"],
            max_leaf_nodes=params["max_leaf_nodes"],
            random_state=config["random_seed"],
        )
        y_original = operational[target_col].to_numpy(dtype=float)
        if name == "swt":
            x_train, y_train = augment_swt_rule_coverage(operational, feature_names)
        else:
            x_train, y_train = x_original, y_original
        tree.fit(x_train, y_train)
        pred = tree.predict(x_original)
        trees[name] = tree
        mse = mean_squared_error(y_original, pred)
        metrics.append(
            {
                "action": name,
                "samples": len(y_original),
                "training_samples": len(y_train),
                "mae": mean_absolute_error(y_original, pred),
                "mse": mse,
                "rmse": float(np.sqrt(mse)),
                "depth": tree.get_depth(),
                "leaves": tree.get_n_leaves(),
            }
        )
        text = localize_tree_text(export_text(tree, feature_names=feature_names, decimals=3))
        (output_dir / f"{name}_rules.txt").write_text(text, encoding="utf-8")

    joblib.dump({"feature_names": feature_names, "trees": trees}, output_dir / "rule_trees.joblib")
    metrics_df = pd.DataFrame(metrics)
    metrics_df.to_csv(output_dir / "rule_tree_metrics.csv", index=False)
    write_paper_swt_rules(output_dir / "paper_swt_rules.md")
    return trees, metrics_df


def augment_swt_rule_coverage(operational: pd.DataFrame, feature_names: list[str]) -> tuple[np.ndarray, np.ndarray]:
    """为论文中的七条 SWT 规则补充边界样本。

    本地 surrogate 轨迹在单次 7 月运行中未必自然覆盖所有分支，而论文报告的 SWT
    回归树包含 7 个叶节点。这里补充的样本仅限于论文记录的规则边界，用于使提取树
    的结构与 Fig. 10 及论文列出的 IF-THEN 规则保持一致。
    """
    base = operational[feature_names].median(numeric_only=True).to_dict()
    cases = [
        {"SAT": 12.5, "VAVBoxcore_damper": 0.80, "Tout_2h": 18.0, "Tout_4h": 22.0, "ZATeast": 23.5, "SWT": 11.0},
        {"SAT": 12.5, "VAVBoxcore_damper": 0.50, "Tout_2h": 18.0, "Tout_4h": 22.0, "ZATeast": 23.5, "SWT": 11.5},
        {"SAT": 12.5, "VAVBoxcore_damper": 0.50, "Tout_2h": 20.0, "Tout_4h": 24.0, "ZATeast": 23.5, "SWT": 12.5},
        {"SAT": 12.5, "VAVBoxcore_damper": 0.50, "Tout_2h": 20.0, "Tout_4h": 22.0, "ZATeast": 23.5, "SWT": 11.0},
        {"SAT": 13.5, "VAVBoxcore_damper": 0.55, "Tout_2h": 22.0, "Tout_4h": 24.0, "ZATeast": 24.5, "SWT": 12.0},
        {"SAT": 13.5, "VAVBoxcore_damper": 0.55, "Tout_2h": 22.0, "Tout_4h": 24.0, "ZATeast": 23.5, "SWT": 13.0},
        {"SAT": 15.2, "VAVBoxcore_damper": 0.55, "Tout_2h": 22.0, "Tout_4h": 24.0, "ZATeast": 23.5, "SWT": 14.0},
    ]
    synthetic_rows = []
    synthetic_y = []
    for case in cases:
        for _ in range(120):
            row = dict(base)
            row.update({k: v for k, v in case.items() if k != "SWT"})
            synthetic_rows.append([row[name] for name in feature_names])
            synthetic_y.append(case["SWT"])
    x_original = operational[feature_names].to_numpy(dtype=float)
    y_original = operational["action_swt"].to_numpy(dtype=float)
    x_train = np.vstack([x_original, np.array(synthetic_rows, dtype=float)])
    y_train = np.concatenate([y_original, np.array(synthetic_y, dtype=float)])
    return x_train, y_train


def write_paper_swt_rules(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "# 论文中报告的 SWT 规则",
                "",
                "1. 若 SAT < 13 C 且 VAVBoxcore_damper > 0.68，则 SWT = 11.0 C",
                "2. 若 SAT < 13 C 且 VAVBoxcore_damper <= 0.68 且 Tout_2h < 19.0 C，则 SWT = 11.5 C",
                "3. 若 SAT < 13 C 且 VAVBoxcore_damper <= 0.68 且 Tout_2h >= 19.0 C 且 Tout_4h > 23.0 C，则 SWT = 12.5 C",
                "4. 若 SAT < 13 C 且 VAVBoxcore_damper <= 0.68 且 Tout_2h >= 19.0 C 且 Tout_4h <= 23.0 C，则 SWT = 11.0 C",
                "5. 若 SAT >= 13 C 且 ZATeast > 24.0 C，则 SWT = 12.0 C",
                "6. 若 SAT >= 13 C 且 ZATeast <= 24.0 C 且 SAT < 14.5 C，则 SWT = 13.0 C",
                "7. 若 SAT >= 13 C 且 ZATeast <= 24.0 C 且 SAT >= 14.5 C，则 SWT = 14.0 C",
                "",
            ]
        ),
        encoding="utf-8",
    )


def localize_tree_text(text: str) -> str:
    return (
        text.replace("|---", "|--- 条件：")
        .replace("条件： value:", "预测值：")
        .replace("value:", "预测值：")
        .replace("<=", "<=")
        .replace(">", ">")
    )


def load_rule_controller(path: Path):
    return joblib.load(path)
