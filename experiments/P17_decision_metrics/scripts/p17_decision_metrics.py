# -*- coding: utf-8 -*-
"""P17: decision-layer benchmark for coating T-bend under fixed data.

The model and features are frozen; this script only turns existing OOF
probabilities into decision policies and decision metrics.

Systems
-------
- full8: P16's 183 + 8 FTIR block with w=1, C nested by inner grouped CV.
- p14_190: P14's post-hoc fixed 190-dim set with C=2 (descriptive reference).

Policies are fixed, pre-registered thresholds. No threshold is tuned on the
outer test fold. OOF probabilities are generated with the same outer
StratifiedGroupKFold(5) by formula_id and 10 seeds used in P14/P16.
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
sys.path.insert(0, str(ROOT / "experiments" / "P14_evidence_chain" / "scripts"))
sys.path.insert(0, str(ROOT / "experiments" / "P16_ftir_block_weight" / "scripts"))

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.metrics import cohen_kappa_score

import p09_grade_exhaustive as p9
import p10c_bench as p10c
import p0_clean_baseline as p0
import p14_t_evidence as p14
import p16_block_weight as p16
from modeling import load_dataset, canon

SEEDS = [42, 202, 777, 1234, 2026, 31415, 2718, 1618, 5678, 9999]
CS = [0.5, 1.0, 1.5, 2.0]
BASE_N = 183
FTIR8 = list(p10c.FTIR_RAW8)
P14_FTIR7 = [c for c in FTIR8 if c != "ftir_oh_epox"]

# Pre-registered policy thresholds.
HIGH_T = 0.35
LOW_T = 0.10
SELECTIVE_T = 0.60
TEST_COST = 1.0
COST_FALSE_RELEASE = 10.0
COST_FALSE_REJECT = 3.0
COST_TEST = 1.0

SELECTIVE_GRID = [0.40, 0.50, 0.60, 0.70, 0.80]
HIGH_GUARD_GRID = [0.20, 0.30, 0.35, 0.40, 0.50, 0.60]
POLICIES = ["argmax", "cost", "high_guard", "three_way", "selective", "cost_abstain"]


def load_data():
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
    y = np.array([p9.grade_from_cuts(v, t["schemas"]["t3_eng"]["cuts"]) for v in t["raw"]], dtype=int)
    assert len(y) == 301 and np.bincount(y).tolist() == [33, 197, 71]
    B = X8[base_cols].values
    F8 = X8[FTIR8].values
    X_full8 = np.hstack([B, F8])
    X_p14 = X8[base_cols + P14_FTIR7].values
    assert X_full8.shape == (301, 191), X_full8.shape
    assert X_p14.shape == (301, 190), X_p14.shape
    return {
        "ids": np.array(t["ids"]), "y": y, "groups": t["groups"],
        "X_full8": X_full8, "X_p14": X_p14,
        "base": B, "ftir8": F8,
    }


def generate_oof(data, systems, seeds, tag):
    rows = []
    for system in systems:
        print(f"SYSTEM {system}", flush=True)
        for seed in seeds:
            if system == "full8":
                proba, chosen = p16.select_outer(data["X_full8"], data["y"], data["groups"],
                                                 seed, CS, [1.0], 3)
            elif system == "p14_190":
                proba = p14.ordinal_proba_fixed(data["X_p14"], data["y"], data["groups"],
                                                seed, 2.0)
                chosen = [{"seed": seed, "fold": i, "weight": 1.0, "C": 2.0,
                           "inner_qwk": np.nan}
                          for i in range(5)]
            else:
                raise ValueError(system)
            assert proba.shape == (len(data["y"]), 3), proba.shape
            assert np.allclose(proba.sum(axis=1), 1.0, atol=1e-6)
            for i, sid in enumerate(data["ids"]):
                rows.append({"system": system, "seed": seed, "sample_id": str(sid),
                             "y": int(data["y"][i]),
                             "p0": float(proba[i, 0]), "p1": float(proba[i, 1]),
                             "p2": float(proba[i, 2])})
            print(f"  {system} seed={seed} OOF done", flush=True)
    df = pd.DataFrame(rows)
    df.to_csv(EXP / f"results/p17_oof_proba_{tag}.csv", index=False,
              encoding="utf-8-sig", float_format="%.10g")
    return df


def policy_predict(proba, policy, high_t=HIGH_T, low_t=LOW_T, tau=SELECTIVE_T,
                   test_cost=TEST_COST):
    """Return (pred, abstain) arrays. abstain=False means a decision is made."""
    proba = np.asarray(proba, dtype=float)
    n, k = proba.shape
    pred = np.argmax(proba, axis=1)
    abstain = np.zeros(n, dtype=bool)
    c = p9.cost_matrix(k)

    if policy == "argmax":
        pass
    elif policy == "cost":
        pred = np.argmin(proba @ c, axis=1)
    elif policy == "high_guard":
        # If high risk is above the gate, directly reject; otherwise choose low/mid.
        high = proba[:, 2] >= high_t
        lowmid = proba[:, :2]
        lowmid_pred = np.argmax(lowmid, axis=1)
        pred = np.where(high, 2, lowmid_pred)
    elif policy == "three_way":
        high = proba[:, 2] >= high_t
        low = proba[:, 2] <= low_t
        abstain = ~(high | low)
        lowmid_pred = np.argmax(proba[:, :2], axis=1)
        pred = np.where(high, 2, lowmid_pred)
    elif policy == "selective":
        abstain = proba.max(axis=1) < tau
    elif policy == "cost_abstain":
        expected = proba @ c
        pred = np.argmin(expected, axis=1)
        abstain = expected.min(axis=1) > test_cost
    else:
        raise ValueError(policy)
    return pred.astype(int), abstain


def decision_metrics(y, pred, abstain):
    y = np.asarray(y, dtype=int)
    pred = np.asarray(pred, dtype=int)
    abstain = np.asarray(abstain, dtype=bool)
    accepted = ~abstain
    true_high = y == 2
    true_low = y <= 1
    pred_high = (pred == 2) & accepted
    release = (pred <= 1) & accepted
    test = abstain

    false_release = release & true_high
    false_reject = pred_high & true_low
    tp_high = pred_high & true_high
    high_accepted = true_high & accepted
    high_tested = true_high & test
    n_high = int(true_high.sum())
    n_high_accepted = int(high_accepted.sum())
    n_low = int(true_low.sum())

    operational_cost = float(np.mean(
        COST_FALSE_RELEASE * false_release.astype(float) +
        COST_FALSE_REJECT * false_reject.astype(float) +
        COST_TEST * test.astype(float)
    ))
    # Grade cost only on accepted decisions; abstain has no grade decision.
    grade_cost = np.nan
    if accepted.any():
        c = p9.cost_matrix(3)
        grade_cost = float(np.mean(c[y[accepted], pred[accepted]]))
    qwk = np.nan
    if accepted.any() and len(np.unique(y[accepted])) >= 2:
        qwk = float(cohen_kappa_score(y[accepted], pred[accepted], weights="quadratic",
                                      labels=[0, 1, 2]))
    mae = np.nan
    if accepted.any():
        mae = float(np.mean(np.abs(y[accepted] - pred[accepted])))
    severe_over = np.nan
    if accepted.any():
        severe_over = float(np.mean((pred[accepted] - y[accepted]) >= 2))
    high_precision = np.nan
    if pred_high.any():
        high_precision = float(tp_high.sum() / pred_high.sum())
    return {
        "n": int(len(y)),
        "n_high": n_high,
        "coverage": float(accepted.mean()),
        "test_rate": float(test.mean()),
        "release_rate": float(release.mean()),
        "reject_rate": float(pred_high.mean()),
        "pred_high_rate": float(pred_high.mean()),
        "false_release_rate": float(false_release.sum() / n_high) if n_high else np.nan,
        "false_reject_rate": float(false_reject.sum() / n_low) if n_low else np.nan,
        "high_grade_recall": float(tp_high.sum() / n_high) if n_high else np.nan,
        "high_grade_recall_accepted": float((tp_high & high_accepted).sum() / n_high_accepted)
        if n_high_accepted else np.nan,
        "high_test_rate": float(high_tested.sum() / n_high) if n_high else np.nan,
        "high_precision": high_precision,
        "operational_cost": operational_cost,
        "mean_cost_over2": grade_cost,
        "qwk": qwk,
        "mae_grade": mae,
        "severe_overprediction_rate": severe_over,
    }


def policy_table(oof, systems):
    rows = []
    for system in systems:
        sdf = oof[oof.system == system]
        for seed in sorted(sdf.seed.unique()):
            s = sdf[sdf.seed == seed].sort_values("sample_id")
            proba = s[["p0", "p1", "p2"]].to_numpy()
            y = s["y"].to_numpy()
            for policy in POLICIES:
                pred, abstain = policy_predict(proba, policy)
                m = decision_metrics(y, pred, abstain)
                m.update({"system": system, "seed": int(seed), "policy": policy})
                rows.append(m)
    return pd.DataFrame(rows)


def risk_curves(oof, systems):
    rows = []
    for system in systems:
        sdf = oof[oof.system == system]
        for seed in sorted(sdf.seed.unique()):
            s = sdf[sdf.seed == seed].sort_values("sample_id")
            proba = s[["p0", "p1", "p2"]].to_numpy()
            y = s["y"].to_numpy()
            for tau in SELECTIVE_GRID:
                pred, abstain = policy_predict(proba, "selective", tau=tau)
                m = decision_metrics(y, pred, abstain)
                m.update({"system": system, "seed": int(seed), "curve": "selective", "tau": tau})
                rows.append(m)
            for t in HIGH_GUARD_GRID:
                pred, abstain = policy_predict(proba, "high_guard", high_t=t)
                m = decision_metrics(y, pred, abstain)
                m.update({"system": system, "seed": int(seed), "curve": "high_guard", "tau": t})
                rows.append(m)
    return pd.DataFrame(rows)


def summarize(df, keys):
    metrics = ["coverage", "test_rate", "release_rate", "reject_rate", "pred_high_rate",
               "false_release_rate", "false_reject_rate", "high_grade_recall",
               "high_grade_recall_accepted", "high_test_rate", "high_precision",
               "operational_cost", "mean_cost_over2", "qwk",
               "mae_grade", "severe_overprediction_rate"]
    out = df.groupby(keys).agg({**{m: ["mean", "std"] for m in metrics},
                                  "n": "first", "n_high": "first"}).reset_index()
    out.columns = ["_".join([c for c in col if c]) if isinstance(col, tuple) else col
                   for col in out.columns]
    return out


def paired_deltas(df, systems):
    rows = []
    metrics = ["operational_cost", "false_release_rate", "test_rate", "coverage",
               "high_grade_recall", "high_grade_recall_accepted", "high_test_rate",
               "high_precision", "pred_high_rate", "qwk",
               "mean_cost_over2", "severe_overprediction_rate", "mae_grade"]
    # direction: 1 = larger is better, -1 = smaller is better
    direction = {"operational_cost": -1, "false_release_rate": -1, "test_rate": -1,
                 "coverage": 1, "high_grade_recall": 1, "high_grade_recall_accepted": 1,
                 "high_test_rate": -1, "high_precision": 1,
                 "pred_high_rate": 0, "qwk": 1, "mean_cost_over2": -1,
                 "severe_overprediction_rate": -1, "mae_grade": -1}
    for system in systems:
        base = df[(df.system == system) & (df.policy == "argmax")].set_index("seed")
        for policy in POLICIES:
            if policy == "argmax":
                continue
            other = df[(df.system == system) & (df.policy == policy)].set_index("seed")
            for m in metrics:
                a = base[m].astype(float)
                b = other[m].astype(float)
                z = pd.concat([a.rename("base"), b.rename("policy")], axis=1).dropna()
                d = (z["policy"] - z["base"]).to_numpy()
                if len(d) < 3:
                    continue
                tt = stats.ttest_rel(z["policy"], z["base"])
                wx = stats.wilcoxon(d) if len(d) >= 6 and np.any(d != 0) else None
                better = int((d * direction[m] > 0).sum()) if direction[m] else 0
                rows.append({
                    "system": system, "policy": policy, "metric": m,
                    "delta_mean": float(d.mean()),
                    "delta_sd": float(d.std(ddof=1)),
                    "n_seed": int(len(d)),
                    "t_p": float(tt.pvalue),
                    "wilcoxon_p": float(wx.pvalue) if wx is not None else np.nan,
                    "better_seeds": better,
                    "direction": direction[m],
                })
    return pd.DataFrame(rows)


def claim_check(summary, deltas):
    checks = {}
    if deltas.empty or "system" not in deltas.columns:
        for system in sorted(summary.system.unique()):
            checks[system] = {
                "C1_three_way": {"system": system, "pass": False,
                                 "error": "sanity: paired deltas need >=3 seeds"},
                "C2_selective": {"system": system, "pass": False,
                                 "error": "sanity: paired deltas need >=3 seeds"},
            }
        return checks
    for system in sorted(summary.system.unique()):
        s = summary[summary.system == system].set_index("policy")
        d = deltas[(deltas.system == system) & (deltas.metric == "operational_cost")]
        dp = deltas[(deltas.system == system) & (deltas.metric == "false_release_rate")]
        dh = deltas[(deltas.system == system) & (deltas.metric == "high_grade_recall")]
        dq = deltas[(deltas.system == system) & (deltas.metric == "qwk")]
        # C1 three_way
        c1 = {}
        try:
            tw = s.loc["three_way"]
            base = s.loc["argmax"]
            c1 = {
                "system": system,
                "operational_cost": float(tw["operational_cost_mean"]),
                "base_cost": float(base["operational_cost_mean"]),
                "delta_cost": float(tw["operational_cost_mean"] - base["operational_cost_mean"]),
                "false_release": float(tw["false_release_rate_mean"]),
                "base_false_release": float(base["false_release_rate_mean"]),
                "relative_false_release_reduction": float(
                    (base["false_release_rate_mean"] - tw["false_release_rate_mean"]) /
                    max(base["false_release_rate_mean"], 1e-12)),
                "test_rate": float(tw["test_rate_mean"]),
                "cost_p": float(d[d.policy == "three_way"].t_p.iloc[0]) if len(d[d.policy == "three_way"]) else np.nan,
                "false_release_p": float(dp[dp.policy == "three_way"].t_p.iloc[0]) if len(dp[dp.policy == "three_way"]) else np.nan,
                "better_seeds_cost": int(d[d.policy == "three_way"].better_seeds.iloc[0]) if len(d[d.policy == "three_way"]) else 0,
                "better_seeds_false_release": int(dp[dp.policy == "three_way"].better_seeds.iloc[0]) if len(dp[dp.policy == "three_way"]) else 0,
            }
            c1["pass"] = bool(
                c1["delta_cost"] <= -0.10 and
                c1["relative_false_release_reduction"] >= 0.30 and
                c1["test_rate"] <= 0.35 and
                c1["cost_p"] < 0.05 and
                c1["false_release_p"] < 0.05 and
                c1["better_seeds_cost"] >= 7 and
                c1["better_seeds_false_release"] >= 7
            )
        except Exception as e:
            c1 = {"system": system, "pass": False, "error": str(e)}
        # C2 selective tau=0.60
        c2 = {}
        try:
            se = s.loc["selective"]
            base = s.loc["argmax"]
            c2 = {
                "system": system,
                "coverage": float(se["coverage_mean"]),
                "false_release": float(se["false_release_rate_mean"]),
                "base_false_release": float(base["false_release_rate_mean"]),
                "relative_false_release_reduction": float(
                    (base["false_release_rate_mean"] - se["false_release_rate_mean"]) /
                    max(base["false_release_rate_mean"], 1e-12)),
                "high_recall": float(se["high_grade_recall_mean"]),
                "base_high_recall": float(base["high_grade_recall_mean"]),
                "qwk": float(se["qwk_mean"]),
                "base_qwk": float(base["qwk_mean"]),
                "qwk_delta": float(se["qwk_mean"] - base["qwk_mean"]),
                "false_release_p": float(dp[dp.policy == "selective"].t_p.iloc[0]) if len(dp[dp.policy == "selective"]) else np.nan,
                "better_seeds_false_release": int(dp[dp.policy == "selective"].better_seeds.iloc[0]) if len(dp[dp.policy == "selective"]) else 0,
            }
            c2["pass"] = bool(
                c2["coverage"] >= 0.70 and
                c2["relative_false_release_reduction"] >= 0.30 and
                (c2["high_recall"] - c2["base_high_recall"]) >= -0.05 and
                c2["qwk_delta"] >= -0.05 and
                c2["false_release_p"] < 0.05 and
                c2["better_seeds_false_release"] >= 7
            )
        except Exception as e:
            c2 = {"system": system, "pass": False, "error": str(e)}
        checks[system] = {"C1_three_way": c1, "C2_selective": c2}
    return checks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="sanity", choices=["sanity", "full"])
    ap.add_argument("--seeds", nargs="*", type=int, default=SEEDS)
    ap.add_argument("--systems", nargs="*", default=["full8", "p14_190"],
                    choices=["full8", "p14_190"])
    ap.add_argument("--tag", default="sanity")
    args = ap.parse_args()
    if args.mode == "sanity" and args.seeds == SEEDS:
        args.seeds = [SEEDS[0]]
    t0 = time.time()

    data = load_data()
    print(f"data n={len(data['y'])} groups={len(set(data['groups']))} "
          f"full8={data['X_full8'].shape} p14={data['X_p14'].shape}", flush=True)
    oof = generate_oof(data, args.systems, args.seeds, args.tag)
    pol = policy_table(oof, args.systems)
    curves = risk_curves(oof, args.systems)

    pol.to_csv(EXP / f"results/p17_policy_per_seed_{args.tag}.csv", index=False,
               encoding="utf-8-sig", float_format="%.10g")
    sumdf = summarize(pol, ["system", "policy"])
    sumdf.to_csv(EXP / f"results/p17_policy_summary_{args.tag}.csv", index=False,
                 encoding="utf-8-sig", float_format="%.10g")
    delta = paired_deltas(pol, args.systems)
    delta.to_csv(EXP / f"results/p17_policy_delta_{args.tag}.csv", index=False,
                 encoding="utf-8-sig", float_format="%.10g")
    curves.to_csv(EXP / f"results/p17_risk_coverage_{args.tag}.csv", index=False,
                  encoding="utf-8-sig", float_format="%.10g")

    checks = claim_check(sumdf, delta)
    (EXP / f"results/p17_claim_check_{args.tag}.json").write_text(
        json.dumps(checks, ensure_ascii=False, indent=2), encoding="utf-8")
    config = {
        "date": "2026-11-26",
        "experiment": "P17 decision metrics for T-bend",
        "systems": args.systems,
        "seeds": args.seeds,
        "target": "T three-grade, cuts [15,20]",
        "n": 301,
        "policies": POLICIES,
        "thresholds": {"high_guard": HIGH_T, "three_way": [LOW_T, HIGH_T],
                       "selective": SELECTIVE_T, "cost_abstain_test_cost": TEST_COST},
        "operational_cost": {"false_release": COST_FALSE_RELEASE,
                             "false_reject": COST_FALSE_REJECT, "test": COST_TEST},
        "note": "No new data; OOF only; p14_190 is post-hoc fixed reference",
        "external_reviewer": "unavailable; local deterministic only",
    }
    (EXP / f"results/p17_config_{args.tag}.json").write_text(
        json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\nPOLICY SUMMARY\n", sumdf.round(4).to_string(index=False))
    print("\nCLAIM CHECK\n", json.dumps(checks, ensure_ascii=False, indent=2))
    print("elapsed", round(time.time() - t0, 1), "s")


if __name__ == "__main__":
    main()
