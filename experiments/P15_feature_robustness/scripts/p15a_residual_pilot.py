# -*- coding: utf-8 -*-
"""P15: leakage-safe FTIR residualization for coating T-bend grade.

Hypothesis
----------
P10 showed that the 8 raw FTIR indices are 94.0-99.97% linearly reconstructable
from the 183 base descriptors.  P14's 190-dim gain may therefore come from the
small residual component that base183 cannot explain.  This script isolates that
component inside every training fold:

    F = Ridge(base183 -> FTIR7) fitted on training only
    R = F_observed - F_predicted
    final model = ordinal_logit(base183 + R)

The comparison is pre-specified: base183, raw FTIR7 (P14-style), residual FTIR7.
C is selected by an inner grouped CV inside each outer training fold.  The
feature construction is fitted inside both the outer and inner training folds,
so neither the outer test labels nor the outer test features affect it.

This is deliberately not another formula search: no candidate features are
ranked on the target, and no FTIR subset is selected after seeing results.
"""
from __future__ import annotations

import argparse
import json
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
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

import p09_grade_exhaustive as p9
import p10c_bench as p10c
import p0_clean_baseline as p0
from modeling import load_dataset, canon

SEEDS = [42, 202, 777, 1234, 2026, 31415, 2718, 1618, 5678, 9999]
CS = [0.5, 1.0, 1.5, 2.0]
SETS = ["base183", "raw_ftir7", "resid_ftir7"]


class BasePrep(BaseEstimator, TransformerMixin):
    """Median-impute base features; missing indicators only for columns that need them."""

    def fit(self, X, y=None):
        X = np.asarray(X, dtype=float)
        self.imputer_ = SimpleImputer(strategy="median", add_indicator=True,
                                      keep_empty_features=True).fit(X)
        return self

    def transform(self, X):
        return self.imputer_.transform(np.asarray(X, dtype=float))


class FTIRPrep(BaseEstimator, TransformerMixin):
    """Impute base/FTIR; optionally replace FTIR by its base-residual.

    Output columns are:
      [base_imputed_and_indicators, ftir_core_or_residual, ftir_indicators]
    Raw and residual variants therefore have identical outer dimensions; only
    columns with observed missingness receive indicators, matching P14's
    SimpleImputer(add_indicator=True) behaviour.
    """

    def __init__(self, n_base: int, mode: str = "raw", ridge_alpha: float = 1.0):
        self.n_base = int(n_base)
        self.mode = mode
        self.ridge_alpha = float(ridge_alpha)

    def fit(self, X, y=None):
        X = np.asarray(X, dtype=float)
        Xb, Xf = X[:, : self.n_base], X[:, self.n_base :]
        self.n_ftir_ = Xf.shape[1]
        self.base_imputer_ = SimpleImputer(strategy="median", add_indicator=True,
                                           keep_empty_features=True).fit(Xb)
        self.ftir_imputer_ = SimpleImputer(strategy="median", add_indicator=True,
                                           keep_empty_features=True).fit(Xf)
        B = self.base_imputer_.transform(Xb)[:, : self.n_base]
        F = self.ftir_imputer_.transform(Xf)[:, : self.n_ftir_]
        if self.mode == "resid":
            self.ridge_ = Ridge(alpha=self.ridge_alpha, fit_intercept=True)
            self.ridge_.fit(B, F)
            self.r2_train_ = float(r2_score(F, self.ridge_.predict(B), multioutput="uniform_average"))
            self.residual_std_ratio_ = float(np.mean(np.std(F - self.ridge_.predict(B), axis=0) /
                                                      np.maximum(np.std(F, axis=0), 1e-12)))
        else:
            self.ridge_ = None
            self.r2_train_ = np.nan
            self.residual_std_ratio_ = np.nan
        return self

    def transform(self, X):
        X = np.asarray(X, dtype=float)
        Xb, Xf = X[:, : self.n_base], X[:, self.n_base :]
        B_all = self.base_imputer_.transform(Xb)
        F_all = self.ftir_imputer_.transform(Xf)
        B = B_all[:, : self.n_base]
        F = F_all[:, : self.n_ftir_]
        F_ind = F_all[:, self.n_ftir_ :]
        if self.mode == "resid":
            F = F - self.ridge_.predict(B)
        return np.hstack([B_all, F, F_ind])


