# -*- coding: utf-8 -*-
"""P15-B: fully nested FTIR-subset selection for coating T-bend grade.

Why this exists
---------------
P14 selected the 190-dim set (183 + 7 FTIR, dropping ftir_oh_epox) by a
drop-one screen on the full 10-seed result, then ran a nested C search with that
set fixed.  That protects C selection but not feature-subset selection.  This
experiment makes the subset choice part of the outer training procedure:

  for each outer training fold:
      for each pre-specified FTIR subset and C:
          score on a 3-fold inner grouped CV
      choose the best (subset, C)
      refit on the outer training fold
      evaluate on the untouched outer test fold

Candidate subsets are the already-reported P14 subsets, not a new exhaustive
search: base183, full8, drop_oh_epox, drop_oh_epox_aroc, core4, core5.  The
result is an honest estimate of "choose a subset + C" rather than a post-hoc
estimate of the winning subset.

The residualization pilot (p15a) is kept separate; it is exploratory and must
not be merged into this confirmatory result.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "core"))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "experiments" / "P10_ftir_v3" / "scripts"))
sys.path.insert(0, str(ROOT / "experiments" / "P14_evidence_chain" / "scripts"))

import numpy as np
import pandas as pd
from scipy import stats

import p09_grade_exhaustive as p9
import p10c_bench as p10c
import p0_clean_baseline as p0
from modeling import load_dataset, canon
from p14_t_evidence import ordinal_proba_fold

SEEDS = [42, 202, 777, 1234, 2026, 31415, 2718, 1618, 5678, 9999]
CS = [0.5, 1.0, 1.5, 2.0]
FTIR8 = list(p10c.FTIR_RAW8)
CANDIDATES = {
    "base183": [],
    "full8": FTIR8,
    "drop_oh_epox": [c for c in FTIR8 if c != "ftir_oh_epox"],
    "drop_oh_epox_aroc": [c for c in FTIR8 if c not in ("ftir_oh_epox", "ftir_aroc_phen")],
    "core4": ["ftir_meoh_phen", "ftir_ch_all", "ftir_coc_all", "ftir_oh_phen"],
    "core5": ["ftir_meoh_phen", "ftir_ch_all", "ftir_coc_all", "ftir_oh_phen", "ftir_arsub_all"],
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="sanity", choices=["sanity", "full"])
    ap.add_argument("--seeds", nargs="*", type=int, default=SEEDS)
    ap.add_argument("--cs", nargs="*", type=float, default=CS)
    ap.add_argument("--candidates", nargs="*", default=list(CANDIDATES), choices=list(CANDIDATES))
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
    assert len(base_cols) == 183 and len(FTIR8) == 8, (len(base_cols), len(FTIR8))
    y = np.array([p9.grade_from_cuts(v, t["schemas"]["t3_eng"]["cuts"]) for v in t["raw"]], dtype=int)
    assert len(y) == 301 and np.bincount(y).tolist() == [33, 197, 71]

    cands = {name: X8[base_cols + CANDIDATES[name]].values for name in args.candidates}
    print("candidate shapes:", {k: v.shape for k, v in cands.items()}, flush=True)

    rows, chosen_rows = [], []
    for seed in args.seeds:
        oof = np.zeros((len(y), 3), dtype=float)
        for fi, (tr, te) in enumerate(p9.make_splits(y, t["groups"], seed)):
            scores = {}
            for name, X in cands.items():
                for C in args.cs:
                    scores[(name, C)] = inner_qwk(
                        X[tr], y[tr], t["groups"][tr], seed + 1000 + 37 * fi, C, 3
                    )
            best_name, best_c = max(scores, key=scores.get)
            chosen_rows.append({"seed": seed, "fold": fi, "candidate": best_name,
                                "C": best_c, "inner_qwk": scores[(best_name, best_c)]})
            oof[te] = ordinal_proba_fold(
                cands[best_name][tr], y[tr], cands[best_name][te], seed, best_c, 3
            )
        pred = np.argmax(oof, axis=1)
        m = p9.grade_metrics(y, pred, 3)
        rows.append({"target": "T", "protocol": "nested_subset_C", "seed": seed,
                     "n": len(y), "qwk": m["qwk"], "mae": m["mae_grade"],
                     "high": m["high_grade_recall"], "over": m["overprediction_rate"],
                     "cost": m["mean_cost_over2"]})
        print(f"seed={seed} nested_subset_C QWK={m['qwk']:.4f}", flush=True)

    df = pd.DataFrame(rows)
    cdf = pd.DataFrame(chosen_rows)
    suffix = args.tag
    df.to_csv(EXP / f"results/p15b_{suffix}_per_seed.csv", index=False,
              encoding="utf-8-sig", float_format="%.10g")
    cdf.to_csv(EXP / f"results/p15b_{suffix}_chosen.csv", index=False,
               encoding="utf-8-sig")
    agg = df[["qwk", "mae", "high", "over", "cost"]].agg(["mean", "std"]).T.reset_index()
    agg.columns = ["metric", "mean", "sd"]
    agg.to_csv(EXP / f"results/p15b_{suffix}_summary.csv", index=False,
               encoding="utf-8-sig", float_format="%.10g")
    freq = cdf.groupby(["candidate", "C"]).size().reset_index(name="n_folds")
    freq["share"] = freq["n_folds"] / len(cdf)
    freq = freq.sort_values(["n_folds", "candidate"], ascending=[False, True])
    freq.to_csv(EXP / f"results/p15b_{suffix}_selection_frequency.csv", index=False,
                encoding="utf-8-sig", float_format="%.10g")

    # Reference: the P14 fixed-C2 190 set, per seed.  This is a post-hoc reference,
    # not a paired nested-selection baseline.
    p14 = pd.read_csv(ROOT / "experiments/P14_evidence_chain/results/p14_t_drop_one_per_seed.csv")
    ref = p14[p14["drop"] == "ftir_oh_epox"][["seed", "qwk"]].rename(columns={"qwk": "p14_190_fixed_qwk"})
    cmp = df[["seed", "qwk"]].rename(columns={"qwk": "nested_qwk"}).merge(ref, on="seed", how="left")
    cmp["delta_vs_p14_fixed"] = cmp["nested_qwk"] - cmp["p14_190_fixed_qwk"]
    cmp.to_csv(EXP / f"results/p15b_{suffix}_vs_p14.csv", index=False,
               encoding="utf-8-sig", float_format="%.10g")
    d = cmp["delta_vs_p14_fixed"].dropna().to_numpy()
    delta = pd.DataFrame([{
        "comparison": "nested_subset_C - P14_190_fixed_C2",
        "delta_mean": float(d.mean()) if len(d) else np.nan,
        "delta_sd": float(d.std(ddof=1)) if len(d) else np.nan,
        "n_seed": int(len(d)),
        "t_p": float(stats.ttest_rel(cmp["nested_qwk"], cmp["p14_190_fixed_qwk"]).pvalue) if len(d) >= 3 else np.nan,
        "positive_seeds": int((d > 0).sum()) if len(d) else 0,
    }])
    delta.to_csv(EXP / f"results/p15b_{suffix}_delta.csv", index=False,
                 encoding="utf-8-sig", float_format="%.10g")

    config = {
        "date": "2026-11-25",
        "experiment": "P15-B nested FTIR subset + C selection",
        "target": "T three-grade, cuts [15,20]",
        "n": 301,
        "seeds": args.seeds,
        "cs": args.cs,
        "candidates": args.candidates,
        "candidate_definitions": {k: CANDIDATES[k] for k in args.candidates},
        "outer_cv": "StratifiedGroupKFold(5) by formula_id",
        "inner_cv": "StratifiedGroupKFold(3) by formula_id",
        "model": "ordinal cumulative logistic, class_weight=balanced, L2, max_iter=3000",
        "selection": "inner QWK chooses among pre-specified subset x C combinations; the outer test fold is untouched",
        "reference": "P14 190 fixed C2 is a post-hoc reference, not a nested baseline",
    }
    (EXP / f"results/p15b_{suffix}_config.json").write_text(
        json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n", agg.round(4).to_string(index=False))
    print("\nselection frequency:\n", freq.round(4).to_string(index=False))
    print("\nvs P14:\n", delta.round(4).to_string(index=False))
    print("elapsed", round(time.time() - t0, 1), "s")


def inner_qwk(Xtr, ytr, groups_tr, seed, C, k, n_splits=3):
    pred = np.full(len(ytr), -1, dtype=int)
    for itr, ite in p9.make_splits(ytr, groups_tr, seed, n_splits=n_splits):
        proba = ordinal_proba_fold(Xtr[itr], ytr[itr], Xtr[ite], seed, C, k)
        pred[ite] = np.argmax(proba, axis=1)
    if (pred < 0).any():
        return -np.inf
    return float(p9.grade_metrics(ytr, pred, k)["qwk"])


if __name__ == "__main__":
    main()
