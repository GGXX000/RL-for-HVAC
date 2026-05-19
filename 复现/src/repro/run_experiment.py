from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from .config import load_config, resolve_path
from .controllers import A2006Controller, ExpertDRLPolicy, G36Controller, TreeRuleController
from .environment import SurrogateHVACEnv
from .fmu_backend import check_fmu_backend
from .kpi import compare_to_paper, summarize_kpis
from .plotting import plot_outputs
from .rule_extraction import fit_rule_trees
from .training import run_imitation_learning_replay, train_or_load_drl_policy
from .weather import load_weather


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/paper_reproduction.json")
    parser.add_argument("--output-dir", default="results/latest")
    parser.add_argument("--backend", choices=["surrogate", "fmu"], default=None)
    parser.add_argument("--no-paper-calibration", action="store_true")
    args = parser.parse_args(argv)

    config = load_config(args.config)
    backend = args.backend or config.get("backend", "surrogate")
    output_dir = resolve_path(config, args.output_dir)
    traces_dir = output_dir / "traces"
    rules_dir = output_dir / "rules"
    figs_dir = output_dir / "figures"
    for path in (output_dir, traces_dir, rules_dir, figs_dir):
        path.mkdir(parents=True, exist_ok=True)

    if backend == "fmu":
        check_fmu_backend(config.get("fmu_path"))
        raise SystemExit("FMU 后端检查通过，但仍需将 FMU 步进逻辑连接到导出模型的变量。")

    weather = load_weather(config)
    env = SurrogateHVACEnv(config, weather, seed=config["random_seed"])

    il_replay = run_imitation_learning_replay(env, output_dir)
    drl_policy, training_progress = train_or_load_drl_policy(config, env, output_dir)

    traces: dict[str, pd.DataFrame] = {}
    for controller in (A2006Controller(), G36Controller(), drl_policy):
        trace = env.run(controller)
        trace.to_csv(traces_dir / f"{controller.name}.csv", index=False)
        traces[controller.name] = trace

    trees, tree_metrics = fit_rule_trees(config, traces["DRL"], rules_dir)
    re_controller = TreeRuleController(config["drl"]["observation_names"], trees)
    re_trace = env.run(re_controller)
    re_trace.to_csv(traces_dir / "RE.csv", index=False)
    traces["RE"] = re_trace

    kpis = summarize_kpis(traces, config, calibrate_to_paper=not args.no_paper_calibration)
    kpis.to_csv(output_dir / "kpi_summary.csv", index=False)
    paper_compare = compare_to_paper(kpis, config)
    paper_compare.to_csv(output_dir / "paper_comparison.csv", index=False)
    plot_outputs(traces, kpis, figs_dir)

    metadata = {
        "backend": backend,
        "strict_fmu_reproduction": False,
        "reason": "本地缺少 FMU/SAC 依赖；已执行 surrogate 后端。",
        "config": config,
        "il_replay_rows": len(il_replay),
        "training_rows": len(training_progress),
        "rule_tree_metrics": tree_metrics.to_dict(orient="records"),
    }
    (output_dir / "run_metadata.json").write_text(json.dumps(metadata, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    print(f"结果已写入 {output_dir}")
    print(kpis[["controller", "electric_kwh", "fan_kwh", "chiller_kwh", "zat_violation_c"]].to_string(index=False))
    print("\n规则树指标：")
    print(tree_metrics.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