def make_model(seed, C, mode):
    steps = []
    if mode == "base183":
        steps.append(("prep", BasePrep()))
    else:
        steps.append(("prep", FTIRPrep(n_base=183, mode=("resid" if mode == "resid_ftir7" else "raw")))
        )
    steps += [
        ("scale", StandardScaler()),
        ("clf", LogisticRegression(C=C, penalty="l2", class_weight="balanced",
                                   solver="lbfgs", max_iter=3000, n_jobs=1,
                                   random_state=seed)),
    ]
    return Pipeline(steps)


def ordinal_proba(Xtr, ytr, Xte, seed, C, k, mode):
    p_cols = []
    for th in range(k - 1):
        yb = (ytr > th).astype(int)
        if len(np.unique(yb)) == 1:
            p_cols.append(np.full(len(Xte), float(yb[0])))
            continue
        model = make_model(seed, C, mode)
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


def inner_qwk(Xtr, ytr, groups_tr, seed, C, k, mode, n_splits=3):
    pred = np.full(len(ytr), -1, dtype=int)
    for itr, ite in p9.make_splits(ytr, groups_tr, seed, n_splits=n_splits):
        proba = ordinal_proba(Xtr[itr], ytr[itr], Xtr[ite], seed, C, k, mode)
        pred[ite] = np.argmax(proba, axis=1)
    if (pred < 0).any():
        return -np.inf
    return float(p9.grade_metrics(ytr, pred, k)["qwk"])


