# -*- coding: utf-8 -*-
"""P16: FTIR block weighting with a row-shuffled placebo control.

Questions
---------
1. Is the FTIR8 gain real sample-specific information, or only extra
   parameters / L2 regularization?  Compare `full8` against `placebo8`,
   a same-dimensional row-shuffled FTIR block with the same marginals and
   covariance but no sample-target alignment.
2. Can one continuous block weight `w` replace P15's unstable hard subset
   selection?  `ftir8_w` multiplies the standardized FTIR block by w; w and C
   are selected inside every outer training fold.  `core4_w` is a parsimony
   control using P14's prior core4 subset (labelled post-hoc).

Leakage boundaries
------------------
- imputation, scaling, w, C and the model are fitted inside the outer training
  fold; inner C/w selection is fitted inside each inner training fold.
- the placebo is a seed-fixed row permutation of the FTIR block, generated
  without looking at y; it preserves FTIR marginals/covariance but destroys
  sample alignment.  Base features are unchanged.
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
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

import p09_grade_exhaustive as p9
import p10c_bench as p10c
import p0_clean_baseline as p0
from modeling import load_dataset, canon

SEEDS = [42, 202, 777, 1234, 2026, 31415, 2718, 1618, 5678, 9999]
CS = [0.5, 1.0, 1.5, 2.0]
WEIGHTS = [0.5, 1.0, 1.5, 2.0, 3.0, 4.0]
FTIR8 = list(p10c.FTIR_RAW8)
CORE4 = ["ftir_meoh_phen", "ftir_ch_all", "ftir_coc_all", "ftir_oh_phen"]
BASE_N = 183


class BlockWeightPrep(BaseEstimator, TransformerMixin):
    """Median-impute base/FTIR, scale all, then multiply the FTIR block by w.

    Output order: [base_imputed, base_indicators, ftir_imputed, ftir_indicators].
    The FTIR block is the trailing `n_ftir_block_` columns, so multiplying it
    after `StandardScaler` is not undone by scaling.  Base-only inputs are
    supported (n_ftir_block_ = 0).
    """

    def __init__(self, n_base: int = BASE_N, weight: float = 1.0):
        self.n_base = int(n_base)
        self.weight = float(weight)

    def fit(self, X, y=None):
        X = np.asarray(X, dtype=float)
        self.n_base_ = min(self.n_base, X.shape[1])
        Xb = X[:, : self.n_base_]
        self.base_imputer_ = SimpleImputer(
            strategy="median", add_indicator=True, keep_empty_features=True
        ).fit(Xb)
        if X.shape[1] > self.n_base_:
            Xf = X[:, self.n_base_ :]
            self.ftir_imputer_ = SimpleImputer(
                strategy="median", add_indicator=True, keep_empty_features=True
            ).fit(Xf)
            F = self.ftir_imputer_.transform(Xf)
            self.n_ftir_block_ = F.shape[1]
        else:
            self.ftir_imputer_ = None
            self.n_ftir_block_ = 0
            F = np.empty((len(X), 0), dtype=float)
        B = self.base_imputer_.transform(Xb)
        Z = np.hstack([B, F])
        self.scaler_ = StandardScaler().fit(Z)
        return self

    def transform(self, X):
        X = np.asarray(X, dtype=float)
        Xb = X[:, : self.n_base_]
        B = self.base_imputer_.transform(Xb)
        if self.ftir_imputer_ is None:
            Z = B
        else:
            F = self.ftir_imputer_.transform(X[:, self.n_base_ :])
            Z = np.hstack([B, F])
        Z = self.scaler_.transform(Z)
        if self.n_ftir_block_:
            Z = Z.copy()
            Z[:, -self.n_ftir_block_ :] *= self.weight
        return Z


def make_model(seed: int, C: float, w: float):
    return Pipeline([
        ("prep", BlockWeightPrep(n_base=BASE_N, weight=w)),
        ("clf", LogisticRegression(
            C=C, penalty="l2", class_weight="balanced", solver="lbfgs",
            max_iter=3000, n_jobs=1, random_state=seed,
        )),
    ])


def ordinal_proba(Xtr, ytr, Xte, seed: int, C: float, w: float, k: int = 3):
    p_cols = []
    for th in range(k - 1):
        yb = (ytr > th).astype(int)
        if len(np.unique(yb)) == 1:
            p_cols.append(np.full(len(Xte), float(yb[0])))
            continue
        model = make_model(seed, C, w)
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


def inner_qwk(Xtr, ytr, groups_tr, seed: int, C: float, w: float, k: int = 3):
    pred = np.full(len(ytr), -1, dtype=int)
    for itr, ite in p9.make_splits(ytr, groups_tr, seed, n_splits=3):
        pred[ite] = np.argmax(
            ordinal_proba(Xtr[itr], ytr[itr], Xtr[ite], seed, C, w, k), axis=1
        )
    if (pred < 0).any():
        return -np.inf
    return float(p9.grade_metrics(ytr, pred, k)["qwk"])


def select_outer(X, y, groups, seed, cs, weights, k=3):
    oof = np.zeros((len(y), k), dtype=float)
    chosen = []
    for fi, (tr, te) in enumerate(p9.make_splits(y, groups, seed)):
        scores = {}
        for w in weights:
            for C in cs:
                scores[(w, C)] = inner_qwk(
                    X[tr], y[tr], groups[tr], seed + 1000 + 37 * fi, C, w, k
                )
        best_w, best_c = max(scores, key=scores.get)
        chosen.append({"seed": seed, "fold": fi, "weight": best_w,
                       "C": best_c, "inner_qwk": scores[(best_w, best_c)]})
        oof[te] = ordinal_proba(X[tr], y[tr], X[te], seed, best_c, best_w, k)
    return oof, chosen


def holm(raw_p, names):
    """Holm adjust a small family; names order is the family order."""
    m = len(raw_p)
    order = np.argsort(raw_p)
    adjusted = np.ones(m, dtype=float)
    running = 0.0
    for rank, idx in enumerate(order):
        val = min(1.0, raw_p[idx] * (m - rank))
        running = max(running, val)
        adjusted[idx] = running
    return {name: float(adjusted[i]) for i, name in enumerate(names)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="sanity", choices=["sanity", "full"])
    ap.add_argument("--seeds", nargs="*", type=int, default=SEEDS)
    ap.add_argument("--cs", nargs="*", type=float, default=CS)
    ap.add_argument("--weights", nargs="*", type=float, default=WEIGHTS)
    ap.add_argument("--sets", nargs="*", default=[
        "base183", "full8", "placebo8", "ftir8_w", "core4_w"
    ], choices=["base183", "full8", "placebo8", "ftir8_w", "core4_w"])
    ap.add_argument("--tag", default="sanity")
    args = ap.parse_args()
    if args.mode == "sanity" and args.seeds == SEEDS:
        args.seeds = [SEEDS[0]]

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
    X8 = pd.read_csv(ROOT / "experiments/P13_feature_opt/data/feature_matrix_p13_t_ftir8.csv",
                     encoding="utf-8-sig").set_index("sample_id")
    X8.index = X8.index.astype(str)
    X8 = X8.loc[t["ids"]]
    base_cols = [c for c in X8.columns if c not in FTIR8]
    assert len(base_cols) == BASE_N and len(FTIR8) == 8, (len(base_cols), len(FTIR8))
    B = X8[base_cols].values
    F8 = X8[FTIR8].values
    F4 = X8[CORE4].values
    y = np.array([p9.grade_from_cuts(v, t["schemas"]["t3_eng"]["cuts"]) for v in t["raw"]], dtype=int)
    assert B.shape == (301, BASE_N) and F8.shape == (301, 8)
    assert len(y) == 301 and np.bincount(y).tolist() == [33, 197, 71]
    print(f"data base={B.shape} ftir8={F8.shape} y={np.bincount(y).tolist()} groups={len(set(t['groups']))}", flush=True)

    systems = {}
    for name in args.sets:
        if name == "base183":
            systems[name] = [B]
        elif name == "full8":
            systems[name] = [np.hstack([B, F8])]
        elif name == "ftir8_w":
            systems[name] = [np.hstack([B, F8])]
        elif name == "core4_w":
            systems[name] = [np.hstack([B, F4])]
        elif name == "placebo8":
            placebos = []
            for seed in args.seeds:
                rng = np.random.default_rng(seed)
                perm = rng.permutation(len(B))
                placebos.append(np.hstack([B, F8[perm]]))
            systems[name] = placebos

    rows, chosen_rows = [], []
    for name in args.sets:
        print(f"SET {name}", flush=True)
        for si, seed in enumerate(args.seeds):
            X = systems[name][si] if name == "placebo8" else systems[name][0]
            weights = [1.0] if name in ("base183", "full8", "placebo8") else args.weights
            proba, chosen = select_outer(X, y, t["groups"], seed, args.cs, weights, 3)
            pred = np.argmax(proba, axis=1)
            m = p9.grade_metrics(y, pred, 3)
            rows.append({
                "target": "T", "set": name, "seed": seed, "n": len(y),
                "n_features": X.shape[1],
                "qwk": m["qwk"], "mae": m["mae_grade"],
                "high": m["high_grade_recall"], "over": m["overprediction_rate"],
                "cost": m["mean_cost_over2"],
                "mean_chosen_w": float(np.mean([c["weight"] for c in chosen])),
                "mean_chosen_C": float(np.mean([c["C"] for c in chosen])),
            })
            chosen_rows.extend([{**c, "set": name} for c in chosen])
            print(f"  {name} seed={seed} QWK={m['qwk']:.4f} "
                  f"w={np.mean([c['weight'] for c in chosen]):.3f} "
                  f"C={np.mean([c['C'] for c in chosen]):.3f}", flush=True)

    df = pd.DataFrame(rows)
    cdf = pd.DataFrame(chosen_rows)
    suffix = args.tag
    df.to_csv(EXP / f"results/p16_{suffix}_per_seed.csv", index=False,
              encoding="utf-8-sig", float_format="%.10g")
    cdf.to_csv(EXP / f"results/p16_{suffix}_chosen.csv", index=False,
               encoding="utf-8-sig", float_format="%.10g")
    agg = df.groupby("set").agg(
        qwk=("qwk", "mean"), qwk_sd=("qwk", "std"), mae=("mae", "mean"),
        high=("high", "mean"), over=("over", "mean"), cost=("cost", "mean"),
        n_features=("n_features", "first"), mean_w=("mean_chosen_w", "mean"),
        mean_C=("mean_chosen_C", "mean"),
    ).reset_index()
    agg.to_csv(EXP / f"results/p16_{suffix}_summary.csv", index=False,
               encoding="utf-8-sig", float_format="%.10g")

    freq = cdf.groupby(["set", "weight", "C"]).size().reset_index(name="n_folds")
    freq["share"] = freq.apply(lambda r: r["n_folds"] / (cdf["set"] == r["set"]).sum(), axis=1)
    freq.to_csv(EXP / f"results/p16_{suffix}_weight_frequency.csv", index=False,
                encoding="utf-8-sig", float_format="%.10g")

    comparisons = [
        ("C1_full8_vs_placebo", "full8", "placebo8", True),
        ("C2_ftir8w_vs_full8", "ftir8_w", "full8", True),
        ("support_ftir8w_vs_base", "ftir8_w", "base183", False),
        ("support_core4w_vs_ftir8w", "core4_w", "ftir8_w", False),
    ]
    drows = []
    for label, a, b, primary in comparisons:
        av = df[df.set == a].set_index("seed")["qwk"]
        bv = df[df.set == b].set_index("seed")["qwk"]
        al = pd.concat([av.rename("a"), bv.rename("b")], axis=1).dropna()
        d = (al["a"] - al["b"]).to_numpy()
        tt = stats.ttest_rel(al["a"], al["b"]) if len(d) >= 3 else None
        wx = stats.wilcoxon(d) if len(d) >= 6 else None
        drows.append({
            "comparison": label, "a": a, "b": b, "delta_mean": float(d.mean()),
            "delta_sd": float(d.std(ddof=1)) if len(d) > 1 else np.nan,
            "n_seed": int(len(d)),
            "t_p": float(tt.pvalue) if tt is not None else np.nan,
            "wilcoxon_p": float(wx.pvalue) if wx is not None else np.nan,
            "positive_seeds": int((d > 0).sum()),
            "primary": bool(primary),
        })
    delta = pd.DataFrame(drows)
    primary = delta[delta["primary"]].copy()
    holm_map = holm(primary["t_p"].to_numpy(dtype=float), primary["comparison"].tolist())
    delta["holm_p"] = delta["comparison"].map(holm_map).fillna(delta["t_p"])
    delta.to_csv(EXP / f"results/p16_{suffix}_delta.csv", index=False,
                 encoding="utf-8-sig", float_format="%.10g")

    p14 = pd.read_csv(ROOT / "experiments/P14_evidence_chain/results/p14_t_drop_one_per_seed.csv")
    ref = p14[p14["drop"] == "ftir_oh_epox"][["seed", "qwk", "high", "cost"]].copy()
    ref.rename(columns={"qwk": "p14_190_fixed_qwk", "high": "p14_190_fixed_high",
                        "cost": "p14_190_fixed_cost"}, inplace=True)
    ref.to_csv(EXP / f"results/p16_{suffix}_p14_reference.csv", index=False,
               encoding="utf-8-sig", float_format="%.10g")

    config = {
        "date": "2026-11-25",
        "experiment": "P16 FTIR block weighting + row-shuffled placebo",
        "target": "T three-grade, cuts [15,20]",
        "n": 301,
        "base_n": BASE_N,
        "ftir8": FTIR8,
        "core4": CORE4,
        "seeds": args.seeds,
        "cs": args.cs,
        "weights": args.weights,
        "sets": args.sets,
        "placebo": "seed-fixed global row permutation of FTIR8; base unchanged; covariance preserved; y never used",
        "weighting": "impute -> StandardScaler -> multiply trailing FTIR block (values + missing indicators) by w",
        "selection": "inner 3-fold grouped QWK selects (w,C); outer test untouched",
        "model": "ordinal cumulative logistic, balanced, L2, max_iter=3000",
        "external_reviewer": "unavailable; local deterministic only",
    }
    (EXP / f"results/p16_{suffix}_config.json").write_text(
        json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n", agg.round(4).to_string(index=False))
    print("\n", delta.round(4).to_string(index=False))
    print("elapsed", round(time.time() - t0, 1), "s")


if __name__ == "__main__":
    main()
