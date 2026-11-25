# -*- coding: utf-8 -*-
"""P14-A: 10-seed evidence chain for T, base183 vs base183+FTIR8.

Two modes:
- fixed: same C for every outer fold; sweeps C to show the parameter surface.
- nested: C chosen inside each outer training fold by a 3-fold grouped inner CV;
  this is the leakage-safe estimate to use for model selection.

The outer protocol is the same as P10/P12/P13: StratifiedGroupKFold(5) by
formula_id, 10 seeds.  T decision is argmax of cumulative ordinal probabilities.
"""
from __future__ import annotations

import argparse
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
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

import p09_grade_exhaustive as p9
import p10c_bench as p10c
import p0_clean_baseline as p0
from modeling import load_dataset, canon

SEEDS = [42, 202, 777, 1234, 2026, 31415, 2718, 1618, 5678, 9999]
CS = [0.1, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0]


def logit_model(seed, C):
    return make_pipeline(
        SimpleImputer(strategy="median", add_indicator=True, keep_empty_features=True),
        StandardScaler(),
        LogisticRegression(C=C, penalty="l2", class_weight="balanced",
                           solver="lbfgs", max_iter=3000, n_jobs=1, random_state=seed),
    )


def ordinal_proba_fold(Xtr, ytr, Xte, seed, C, k):
    p_cols = []
    for th in range(k - 1):
        yb = (ytr > th).astype(int)
        if len(np.unique(yb)) == 1:
            p_cols.append(np.full(len(Xte), float(yb[0])))
            continue
        model = logit_model(seed, C)
        model.fit(Xtr, yb)
        p_cols.append(model.predict_proba(Xte)[:, 1])
    p = np.minimum.accumulate(np.column_stack(p_cols), axis=1)
    proba = np.zeros((len(Xte), k), dtype=float)
    proba[:, 0] = 1.0 - p[:, 0]
    for j in range(1, k - 1):
        proba[:, j] = p[:, j - 1] - p[:, j]
    proba[:, k - 1] = p[:, k - 2]
    proba = np.clip(proba, 1e-9, 1.0)
    proba /= proba.sum(axis=1, keepdims=True)
    return proba


def ordinal_proba_fixed(X, y, groups, seed, C):
    k = int(y.max() + 1)
    oof = np.zeros((len(y), k), dtype=float)
    for tr, te in p9.make_splits(y, groups, seed):
        oof[te] = ordinal_proba_fold(X[tr], y[tr], X[te], seed, C, k)
    return oof


def inner_qwk(Xtr, ytr, groups_tr, seed, C, k, n_splits=3):
    pred = np.full(len(ytr), -1, dtype=int)
    for itr, ite in p9.make_splits(ytr, groups_tr, seed, n_splits=n_splits):
        proba = ordinal_proba_fold(Xtr[itr], ytr[itr], Xtr[ite], seed, C, k)
        pred[ite] = np.argmax(proba, axis=1)
    if (pred < 0).any():
        return -np.inf
    return float(p9.grade_metrics(ytr, pred, k)["qwk"])