def nested_predict(X, y, groups, seed, cs, mode):
    k = int(y.max() + 1)
    oof = np.zeros((len(y), k), dtype=float)
    chosen = []
    for fi, (tr, te) in enumerate(p9.make_splits(y, groups, seed)):
        scores = {}
        for C in cs:
            scores[C] = inner_qwk(X[tr], y[tr], groups[tr], seed + 1000 + 37 * fi, C, k, mode)
        best_c = max(scores, key=scores.get)
        chosen.append(best_c)
        oof[te] = ordinal_proba(X[tr], y[tr], X[te], seed, best_c, k, mode)
    return oof, chosen


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="sanity", choices=["sanity", "full"])
    ap.add_argument("--seeds", nargs="*", type=int, default=SEEDS)
    ap.add_argument("--cs", nargs="*", type=float, default=CS)
    ap.add_argument("--sets", nargs="*", default=SETS, choices=SETS)
    ap.add_argument("--tag", default="sanity")
    args = ap.parse_args()
    if args.mode == "sanity" and args.seeds == SEEDS:
        args.seeds = [SEEDS[0]]

    t0 = time.time()
    # --- data construction: same provenance and target as P14 ---
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
    ftir_cols = [c for c in X7.columns if c not in X0.columns]
    assert len(ftir_cols) == 7, ftir_cols
    base = X0.loc[t["ids"]]
    ftir = X7.loc[t["ids"]][ftir_cols]
    X = np.hstack([base.values, ftir.values])
    y = np.array([p9.grade_from_cuts(v, t["schemas"]["t3_eng"]["cuts"]) for v in t["raw"]], dtype=int)
    assert X.shape == (301, 190), X.shape
    assert len(y) == 301 and np.bincount(y).tolist() == [33, 197, 71]
    print(f"data X={X.shape} y={np.bincount(y).tolist()} groups={len(set(t['groups']))}", flush=True)

    rows, chosen_rows, diag_rows = [], [], []
    for set_name in args.sets:
        print(f"SET {set_name}", flush=True)
        if set_name == "base183":
            Xs = base.values
        else:
            Xs = X
        for seed in args.seeds:
            proba, chosen = nested_predict(Xs, y, t["groups"], seed, args.cs, set_name)
            pred = np.argmax(proba, axis=1)
            m = p9.grade_metrics(y, pred, 3)
            rows.append({"target": "T", "set": set_name, "seed": seed, "n": len(y),
                         "qwk": m["qwk"], "mae": m["mae_grade"],
                         "high": m["high_grade_recall"], "over": m["overprediction_rate"],
                         "cost": m["mean_cost_over2"]})
            for fi, c in enumerate(chosen):
                chosen_rows.append({"set": set_name, "seed": seed, "fold": fi, "C": c})
            # Fold-level residual diagnostics: fitted on outer train only.
            if set_name != "base183":
                for fi, (tr, te) in enumerate(p9.make_splits(y, t["groups"], seed)):
                    prep = FTIRPrep(n_base=183, mode=("resid" if set_name == "resid_ftir7" else "raw"))
                    prep.fit(Xs[tr])
                    if set_name == "resid_ftir7":
                        diag_rows.append({"set": set_name, "seed": seed, "fold": fi,
                                          "n_train": len(tr),
                                          "ridge_r2": prep.r2_train_,
                                          "residual_std_ratio": prep.residual_std_ratio_})
            print(f"  {set_name} seed={seed} QWK={m['qwk']:.4f} C={chosen}", flush=True)

    df = pd.DataFrame(rows)
    cdf = pd.DataFrame(chosen_rows)
    ddf = pd.DataFrame(diag_rows)
    suffix = args.tag
    df.to_csv(EXP / f"results/p15_{suffix}_per_seed.csv", index=False,
              encoding="utf-8-sig", float_format="%.10g")
    cdf.to_csv(EXP / f"results/p15_{suffix}_chosen_C.csv", index=False,
               encoding="utf-8-sig")
    if len(ddf):
        ddf.to_csv(EXP / f"results/p15_{suffix}_diagnostics.csv", index=False,
                   encoding="utf-8-sig", float_format="%.10g")
    agg = df.groupby(["target", "set"]).agg(
        qwk=("qwk", "mean"), qwk_sd=("qwk", "std"), mae=("mae", "mean"),
        high=("high", "mean"), over=("over", "mean"), cost=("cost", "mean"),
        n=("n", "first")).reset_index()
    agg.to_csv(EXP / f"results/p15_{suffix}_summary.csv", index=False,
               encoding="utf-8-sig", float_format="%.10g")

    # Paired comparisons at the seed level.
    comparisons = [("resid_ftir7", "raw_ftir7"), ("resid_ftir7", "base183"), ("raw_ftir7", "base183")]
    drows = []
    for a, b in comparisons:
        av = df[df.set == a].set_index("seed")["qwk"]
        bv = df[df.set == b].set_index("seed")["qwk"]
        al = pd.concat([av.rename("a"), bv.rename("b")], axis=1).dropna()
        d = (al["a"] - al["b"]).to_numpy()
        tt = stats.ttest_rel(al["a"], al["b"]) if len(d) >= 3 else None
        wx = stats.wilcoxon(d) if len(d) >= 6 else None
        drows.append({
            "comparison": f"{a} - {b}", "delta_mean": float(d.mean()),
            "delta_sd": float(d.std(ddof=1)), "n_seed": int(len(d)),
            "t_p": float(tt.pvalue) if tt is not None else np.nan,
            "wilcoxon_p": float(wx.pvalue) if wx is not None else np.nan,
            "positive_seeds": int((d > 0).sum()),
        })
    delta = pd.DataFrame(drows)
    delta.to_csv(EXP / f"results/p15_{suffix}_delta.csv", index=False,
                 encoding="utf-8-sig", float_format="%.10g")
    config = {
        "date": "2026-11-25",
        "experiment": "P15 FTIR residualization",
        "target": "T three-grade, cuts [15,20]",
        "n": int(len(y)),
        "seeds": args.seeds,
        "cs": args.cs,
        "sets": args.sets,
        "residualization": "Ridge(alpha=1.0) fit on outer training base183 -> FTIR7; residual used as features; inner CV refits it on inner training",
        "model": "ordinal cumulative logistic, class_weight=balanced, L2, max_iter=3000",
        "preprocessing": "median imputation + missing indicators; StandardScaler after feature construction",
        "outer_cv": "StratifiedGroupKFold(5) by formula_id; T groups are unique in this cohort",
        "inner_cv": "StratifiedGroupKFold(3) by formula_id",
        "note": "no post-hoc feature subset selection; base183/raw7/resid7 are pre-specified",
    }
    (EXP / f"results/p15_{suffix}_config.json").write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n", agg.round(4).to_string(index=False))
    print("\n", delta.round(4).to_string(index=False))
    if len(ddf):
        print("\nresidual diagnostics:\n", ddf.groupby("set").agg(
            ridge_r2=("ridge_r2", "mean"), residual_std_ratio=("residual_std_ratio", "mean"),
            n_folds=("ridge_r2", "size")).round(4).to_string())
    print("elapsed", round(time.time() - t0, 1), "s")


if __name__ == "__main__":
    main()
