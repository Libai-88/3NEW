# -*- coding: utf-8 -*-
"""P14-D: drop-one FTIR feature ablation on T 191, C=2, 10 seeds.

If one FTIR feature is responsible for the gain, dropping it should collapse
QWK; uniform small drops indicate the block works as a whole.
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
FTIR8 = list(p10c.FTIR_RAW8)


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
    X8 = pd.read_csv(EXP.parent / "P13_feature_opt" / "data" / "feature_matrix_p13_t_ftir8.csv",
                     encoding="utf-8-sig").set_index("sample_id")
    X8.index = X8.index.astype(str)
    X = X8.loc[t["ids"]].copy()
    y = np.array([p9.grade_from_cuts(v, t["schemas"]["t3_eng"]["cuts"]) for v in t["raw"]], dtype=int)
    full_cols = list(X.columns)
    rows = []
    for drop in ["full"] + FTIR8:
        cols = [c for c in full_cols if c != drop]
        for seed in SEEDS:
            proba = ordinal_proba_fixed(X[cols].values, y, t["groups"], seed, 2.0)
            pred = np.argmax(proba, axis=1)
            m = p9.grade_metrics(y, pred, 3)
            rows.append({"target": "T", "drop": drop, "n_features": len(cols), "seed": seed,
                         "n": len(y), "qwk": m["qwk"], "mae": m["mae_grade"],
                         "high": m["high_grade_recall"], "over": m["overprediction_rate"],
                         "cost": m["mean_cost_over2"]})
            print(f"drop={drop:16s} seed={seed} QWK={m['qwk']:.4f}", flush=True)
    df = pd.DataFrame(rows)
    df.to_csv(EXP / "results/p14_t_drop_one_per_seed.csv", index=False,
              encoding="utf-8-sig", float_format="%.10g")
    agg = df.groupby(["target", "drop"]).agg(
        qwk=("qwk", "mean"), qwk_sd=("qwk", "std"), mae=("mae", "mean"),
        high=("high", "mean"), over=("over", "mean"), cost=("cost", "mean"),
        n_features=("n_features", "first"), n=("n", "first")).reset_index()
    full = float(agg[agg["drop"] == "full"].qwk.iloc[0])
    agg["delta_vs_full"] = agg["qwk"] - full
    agg.to_csv(EXP / "results/p14_t_drop_one_summary.csv", index=False,
               encoding="utf-8-sig", float_format="%.10g")
    print("\n", agg.round(4).to_string(index=False))
    print("elapsed", round(time.time() - t0, 1), "s")


if __name__ == "__main__":
    main()
