# -*- coding: utf-8 -*-
"""P18: nested, calibrated decision policy for T-bend.

Question
--------
P17 showed that a fixed three-way risk gate can cut false release, but its
thresholds were pre-set, its probabilities were uncalibrated, and a single
example cost matrix drove the conclusion.  P18 asks whether a strictly nested
policy (thresholds selected only on inner grouped OOF) plus temperature
calibration can preserve the risk gate without paying for it through more
high predictions or more retests.

Design
------
- Data: 301 epoxy-phenolic T samples, cuts [15, 20], formula_id groups.
- Outer: StratifiedGroupKFold(5), 10 seeds.
- Inner: StratifiedGroupKFold(4) on each outer training fold.
- Model: P16 full8 (183 + 8 FTIR), C=2.0 fixed, w=1.0 fixed.  No feature or
  model-family change; the experiment isolates the decision layer.
- Calibration: temperature scaling fitted on inner OOF only; outer test never
  selects T or thresholds.
- Thresholds: three-way (high, low) and selective (tau), selected on inner OOF
  by expected operational cost subject to feasibility constraints.
- Sensitivity: false-release weight {5,10,20}, false-reject weight {2,3,5},
  test capacity {15%,25%,35%}.

This script deliberately does not use outer-test labels to choose a threshold.
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
sys.path.insert(0, str(ROOT / "experiments" / "P17_decision_metrics" / "scripts"))

import numpy as np
import pandas as pd
from scipy import stats
from scipy.optimize import minimize_scalar
from sklearn.metrics import cohen_kappa_score

import p09_grade_exhaustive as p9
import p16_block_weight as p16
from p17_decision_metrics import load_data as p17_load_data

SEEDS = [42, 202, 777, 1234, 2026, 31415, 2718, 1618, 5678, 9999]
C_FIXED = 2.0
W_FIXED = 1.0

# P17 fixed reference thresholds.
HIGH_T = 0.35
LOW_T = 0.10
SELECTIVE_T = 0.60

MAX_FALSE_RELEASE = 0.05
MAX_TEST_PRIMARY = 0.25
MAX_HIGH_RECALL_DROP = 0.05
MAX_HIGH_PRECISION_DROP = 0.05
MAX_PRED_HIGH = 0.38588  # true high 71/301 = 0.23588 + 0.15
MIN_COVERAGE = 0.70

COST_GRID = [(5.0, 2.0), (5.0, 3.0), (10.0, 2.0), (10.0, 3.0),
             (10.0, 5.0), (20.0, 3.0), (20.0, 5.0)]
CAP_GRID = [0.15, 0.25, 0.35]
PRIMARY = (10.0, 3.0, 0.25)

THREE_H = np.round(np.arange(0.20, 0.801, 0.05), 2)
THREE_L = np.round(np.arange(0.00, 0.301, 0.05), 2)
SELECTIVE_TAU = np.round(np.arange(0.40, 0.901, 0.05), 2)

PRIMARY_THREE = "nested_three_way_temp_primary"
PRIMARY_SELECTIVE = "nested_selective_temp_primary"
PRIMARY_ARMS = [PRIMARY_THREE, PRIMARY_SELECTIVE]


def _finite(x, default=0.0):
    return float(x) if np.isfinite(x) else float(default)


def temp_scale(proba, temperature):
    """Temperature scaling on log-probabilities; returns a simplex."""
    p = np.clip(np.asarray(proba, dtype=float), 1e-12, 1.0)
    z = np.log(p) / float(temperature)
    z = z - z.max(axis=1, keepdims=True)
    p2 = np.exp(z)
    p2 = p2 / p2.sum(axis=1, keepdims=True)
    p2 = np.clip(p2, 1e-12, 1.0)
    return p2 / p2.sum(axis=1, keepdims=True)


def nll(proba, y, temperature=1.0):
    p = temp_scale(proba, temperature)
    return float(-np.mean(np.log(np.clip(p[np.arange(len(y)), np.asarray(y, dtype=int)], 1e-12, 1.0))))


def ece(proba, y, n_bins=10):
    p = np.asarray(proba, dtype=float)
    conf = p.max(axis=1)
    pred = p.argmax(axis=1)
    correct = (pred == np.asarray(y, dtype=int)).astype(float)
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    out = 0.0
    for i in range(n_bins):
        mask = (conf >= edges[i]) & (conf < edges[i + 1] if i < n_bins - 1 else conf <= edges[i + 1])
        if mask.any():
            out += float(mask.mean()) * abs(float(correct[mask].mean()) - float(conf[mask].mean()))
    return out


def fit_temperature(proba, y):
    """Fit one scalar T on inner OOF by NLL; bounded to avoid a degenerate fit."""
    if len(np.unique(y)) < 2:
        return 1.0
    res = minimize_scalar(
        lambda t: nll(proba, y, float(t)),
        bounds=(0.50, 3.00), method="bounded",
        options={"xatol": 1e-4},
    )
    if not res.success or not np.isfinite(res.x):
        return 1.0
    return float(res.x)


def apply_policy(proba, policy, params):
    """Return predicted grade and abstain mask.

    abstain=False means a grade decision is made (release low/mid or reject high).
    """
    p = np.asarray(proba, dtype=float)
    n = len(p)
    pred = np.argmax(p, axis=1).astype(int)
    abstain = np.zeros(n, dtype=bool)

    if policy == "argmax":
        pass
    elif policy == "three_way":
        high_t = float(params["high"])
        low_t = float(params["low"])
        high = p[:, 2] >= high_t
        low = p[:, 2] <= low_t
        abstain = ~(high | low)
        pred = np.where(high, 2, np.argmax(p[:, :2], axis=1)).astype(int)
    elif policy == "selective":
        tau = float(params["tau"])
        abstain = p.max(axis=1) < tau
    else:
        raise ValueError(policy)
    return pred, abstain


def selection_metrics(y, pred, abstain, cfr, crej):
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
    n_high = int(true_high.sum())
    n_low = int(true_low.sum())
    tp_high = pred_high & true_high
    high_precision = float(tp_high.sum() / pred_high.sum()) if pred_high.any() else np.nan
    return {
        "coverage": float(accepted.mean()),
        "test_rate": float(test.mean()),
        "false_release_rate": float(false_release.sum() / n_high) if n_high else np.nan,
        "false_reject_rate": float(false_reject.sum() / n_low) if n_low else np.nan,
        "high_grade_recall": float(tp_high.sum() / n_high) if n_high else np.nan,
        "pred_high_rate": float(pred_high.mean()),
        "high_precision": high_precision,
        "operational_cost": float(np.mean(
            cfr * false_release.astype(float) +
            crej * false_reject.astype(float) +
            test.astype(float)
        )),
    }


def final_metrics(y, pred, abstain, cfr, crej):
    m = selection_metrics(y, pred, abstain, cfr, crej)
    y = np.asarray(y, dtype=int)
    pred = np.asarray(pred, dtype=int)
    abstain = np.asarray(abstain, dtype=bool)
    accepted = ~abstain
    qwk = np.nan
    mae = np.nan
    severe = np.nan
    high_test_rate = np.nan
    accepted_high_recall = np.nan
    if accepted.any():
        mae = float(np.mean(np.abs(y[accepted] - pred[accepted])))
        severe = float(np.mean((pred[accepted] - y[accepted]) >= 2))
        if len(np.unique(y[accepted])) >= 2:
            qwk = float(cohen_kappa_score(y[accepted], pred[accepted], weights="quadratic",
                                          labels=[0, 1, 2]))
        nh = int((y[accepted] == 2).sum())
        if nh:
            accepted_high_recall = float(((pred[accepted] == 2) & (y[accepted] == 2)).sum() / nh)
    true_high = y == 2
    if true_high.any():
        high_test_rate = float((true_high & abstain).sum() / true_high.sum())
    m.update({"qwk": qwk, "mae_grade": mae, "severe_overprediction_rate": severe,
              "high_test_rate": high_test_rate,
              "high_grade_recall_accepted": accepted_high_recall})
    return m


def candidates(policy):
    if policy == "three_way":
        for h in THREE_H:
            for l in THREE_L:
                if l < h:
                    yield {"high": float(h), "low": float(l)}
    elif policy == "selective":
        for tau in SELECTIVE_TAU:
            yield {"tau": float(tau)}
    else:
        raise ValueError(policy)


def select_thresholds(y, proba, policy, cfr, crej, cap):
    """Select on inner OOF only; return params + diagnostics + feasibility."""
    base = selection_metrics(y, *apply_policy(proba, "argmax", {}), cfr, crej)
    true_high_rate = float(np.mean(np.asarray(y) == 2))
    best = None
    best_params = None
    best_metrics = None
    n_candidates = 0
    n_feasible = 0
    for params in candidates(policy):
        n_candidates += 1
        pred, abstain = apply_policy(proba, policy, params)
        m = selection_metrics(y, pred, abstain, cfr, crej)
        violation = 0.0
        violation += max(0.0, m["test_rate"] - cap)
        violation += max(0.0, _finite(m["false_release_rate"], 1.0) - MAX_FALSE_RELEASE)
        violation += max(0.0, (_finite(base["high_grade_recall"], 0.0) -
                               _finite(m["high_grade_recall"], 0.0)) - MAX_HIGH_RECALL_DROP)
        violation += max(0.0, m["pred_high_rate"] - (true_high_rate + 0.15))
        violation += max(0.0, (_finite(base["high_precision"], 0.0) -
                               _finite(m["high_precision"], 1.0)) - MAX_HIGH_PRECISION_DROP)
        violation += max(0.0, MIN_COVERAGE - m["coverage"])
        feasible = violation <= 1e-12
        n_feasible += int(feasible)
        score = (0 if feasible else 1, float(violation), float(m["operational_cost"]),
                 float(m["test_rate"]))
        if best is None or score < best:
            best = score
            best_params = params
            best_metrics = m
    return {
        "params": best_params,
        "feasible": bool(best[0] == 0),
        "violation": float(best[1]),
        "inner_cost": float(best_metrics["operational_cost"]),
        "inner_false_release": float(_finite(best_metrics["false_release_rate"], 1.0)),
        "inner_test_rate": float(best_metrics["test_rate"]),
        "inner_high_recall": float(_finite(best_metrics["high_grade_recall"], 0.0)),
        "inner_pred_high": float(best_metrics["pred_high_rate"]),
        "base_inner_high_recall": float(_finite(base["high_grade_recall"], 0.0)),
        "base_inner_high_precision": float(_finite(base["high_precision"], 0.0)),
        "base_inner_pred_high": float(base["pred_high_rate"]),
        "n_candidates": int(n_candidates),
        "n_feasible": int(n_feasible),
    }


def build_arms():
    arms = {
        "argmax": {"policy": "argmax", "calibrated": False, "fixed": True,
                   "params": {}, "cfr": 10.0, "crej": 3.0, "cap": 0.25},
        "p17_three_way_fixed": {"policy": "three_way", "calibrated": False, "fixed": True,
                                "params": {"high": HIGH_T, "low": LOW_T},
                                "cfr": 10.0, "crej": 3.0, "cap": 0.25},
        "p17_selective_fixed": {"policy": "selective", "calibrated": False, "fixed": True,
                                "params": {"tau": SELECTIVE_T},
                                "cfr": 10.0, "crej": 3.0, "cap": 0.25},
        "nested_three_way_raw_primary": {"policy": "three_way", "calibrated": False,
                                          "fixed": False, "params": None,
                                          "cfr": 10.0, "crej": 3.0, "cap": 0.25},
        "nested_selective_raw_primary": {"policy": "selective", "calibrated": False,
                                          "fixed": False, "params": None,
                                          "cfr": 10.0, "crej": 3.0, "cap": 0.25},
        PRIMARY_THREE: {"policy": "three_way", "calibrated": True, "fixed": False,
                        "params": None, "cfr": 10.0, "crej": 3.0, "cap": 0.25},
        PRIMARY_SELECTIVE: {"policy": "selective", "calibrated": True, "fixed": False,
                            "params": None, "cfr": 10.0, "crej": 3.0, "cap": 0.25},
    }
    for policy in ("three_way", "selective"):
        for cfr, crej in COST_GRID:
            for cap in CAP_GRID:
                if (cfr, crej, cap) == PRIMARY:
                    continue
                name = f"nested_{policy}_temp_cfr{cfr:g}_crej{crej:g}_cap{int(cap * 100)}"
                arms[name] = {"policy": policy, "calibrated": True, "fixed": False,
                              "params": None, "cfr": cfr, "crej": crej, "cap": cap}
    return arms


def run_seed(data, seed, arms):
    X = data["X_full8"]
    y = data["y"]
    groups = data["groups"]
    n = len(y)
    outer_raw = np.zeros((n, 3), dtype=float)
    outer_cal = np.zeros((n, 3), dtype=float)
    outer_fold = np.full(n, -1, dtype=int)
    outer_T = np.full(n, np.nan, dtype=float)

    arm_pred = {a: np.full(n, -1, dtype=int) for a in arms}
    arm_abstain = {a: np.zeros(n, dtype=bool) for a in arms}
    threshold_rows = []
    calibration_rows = []
    infeasible = {a: 0 for a in arms}

    for fi, (tr, te) in enumerate(p9.make_splits(y, groups, seed, n_splits=5)):
        assert len(set(groups[tr]) & set(groups[te])) == 0, "outer group leakage"
        # Outer training fold -> outer test probabilities.
        outer_raw[te] = p16.ordinal_proba(X[tr], y[tr], X[te], seed, C_FIXED, W_FIXED, 3)
        assert np.allclose(outer_raw[te].sum(axis=1), 1.0, atol=1e-8), "outer proba sum"

        # Inner grouped OOF on the outer training fold only.
        ytr = y[tr]
        gtr = groups[tr]
        Xtr = X[tr]
        inner_raw = np.zeros((len(tr), 3), dtype=float)
        assigned = np.zeros(len(tr), dtype=bool)
        for itr, ite in p9.make_splits(ytr, gtr, seed + 1000 + 37 * fi, n_splits=4):
            assert len(set(gtr[itr]) & set(gtr[ite])) == 0, "inner group leakage"
            inner_raw[ite] = p16.ordinal_proba(Xtr[itr], ytr[itr], Xtr[ite],
                                               seed + 1000 + 37 * fi, C_FIXED, W_FIXED, 3)
            assigned[ite] = True
        assert assigned.all(), "inner OOF not fully assigned"
        assert np.allclose(inner_raw.sum(axis=1), 1.0, atol=1e-8), "inner proba sum"

        temperature = fit_temperature(inner_raw, ytr)
        inner_cal = temp_scale(inner_raw, temperature)
        outer_cal[te] = temp_scale(outer_raw[te], temperature)
        outer_fold[te] = fi
        outer_T[te] = temperature
        calibration_rows.append({
            "seed": int(seed), "fold": int(fi), "n_train": int(len(tr)),
            "n_high_train": int((ytr == 2).sum()),
            "temperature": float(temperature),
            "nll_raw": nll(inner_raw, ytr, 1.0),
            "nll_cal": nll(inner_raw, ytr, temperature),
            "ece_raw": ece(inner_raw, ytr),
            "ece_cal": ece(inner_cal, ytr),
        })

        for arm_name, spec in arms.items():
            policy = spec["policy"]
            if spec["fixed"]:
                params = spec["params"]
                proba = outer_raw[te]
            else:
                source = inner_cal if spec["calibrated"] else inner_raw
                sel = select_thresholds(ytr, source, policy, spec["cfr"], spec["crej"], spec["cap"])
                params = sel["params"]
                proba = outer_cal[te] if spec["calibrated"] else outer_raw[te]
                if not sel["feasible"]:
                    infeasible[arm_name] += 1
                threshold_rows.append({
                    "seed": int(seed), "fold": int(fi), "arm": arm_name,
                    "policy": policy, "calibrated": bool(spec["calibrated"]),
                    "cfr": float(spec["cfr"]), "crej": float(spec["crej"]),
                    "cap": float(spec["cap"]),
                    "high_t": float(params.get("high", np.nan)),
                    "low_t": float(params.get("low", np.nan)),
                    "tau": float(params.get("tau", np.nan)),
                    "feasible": bool(sel["feasible"]),
                    "violation": float(sel["violation"]),
                    "inner_cost": float(sel["inner_cost"]),
                    "inner_false_release": float(sel["inner_false_release"]),
                    "inner_test_rate": float(sel["inner_test_rate"]),
                    "inner_high_recall": float(sel["inner_high_recall"]),
                    "inner_pred_high": float(sel["inner_pred_high"]),
                    "base_inner_high_recall": float(sel["base_inner_high_recall"]),
                    "base_inner_high_precision": float(sel["base_inner_high_precision"]),
                    "base_inner_pred_high": float(sel["base_inner_pred_high"]),
                    "n_candidates": int(sel["n_candidates"]),
                    "n_feasible": int(sel["n_feasible"]),
                })
            pred, abstain = apply_policy(proba, policy, params)
            arm_pred[arm_name][te] = pred
            arm_abstain[arm_name][te] = abstain

    assert (outer_fold >= 0).all(), "outer OOF not fully assigned"
    for a in arms:
        assert (arm_pred[a] >= 0).all(), f"arm {a} has unassigned predictions"
        assert np.isfinite(outer_T).all(), "outer T missing"

    per_seed = []
    for arm_name, spec in arms.items():
        m = final_metrics(y, arm_pred[arm_name], arm_abstain[arm_name],
                          spec["cfr"], spec["crej"])
        m.update({
            "arm": arm_name, "policy": spec["policy"],
            "calibrated": bool(spec["calibrated"]), "fixed": bool(spec["fixed"]),
            "cfr": float(spec["cfr"]), "crej": float(spec["crej"]),
            "cap": float(spec["cap"]), "seed": int(seed),
            "n_infeasible_folds": int(infeasible[arm_name]),
        })
        per_seed.append(m)

    oof_rows = []
    for i in range(n):
        oof_rows.append({
            "seed": int(seed), "sample_id": str(data["ids"][i]),
            "fold": int(outer_fold[i]), "y": int(y[i]),
            "p0_raw": float(outer_raw[i, 0]), "p1_raw": float(outer_raw[i, 1]),
            "p2_raw": float(outer_raw[i, 2]),
            "p0_cal": float(outer_cal[i, 0]), "p1_cal": float(outer_cal[i, 1]),
            "p2_cal": float(outer_cal[i, 2]), "temperature": float(outer_T[i]),
        })
    return per_seed, threshold_rows, calibration_rows, oof_rows


def summarize(df):
    metrics = ["coverage", "test_rate", "false_release_rate", "false_reject_rate",
               "high_grade_recall", "high_grade_recall_accepted", "high_test_rate",
               "high_precision", "pred_high_rate", "operational_cost",
               "qwk", "mae_grade", "severe_overprediction_rate"]
    keys = ["arm", "policy", "calibrated", "cfr", "crej", "cap"]
    agg = {}
    for m in metrics:
        agg[m + "_mean"] = (m, "mean")
        agg[m + "_std"] = (m, "std")
    agg["n_infeasible_folds_mean"] = ("n_infeasible_folds", "mean")
    return df.groupby(keys).agg(**agg).reset_index()


def paired_deltas(df):
    rows = []
    metrics = ["operational_cost", "false_release_rate", "false_reject_rate",
               "test_rate", "coverage", "high_grade_recall",
               "high_grade_recall_accepted", "pred_high_rate", "high_precision",
               "qwk", "mae_grade"]
    direction = {"operational_cost": -1, "false_release_rate": -1,
                 "false_reject_rate": -1, "test_rate": -1, "coverage": 1,
                 "high_grade_recall": 1, "high_grade_recall_accepted": 1,
                 "pred_high_rate": 0, "high_precision": 1, "qwk": 1,
                 "mae_grade": -1}
    for arm in PRIMARY_ARMS:
        for base in ("argmax", "p17_three_way_fixed"):
            if arm not in set(df.arm) or base not in set(df.arm):
                continue
            b = df[df.arm == base].set_index("seed")
            a = df[df.arm == arm].set_index("seed")
            for metric in metrics:
                z = pd.concat([b[metric].rename("base"), a[metric].rename("arm")], axis=1).dropna()
                if len(z) < 3:
                    continue
                d = (z["arm"] - z["base"]).to_numpy()
                tt = stats.ttest_rel(z["arm"], z["base"])
                wx = stats.wilcoxon(d) if len(d) >= 6 and np.any(d != 0) else None
                better = int((d * direction[metric] > 0).sum()) if direction[metric] else 0
                rows.append({
                    "arm": arm, "base": base, "metric": metric,
                    "delta_mean": float(d.mean()), "delta_sd": float(d.std(ddof=1)),
                    "n_seed": int(len(d)), "t_p": float(tt.pvalue),
                    "wilcoxon_p": float(wx.pvalue) if wx is not None else np.nan,
                    "better_seeds": better, "direction": direction[metric],
                })
    return pd.DataFrame(rows)


def claim_check(summary, delta, per_seed):
    checks = {}
    if per_seed["seed"].nunique() < 3:
        for arm in PRIMARY_ARMS:
            checks[arm] = {"pass": False, "error": "sanity: nested claims need >=3 seeds"}
        return checks
    s = summary.set_index("arm")
    base = s.loc["argmax"]
    for arm in PRIMARY_ARMS:
        try:
            m = s.loc[arm]
            d = delta[(delta.arm == arm) & (delta.base == "argmax")]
            base_seed = per_seed[per_seed.arm == "argmax"].set_index("seed")
            arm_seed = per_seed[per_seed.arm == arm].set_index("seed")
            z = pd.concat([base_seed, arm_seed], axis=1, keys=["base", "arm"])
            c1_like = (
                (z[("arm", "false_release_rate")] <= MAX_FALSE_RELEASE) &
                (z[("arm", "test_rate")] <= MAX_TEST_PRIMARY) &
                (z[("arm", "high_grade_recall")] >= z[("base", "high_grade_recall")] - MAX_HIGH_RECALL_DROP) &
                (z[("arm", "pred_high_rate")] <= MAX_PRED_HIGH) &
                (z[("arm", "operational_cost")] <= z[("base", "operational_cost")] - 0.02)
            )
            if "high_precision" in z.columns.levels[1]:
                c1_like &= (
                    z[("arm", "high_precision")].fillna(1.0) >=
                    z[("base", "high_precision")].fillna(1.0) - MAX_HIGH_PRECISION_DROP
                )
            c1_seed_gate = int(c1_like.sum())
            fr_d = d[d.metric == "false_release_rate"]
            cost_d = d[d.metric == "operational_cost"]
            c1 = {
                "arm": arm,
                "false_release": float(m["false_release_rate_mean"]),
                "base_false_release": float(base["false_release_rate_mean"]),
                "relative_false_release_reduction": float(
                    (base["false_release_rate_mean"] - m["false_release_rate_mean"]) /
                    max(base["false_release_rate_mean"], 1e-12)),
                "test_rate": float(m["test_rate_mean"]),
                "high_grade_recall": float(m["high_grade_recall_mean"]),
                "base_high_grade_recall": float(base["high_grade_recall_mean"]),
                "pred_high_rate": float(m["pred_high_rate_mean"]),
                "high_precision": float(m["high_precision_mean"]),
                "base_high_precision": float(base["high_precision_mean"]),
                "operational_cost": float(m["operational_cost_mean"]),
                "base_operational_cost": float(base["operational_cost_mean"]),
                "cost_delta": float(m["operational_cost_mean"] - base["operational_cost_mean"]),
                "qwk": float(m["qwk_mean"]),
                "base_qwk": float(base["qwk_mean"]),
                "qwk_delta": float(m["qwk_mean"] - base["qwk_mean"]),
                "coverage": float(m["coverage_mean"]),
                "false_release_p": float(fr_d.t_p.iloc[0]) if len(fr_d) else np.nan,
                "cost_p": float(cost_d.t_p.iloc[0]) if len(cost_d) else np.nan,
                "better_seeds_false_release": int(fr_d.better_seeds.iloc[0]) if len(fr_d) else 0,
                "better_seeds_cost": int(cost_d.better_seeds.iloc[0]) if len(cost_d) else 0,
                "seed_gate_count": c1_seed_gate,
            }
            c1["pass"] = bool(
                c1["false_release"] <= MAX_FALSE_RELEASE and
                c1["test_rate"] <= MAX_TEST_PRIMARY and
                c1["high_grade_recall"] >= c1["base_high_grade_recall"] - MAX_HIGH_RECALL_DROP and
                c1["pred_high_rate"] <= MAX_PRED_HIGH and
                c1["cost_delta"] <= -0.02 and
                c1["high_precision"] >= c1["base_high_precision"] - MAX_HIGH_PRECISION_DROP and
                c1["false_release_p"] < 0.05 and c1["cost_p"] < 0.05 and
                c1["better_seeds_false_release"] >= 7 and c1["better_seeds_cost"] >= 7 and
                c1_seed_gate >= 8
            )
            checks[arm] = {"C1": c1}
            if arm == PRIMARY_SELECTIVE:
                c2_like = (
                    (z[("arm", "coverage")] >= MIN_COVERAGE) &
                    ((z[("base", "false_release_rate")] - z[("arm", "false_release_rate")]) /
                     z[("base", "false_release_rate")].clip(lower=1e-12) >= 0.30) &
                    (z[("arm", "high_grade_recall")] >= z[("base", "high_grade_recall")] - MAX_HIGH_RECALL_DROP) &
                    (z[("arm", "qwk")] >= z[("base", "qwk")] - 0.05) &
                    (z[("arm", "pred_high_rate")] <= MAX_PRED_HIGH)
                )
                c2_seed_gate = int(c2_like.sum())
                c2 = {
                    "arm": arm,
                    "coverage": float(m["coverage_mean"]),
                    "false_release": float(m["false_release_rate_mean"]),
                    "relative_false_release_reduction": float(
                        (base["false_release_rate_mean"] - m["false_release_rate_mean"]) /
                        max(base["false_release_rate_mean"], 1e-12)),
                    "high_grade_recall": float(m["high_grade_recall_mean"]),
                    "base_high_grade_recall": float(base["high_grade_recall_mean"]),
                    "qwk": float(m["qwk_mean"]),
                    "base_qwk": float(base["qwk_mean"]),
                    "qwk_delta": float(m["qwk_mean"] - base["qwk_mean"]),
                    "pred_high_rate": float(m["pred_high_rate_mean"]),
                    "false_release_p": float(fr_d.t_p.iloc[0]) if len(fr_d) else np.nan,
                    "better_seeds_false_release": int(fr_d.better_seeds.iloc[0]) if len(fr_d) else 0,
                    "seed_gate_count": c2_seed_gate,
                }
                c2["pass"] = bool(
                    c2["coverage"] >= MIN_COVERAGE and
                    c2["relative_false_release_reduction"] >= 0.30 and
                    c2["high_grade_recall"] >= c2["base_high_grade_recall"] - MAX_HIGH_RECALL_DROP and
                    c2["qwk_delta"] >= -0.05 and
                    c2["pred_high_rate"] <= MAX_PRED_HIGH and
                    c2["false_release_p"] < 0.05 and
                    c2["better_seeds_false_release"] >= 7 and
                    c2_seed_gate >= 8
                )
                checks[arm]["C2"] = c2
        except Exception as e:
            checks[arm] = {"pass": False, "error": str(e)}
    return checks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="sanity", choices=["sanity", "full"])
    ap.add_argument("--seeds", nargs="*", type=int, default=SEEDS)
    ap.add_argument("--tag", default="sanity")
    args = ap.parse_args()
    if args.mode == "sanity" and args.seeds == SEEDS:
        args.seeds = [SEEDS[0]]
    t0 = time.time()

    data = p17_load_data()
    y = data["y"]
    assert len(y) == 301 and np.bincount(y).tolist() == [33, 197, 71], (len(y), np.bincount(y).tolist())
    print(f"data n={len(y)} groups={len(set(data['groups']))} X={data['X_full8'].shape} "
          f"counts={np.bincount(y).tolist()}", flush=True)

    arms = build_arms()
    print(f"arms={len(arms)} primary={PRIMARY_THREE},{PRIMARY_SELECTIVE}", flush=True)
    per_seed, thresholds, calibration, oof = [], [], [], []
    for seed in args.seeds:
        print(f"SEED {seed}", flush=True)
        ps, th, cal, oo = run_seed(data, seed, arms)
        per_seed.extend(ps)
        thresholds.extend(th)
        calibration.extend(cal)
        oof.extend(oo)
        print(f"  seed {seed} done", flush=True)

    ps = pd.DataFrame(per_seed)
    th = pd.DataFrame(thresholds)
    cal = pd.DataFrame(calibration)
    oo = pd.DataFrame(oof)
    ps.to_csv(EXP / f"results/p18_policy_per_seed_{args.tag}.csv", index=False,
              encoding="utf-8-sig", float_format="%.10g")
    th.to_csv(EXP / f"results/p18_thresholds_{args.tag}.csv", index=False,
              encoding="utf-8-sig", float_format="%.10g")
    cal.to_csv(EXP / f"results/p18_calibration_{args.tag}.csv", index=False,
              encoding="utf-8-sig", float_format="%.10g")
    oo.to_csv(EXP / f"results/p18_oof_proba_{args.tag}.csv", index=False,
              encoding="utf-8-sig", float_format="%.10g")

    summary = summarize(ps)
    summary.to_csv(EXP / f"results/p18_policy_summary_{args.tag}.csv", index=False,
                   encoding="utf-8-sig", float_format="%.10g")
    delta = paired_deltas(ps)
    delta.to_csv(EXP / f"results/p18_policy_delta_{args.tag}.csv", index=False,
                 encoding="utf-8-sig", float_format="%.10g")
    sens = summary[summary.arm.str.startswith("nested_") & summary.calibrated].copy()
    sens.to_csv(EXP / f"results/p18_cost_sensitivity_{args.tag}.csv", index=False,
                encoding="utf-8-sig", float_format="%.10g")

    checks = claim_check(summary, delta, ps)
    (EXP / f"results/p18_claim_check_{args.tag}.json").write_text(
        json.dumps(checks, ensure_ascii=False, indent=2), encoding="utf-8")

    config = {
        "date": "2026-11-26",
        "experiment": "P18 nested calibrated decision policy",
        "data": "301 epoxy-phenolic T, cuts [15,20], formula_id groups",
        "outer_cv": "StratifiedGroupKFold(5)",
        "inner_cv": "StratifiedGroupKFold(4)",
        "seeds": args.seeds,
        "model": {"features": "P16 full8 (183+8)", "C": C_FIXED, "w": W_FIXED,
                  "note": "feature/model family frozen; no new features"},
        "calibration": "temperature scaling on inner OOF; bounded [0.5,3.0]",
        "threshold_grid": {"three_way_high": THREE_H.tolist(),
                           "three_way_low": THREE_L.tolist(),
                           "selective_tau": SELECTIVE_TAU.tolist()},
        "operational_cost": {"false_release": "sensitivity 5/10/20",
                             "false_reject": "sensitivity 2/3/5",
                             "test": 1.0},
        "primary": {"cfr": 10.0, "crej": 3.0, "cap": 0.25,
                    "arms": PRIMARY_ARMS},
        "feasibility": {"false_release_max": MAX_FALSE_RELEASE,
                        "test_capacity_primary": MAX_TEST_PRIMARY,
                        "high_recall_drop_max": MAX_HIGH_RECALL_DROP,
                        "high_precision_drop_max": MAX_HIGH_PRECISION_DROP,
                        "pred_high_max": MAX_PRED_HIGH,
                        "coverage_min": MIN_COVERAGE},
        "external_reviewer": "unavailable; local deterministic only",
        "note": "outer test never selects T or thresholds",
    }
    (EXP / f"results/p18_config_{args.tag}.json").write_text(
        json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\nPRIMARY SUMMARY\n", summary[summary.arm.isin(PRIMARY_ARMS + ["argmax", "p17_three_way_fixed", "p17_selective_fixed"])].round(4).to_string(index=False))
    print("\nCLAIM CHECK\n", json.dumps(checks, ensure_ascii=False, indent=2))
    print("elapsed", round(time.time() - t0, 1), "s")


if __name__ == "__main__":
    main()