def ordinal_proba_nested(X, y, groups, seed, cs):
    k = int(y.max() + 1)
    oof = np.zeros((len(y), k), dtype=float)
    chosen = []
    for fi, (tr, te) in enumerate(p9.make_splits(y, groups, seed)):
        scores = {}
        for C in cs:
            scores[C] = inner_qwk(X[tr], y[tr], groups[tr], seed + 1000 + 37 * fi, C, k)
        best_c = max(scores, key=scores.get)
        chosen.append(best_c)
        oof[te] = ordinal_proba_fold(X[tr], y[tr], X[te], seed, best_c, k)
    return oof, chosen


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="fixed", choices=["fixed", "nested"])
    ap.add_argument("--seeds", nargs="*", type=int, default=SEEDS)
    ap.add_argument("--cs", nargs="*", type=float, default=CS)
    args = ap.parse_args()
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
    X8 = pd.read_csv(EXP.parent / "P13_feature_opt" / "data" / "feature_matrix_p13_t_ftir8.csv",
                     encoding="utf-8-sig").set_index("sample_id")
    X8.index = X8.index.astype(str)
    y = np.array([p9.grade_from_cuts(v, t["schemas"]["t3_eng"]["cuts"]) for v in t["raw"]], dtype=int)
    sets = {"base183": X0.loc[t["ids"]].values, "ftir8": X8.loc[t["ids"]].values}

    rows, chosen_rows = [], []
    for label, X in sets.items():
        print(f"SET {label} {X.shape}", flush=True)
        for seed in args.seeds:
            if args.mode == "fixed":
                for C in args.cs:
                    proba = ordinal_proba_fixed(X, y, t["groups"], seed, C)
                    pred = np.argmax(proba, axis=1)
                    m = p9.grade_metrics(y, pred, int(y.max() + 1))
                    rows.append({"target": "T", "set": label, "mode": "fixed", "C": C, "seed": seed,
                                 "n": len(y), "qwk": m["qwk"], "mae": m["mae_grade"],
                                 "high": m["high_grade_recall"], "over": m["overprediction_rate"],
                                 "cost": m["mean_cost_over2"]})
                    print(f"  {label} C={C:g} seed={seed} QWK={m['qwk']:.4f}", flush=True)
            else:
                proba, chosen = ordinal_proba_nested(X, y, t["groups"], seed, args.cs)
                pred = np.argmax(proba, axis=1)
                m = p9.grade_metrics(y, pred, int(y.max() + 1))
                rows.append({"target": "T", "set": label, "mode": "nested", "C": np.nan, "seed": seed,
                             "n": len(y), "qwk": m["qwk"], "mae": m["mae_grade"],
                             "high": m["high_grade_recall"], "over": m["overprediction_rate"],
                             "cost": m["mean_cost_over2"]})
                for fi, c in enumerate(chosen):
                    chosen_rows.append({"set": label, "seed": seed, "fold": fi, "C": c})
                print(f"  {label} nested seed={seed} QWK={m['qwk']:.4f} C={chosen}", flush=True)

    df = pd.DataFrame(rows)
    suffix = args.mode
    df.to_csv(EXP / f"results/p14_t_{suffix}_per_seed.csv", index=False,
              encoding="utf-8-sig", float_format="%.10g")
    if args.mode == "nested":
        pd.DataFrame(chosen_rows).to_csv(EXP / "results/p14_t_nested_chosen_C.csv",
                                         index=False, encoding="utf-8-sig")

    if args.mode == "fixed":
        agg = df.groupby(["target", "set", "C"]).agg(
            qwk=("qwk", "mean"), qwk_sd=("qwk", "std"), mae=("mae", "mean"),
            high=("high", "mean"), over=("over", "mean"), cost=("cost", "mean"),
            n=("n", "first")).reset_index()
        b = df[df.set == "base183"].set_index(["C", "seed"])["qwk"]
        f = df[df.set == "ftir8"].set_index(["C", "seed"])["qwk"]
        delta = (f - b).dropna().reset_index(name="delta")
        drows = []
        for C, g in delta.groupby("C"):
            d = g["delta"].to_numpy()
            tt = stats.ttest_rel(f.loc[C].to_numpy(), b.loc[C].to_numpy()) if len(d) >= 3 else None
            wx = stats.wilcoxon(d) if len(d) >= 6 else None
            drows.append({"C": C, "delta_mean": d.mean(), "delta_sd": d.std(ddof=1),
                          "n_seed": len(d), "t_p": float(tt.pvalue) if tt is not None else np.nan,
                          "wilcoxon_p": float(wx.pvalue) if wx is not None else np.nan,
                          "positive_seeds": int((d > 0).sum())})
        pd.DataFrame(drows).to_csv(EXP / "results/p14_t_fixed_delta.csv",
                                   index=False, encoding="utf-8-sig", float_format="%.10g")
        agg.to_csv(EXP / "results/p14_t_fixed_summary.csv",
                   index=False, encoding="utf-8-sig", float_format="%.10g")
        print("\n", agg.round(4).to_string(index=False))
        print("\n", pd.DataFrame(drows).round(4).to_string(index=False))
    else:
        agg = df.groupby(["target", "set"]).agg(
            qwk=("qwk", "mean"), qwk_sd=("qwk", "std"), mae=("mae", "mean"),
            high=("high", "mean"), over=("over", "mean"), cost=("cost", "mean"),
            n=("n", "first")).reset_index()
        b = df[df.set == "base183"].set_index("seed")["qwk"]
        f = df[df.set == "ftir8"].set_index("seed")["qwk"]
        aligned = pd.concat([b.rename("base"), f.rename("ftir")], axis=1).dropna()
        d = (aligned["ftir"] - aligned["base"]).to_numpy()
        tt = stats.ttest_rel(aligned["ftir"].to_numpy(), aligned["base"].to_numpy()) if len(d) >= 3 else None
        wx = stats.wilcoxon(d) if len(d) >= 6 else None
        delta = pd.DataFrame([{"delta_mean": d.mean(), "delta_sd": d.std(ddof=1),
                               "n_seed": len(d), "t_p": float(tt.pvalue) if tt is not None else np.nan,
                               "wilcoxon_p": float(wx.pvalue) if wx is not None else np.nan,
                               "positive_seeds": int((d > 0).sum())}])
        agg.to_csv(EXP / "results/p14_t_nested_summary.csv", index=False,
                   encoding="utf-8-sig", float_format="%.10g")
        delta.to_csv(EXP / "results/p14_t_nested_delta.csv", index=False,
                     encoding="utf-8-sig", float_format="%.10g")
        print("\n", agg.round(4).to_string(index=False))
        print("\n", delta.round(4).to_string(index=False))
    print("elapsed", round(time.time() - t0, 1), "s")


if __name__ == "__main__":
    main()
