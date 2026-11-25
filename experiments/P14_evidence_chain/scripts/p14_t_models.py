# -*- coding: utf-8 -*-
"""P14-C: model-family comparison on T 191 (and 183 baseline).

Candidate families:
- ordinal logistic C=1.5 / C=2
- ordinal XGBoost (default p09 arm)
- multiclass XGBoost (default p09 arm)

All use the same 10 seeds and the same outer folds; this is a model-selection
screen, not a second feature search.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "core"))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "experiments" / "P10_ftir_v3" / "scripts"))

import numpy as np
import pandas as pd

import p09_grade_exhaustive as p9
import p10c_bench as p10c
import p0_clean_baseline as p0
from modeling import load_dataset, canon
from p14_t_evidence import ordinal_proba_fixed

SEEDS = [42, 202, 777, 1234, 2026, 31415, 2718, 1618, 5678, 9999]


def main():
    t0 = time.time()
    _, samples, perf, _ = load_dataset(str(ROOT / "合并版数据集.xlsx"))
    fids = {sid: p0.formula_id({canon(str(k).strip()): max(0.0, float(v))
                                for k, v in samples[sid]["组分"].items()}) for sid in samples}
    targets = p9.build_targets(samples, perf, fids)
    ft = pd.read_csv(ROOT / "experiments/P10_ftir_v3/data/ftir_sample_features_v3.csv",
                     encoding="utf-8-sig").set_index("sample_id")
    ft.index = ft.index.astype(str)
    ids = sorted(ft.index[ft["ftir_has"] > 0].astype(str).tolist())
    t = p10c.subset_target(targets["T"], ids)
    X0 = pd.read_csv(ROOT / "experiments/P10_ftir_v3/data/feature_matrix_v2_fix_reduced.csv",
                     encoding="utf-8-sig").set_index("sample_id")
    X0.index = X0.index.astype(str)
    X8 = pd.read_csv(EXP.parent / "P13_feature_opt" / "data" / "feature_matrix_p13_t_ftir7.csv",
                     encoding="utf-8-sig").set_index("sample_id")
    X8.index = X8.index.astype(str)
    y = np.array([p9.grade_from_cuts(v, t["schemas"]["t3_eng"]["cuts"]) for v in t["raw"]], dtype=int)
    Xb, Xf = X0.loc[t["ids"]].values, X8.loc[t["ids"]].values

    rows = []
    for seed in SEEDS:
        for label, X in [("base183", Xb), ("ftir8", Xf)]:
            for arm in ["C1.5", "C2", "ord_xgb", "multi_xgb"]:
                if arm.startswith("C"):
                    C = 1.5 if arm == "C1.5" else 2.0
                    proba = ordinal_proba_fixed(X, y, t["groups"], seed, C)
                else:
                    proba = p9.run_arm(X, t, "t3_eng", arm, seed)["proba"]
                pred = np.argmax(proba, axis=1)
                m = p9.grade_metrics(y, pred, 3)
                rows.append({"target": "T", "set": label, "model": arm, "seed": seed,
                             "n": len(y), "qwk": m["qwk"], "mae": m["mae_grade"],
                             "high": m["high_grade_recall"], "over": m["overprediction_rate"],
                             "cost": m["mean_cost_over2"]})
                print(f"{label:8s} {arm:9s} seed={seed} QWK={m['qwk']:.4f}", flush=True)
    df = pd.DataFrame(rows)
    df.to_csv(EXP / "results/p14_t_models_per_seed.csv", index=False,
              encoding="utf-8-sig", float_format="%.10g")
    agg = df.groupby(["target", "set", "model"]).agg(
        qwk=("qwk", "mean"), qwk_sd=("qwk", "std"), mae=("mae", "mean"),
        high=("high", "mean"), over=("over", "mean"), cost=("cost", "mean"),
        n=("n", "first")).reset_index()
    agg.to_csv(EXP / "results/p14_t_models_summary.csv", index=False,
               encoding="utf-8-sig", float_format="%.10g")
    print("\n", agg.round(4).to_string(index=False))
    print("elapsed", round(time.time() - t0, 1), "s")


if __name__ == "__main__":
    main()
