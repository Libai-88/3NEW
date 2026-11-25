# -*- coding: utf-8 -*-
"""P14-F: nested C selection for T base183 vs 190-dim FTIR7.

Same outer protocol as P14-A; inner 3-fold grouped CV chooses C from a
restricted grid (0.5, 1.0, 1.5, 2.0).  This is the conservative estimate after
the FTIR7 subset was chosen by drop-one ablation.
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
from scipy import stats

import p09_grade_exhaustive as p9
import p10c_bench as p10c
p0 = __import__("p0_clean_baseline")
from modeling import load_dataset, canon
from p14_t_evidence import ordinal_proba_nested

SEEDS = [42, 202, 777, 1234, 2026, 31415, 2718, 1618, 5678, 9999]
CS = [0.5, 1.0, 1.5, 2.0]


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
    X7 = pd.read_csv(EXP.parent / "P13_feature_opt" / "data" / "feature_matrix_p13_t_ftir7.csv",
                     encoding="utf-8-sig").set_index("sample_id")
    X7.index = X7.index.astype(str)
    y = np.array([p9.grade_from_cuts(v, t["schemas"]["t3_eng"]["cuts"]) for v in t["raw"]], dtype=int)
    sets = {"base183": X0.loc[t["ids"]].values, "ftir7": X7.loc[t["ids"]].values}

    rows, chosen_rows = [], []
    for label, X in sets.items():
        print(f"SET {label} {X.shape}", flush=True)
        for seed in SEEDS:
            proba, chosen = ordinal_proba_nested(X, y, t["groups"], seed, CS)
            pred = np.argmax(proba, axis=1)
            m = p9.grade_metrics(y, pred, 3)
            rows.append({"target": "T", "set": label, "seed": seed, "n": len(y),
                         "qwk": m["qwk"], "mae": m["mae_grade"], "high": m["high_grade_recall"],
                         "over": m["overprediction_rate"], "cost": m["mean_cost_over2"]})
            for fi, c in enumerate(chosen):
                chosen_rows.append({"set": label, "seed": seed, "fold": fi, "C": c})
            print(f"  {label} nested seed={seed} QWK={m['qwk']:.4f} C={chosen}", flush=True)
    df = pd.DataFrame(rows)
    df.to_csv(EXP / "results/p14_t7_nested_per_seed.csv", index=False,
              encoding="utf-8-sig", float_format="%.10g")
    pd.DataFrame(chosen_rows).to_csv(EXP / "results/p14_t7_nested_chosen_C.csv",
                                     index=False, encoding="utf-8-sig")
    agg = df.groupby(["target", "set"]).agg(
        qwk=("qwk", "mean"), qwk_sd=("qwk", "std"), mae=("mae", "mean"),
        high=("high", "mean"), over=("over", "mean"), cost=("cost", "mean"),
        n=("n", "first")).reset_index()
    b = df[df.set == "base183"].set_index("seed")["qwk"]
    f = df[df.set == "ftir7"].set_index("seed")["qwk"]
    aligned = pd.concat([b.rename("base"), f.rename("ftir7")], axis=1).dropna()
    d = (aligned["ftir7"] - aligned["base"]).to_numpy()
    tt = stats.ttest_rel(aligned["ftir7"], aligned["base"]) if len(d) >= 3 else None
    wx = stats.wilcoxon(d) if len(d) >= 6 else None
    delta = pd.DataFrame([{"delta_mean": d.mean(), "delta_sd": d.std(ddof=1),
                           "n_seed": len(d), "t_p": float(tt.pvalue) if tt is not None else np.nan,
                           "wilcoxon_p": float(wx.pvalue) if wx is not None else np.nan,
                           "positive_seeds": int((d > 0).sum())}])
    agg.to_csv(EXP / "results/p14_t7_nested_summary.csv", index=False,
               encoding="utf-8-sig", float_format="%.10g")
    delta.to_csv(EXP / "results/p14_t7_nested_delta.csv", index=False,
                 encoding="utf-8-sig", float_format="%.10g")
    print("\n", agg.round(4).to_string(index=False))
    print("\n", delta.round(4).to_string(index=False))
    print("elapsed", round(time.time() - t0, 1), "s")


if __name__ == "__main__":
    main()
