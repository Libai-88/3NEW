# -*- coding: utf-8 -*-
"""P14-G: group bootstrap CI for T, base183 vs FTIR7 at C=2, 10 seeds.

OOF predictions are generated once per seed; bootstrap resamples formula
groups (not rows) with replacement, preserving the group structure.  This is a
descriptive uncertainty interval for the fixed-C model, not a replacement for
nested CV.
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
from sklearn.metrics import cohen_kappa_score

import p09_grade_exhaustive as p9
import p10c_bench as p10c
import p0_clean_baseline as p0
from modeling import load_dataset, canon
from p14_t_evidence import ordinal_proba_fixed

SEEDS = [42, 202, 777, 1234, 2026, 31415, 2718, 1618, 5678, 9999]
N_BOOT = 2000


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
    groups = np.asarray(t["groups"])
    Xb, Xf = X0.loc[t["ids"]].values, X7.loc[t["ids"]].values

    rows = []
    for seed in SEEDS:
        pb = ordinal_proba_fixed(Xb, y, groups, seed, 2.0)
        pf = ordinal_proba_fixed(Xf, y, groups, seed, 2.0)
        rows.append(pd.DataFrame({"seed": seed, "sample_id": t["ids"], "group": groups,
                                  "y": y, "pred_base": np.argmax(pb, axis=1),
                                  "pred_ftir7": np.argmax(pf, axis=1)}))
        print("seed", seed, "done", flush=True)
    per_sample = pd.concat(rows, ignore_index=True)
    per_sample.to_csv(EXP / "results/p14_t_bootstrap_preds.csv", index=False,
                      encoding="utf-8-sig")

    rng = np.random.default_rng(20261125)
    boots = []
    for seed, g in per_sample.groupby("seed"):
        uniq = g["group"].drop_duplicates().to_numpy()
        idx_by_group = {u: np.flatnonzero(g["group"].to_numpy() == u) for u in uniq}
        for _ in range(N_BOOT):
            samp = rng.choice(uniq, size=len(uniq), replace=True)
            idx = np.concatenate([idx_by_group[u] for u in samp])
            yb = g["y"].to_numpy()[idx]
            qb = cohen_kappa_score(yb, g["pred_base"].to_numpy()[idx], weights="quadratic", labels=[0, 1, 2])
            qf = cohen_kappa_score(yb, g["pred_ftir7"].to_numpy()[idx], weights="quadratic", labels=[0, 1, 2])
            boots.append({"seed": seed, "qwk_base": qb, "qwk_ftir7": qf, "delta": qf - qb})
    bdf = pd.DataFrame(boots)
    bdf.to_csv(EXP / "results/p14_t_bootstrap_reps.csv", index=False,
               encoding="utf-8-sig", float_format="%.10g")
    s = bdf.groupby("seed").agg(
        base_mean=("qwk_base", "mean"), base_lo=("qwk_base", lambda x: np.percentile(x, 2.5)),
        base_hi=("qwk_base", lambda x: np.percentile(x, 97.5)),
        ftir_mean=("qwk_ftir7", "mean"), ftir_lo=("qwk_ftir7", lambda x: np.percentile(x, 2.5)),
        ftir_hi=("qwk_ftir7", lambda x: np.percentile(x, 97.5)),
        delta_mean=("delta", "mean"), delta_lo=("delta", lambda x: np.percentile(x, 2.5)),
        delta_hi=("delta", lambda x: np.percentile(x, 97.5))).reset_index()
    s.to_csv(EXP / "results/p14_t_bootstrap_summary.csv", index=False,
             encoding="utf-8-sig", float_format="%.10g")
    print("\n", s.round(4).to_string(index=False))
    print("overall delta mean", bdf.delta.mean(), "2.5/97.5",
          np.percentile(bdf.delta, [2.5, 97.5]))
    print("elapsed", round(time.time() - t0, 1), "s")


if __name__ == "__main__":
    main()
