# -*- coding: utf-8 -*-
"""P14-H: FTIR-block permutation null for T 190, C=2.

The 7 FTIR columns are shuffled as a block across samples, preserving the
within-sample profile but destroying the sample-label association.  This is a
negative control, not a feature-selection procedure.
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

SEEDS = [42, 202, 777, 1234, 2026]
N_PERM = 20
FTIR7 = [c for c in p10c.FTIR_RAW8 if c != "ftir_oh_epox"]


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
    X7 = pd.read_csv(EXP.parent / "P13_feature_opt" / "data" / "feature_matrix_p13_t_ftir7.csv",
                     encoding="utf-8-sig").set_index("sample_id")
    X7.index = X7.index.astype(str)
    X = X7.loc[t["ids"]].copy()
    y = np.array([p9.grade_from_cuts(v, t["schemas"]["t3_eng"]["cuts"]) for v in t["raw"]], dtype=int)
    obs = []
    for seed in SEEDS:
        proba = ordinal_proba_fixed(X.values, y, t["groups"], seed, 2.0)
        m = p9.grade_metrics(y, np.argmax(proba, axis=1), 3)
        obs.append(m["qwk"])
    obs_mean = float(np.mean(obs))
    rng = np.random.default_rng(20261125)
    rows = []
    for p in range(N_PERM):
        Xp = X.copy()
        perm = rng.permutation(len(X))
        Xp[FTIR7] = Xp[FTIR7].to_numpy()[perm]
        for seed in SEEDS:
            proba = ordinal_proba_fixed(Xp.values, y, t["groups"], seed, 2.0)
            m = p9.grade_metrics(y, np.argmax(proba, axis=1), 3)
            rows.append({"perm": p, "seed": seed, "qwk": m["qwk"]})
            print(f"perm={p:02d} seed={seed} QWK={m['qwk']:.4f}", flush=True)
    df = pd.DataFrame(rows)
    df.to_csv(EXP / "results/p14_t_permutation_per_run.csv", index=False,
              encoding="utf-8-sig", float_format="%.10g")
    perm_means = df.groupby("perm").qwk.mean()
    pval = (1 + int((perm_means >= obs_mean).sum())) / (1 + len(perm_means))
    summary = pd.DataFrame([{
        "observed_mean": obs_mean, "obs_seeds": ";".join(f"{v:.6f}" for v in obs),
        "null_mean": perm_means.mean(), "null_sd": perm_means.std(ddof=1),
        "null_min": perm_means.min(), "null_max": perm_means.max(),
        "n_perm": len(perm_means), "perm_p_ge_obs": pval}])
    summary.to_csv(EXP / "results/p14_t_permutation_summary.csv", index=False,
                   encoding="utf-8-sig", float_format="%.10g")
    print("\n", summary.round(4).to_string(index=False))
    print("elapsed", round(time.time() - t0, 1), "s")


if __name__ == "__main__":
    main()
