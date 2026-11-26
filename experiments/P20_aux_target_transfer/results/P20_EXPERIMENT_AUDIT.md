# P20 Experiment Audit Report

**Date**: 2026-11-26
**Experiment**: `P20_aux_target_transfer` — MEK / water auxiliary representation for T-bend
**Auditor**: local deterministic audit; external cross-model reviewer **unavailable**
**Status**: `WARN` / `PROVISIONAL_LOCAL_AUDIT` — this is not a cross-model acquittal.

## Overall Verdict: WARN

## Integrity Status: warn

## Checks

### A. Ground Truth Provenance: PASS

- T labels come from the observed 301-row epoxy-phenolic table through `p19.load_all()`; no synthetic T, pseudo-label, literature T, or manual T is used as a target.
- MEK / water auxiliary labels come from `建模输入` columns `MEK实测` / `水煮实测` by sample ID, not from model outputs. Missing auxiliary labels stay missing (`-1`) and are filled with outer-training-fold priors only for training rows.
- `make_aux_features()` receives `tr`, `te`, `Xtr`, `Xte`; it builds `y_mek_tr = data["mek_y"][tr]` and `y_water_tr = data["water_y"][tr]`, and never reads `data["mek_y"][te]` or `data["water_y"][te]`. The outer test auxiliary probabilities are predicted from `Xte` only.
- Outer group leakage is asserted: `len(set(groups[tr]) & set(groups[te])) == 0` for every fold.
- Evaluation type: `real_gt`.

**Note**: `n_aux_test_labels_used` is set to 0 by construction, not computed by a dynamic taint/tripwire. The evidence is code inspection plus the absence of `te` label reads, not a formal proof. This is why the audit is `WARN`, not `PASS` on C4 strength.

### B. Score Normalization: PASS

- Primary metric is raw quadratic weighted kappa against observed T labels; no prediction-max normalization.
- False-release, high-recall, test-rate, MAE, high-precision, and pred-high are raw operational metrics.
- Auxiliary probabilities are normalized to sum to 1, but that is a model output constraint, not a metric denominator.

### C. Result File Existence: PASS

All cited files exist and match the report:

- `results/p20_summary_full.csv`
- `results/p20_delta_full.csv`
- `results/p20_specificity_full.csv`
- `results/p20_per_seed_full.csv`
- `results/p20_oof_proba_full.csv`
- `results/p20_aux_audit_full.csv`
- `results/p20_claim_check_full.json`
- `results/p20_config_full.json`

The base QWK `0.573974` matches P19 `full8_base` (`0.573974`) to about `4.8e-7`; the sanity base `0.576128` differs by `0.002154`, within the pre-registered `≤0.005` alignment band.

### D. Dead Code Detection: PASS

- `load_all()`, `grade_aux()`, `aux_prior()`, `aux_oof_proba()`, `aux_test_proba()`, `AuxPrep`, `make_aux_model()`, `ordinal_proba_aux()`, `make_aux_features()`, `run_seed()`, `paired_vs_base()`, `paired_specificity()`, `gate_base()`, `gate_specificity()`, `build_claim_check()` are all called.
- All six arms are exercised; all 10 seeds and 5 outer folds are present in `p20_aux_audit_full.csv` (300 records).
- No unused metric or phantom claim path found.

### E. Scope Assessment: WARN

- 301 observed T samples, one endpoint, one model family (cumulative logistic on frozen `full8`), 10 seeds, 5 outer folds.
- No external validation; no new series; no repeated T measurements.
- Water auxiliary coverage is 239/301; MEK 298/301. Missing auxiliary labels are prior-filled in training only.
- The report does not use “comprehensive” or “robust” as a claim; it explicitly limits the conclusion to the current 301-row epoxy-phenolic T table.
- P20 is a stacked-probability representation, not an end-to-end multi-task shared encoder; the report states this limitation.

### F. Evaluation Type: real_gt

- Real observed T labels are the only evaluation reference.
- Auxiliary labels are real observed MEK / water labels used only in the training fold; test auxiliary labels are not read.

## Claim Impact

- **C1 — MEK auxiliary representation**: unsupported. `aux_mek4` mean ΔQWK `−0.003824`, 3/10 seed wins, FR `+1.27 pp`, high recall `−1.55 pp`; fails the `+0.020` gate.
- **C2 — joint MEK+water auxiliary representation**: unsupported. `aux_both` mean ΔQWK `−0.014573`, 3/10 seed wins, FR `+2.54 pp`, high recall `−3.38 pp`; base gate fails. `aux_both` vs `aux_both_shuffle` specificity `+0.009348`, 6/10, p `0.156`; below `+0.010` / 7 seeds, and cannot rescue the base failure.
- **C3 — auxiliary coverage and arm-level audit**: supported as descriptive evidence; MEK 298/301 (`89/97/61/51`), water 239/301 (`86/55/98`), all arm metrics present.
- **C4 — no test auxiliary labels used**: supported by code inspection and 300 fold-level audit records with `n_aux_test_labels_used=0`; audit field is declared, so C4 strength is WARN rather than formal PASS.

## Action Items

1. Do not deploy any P20 auxiliary arm; all three real auxiliary arms are below base.
2. Keep P20 as a negative result: “stacked auxiliary probabilities from the same `full8` do not improve T-bend OOF QWK under the pre-registered protocol.”
3. Do not run more hyperparameter/auxiliary-target searches on the same 301 T rows; the information ceiling is unchanged without new T measurements or a different multi-task architecture.
4. If a future multi-task experiment is proposed, test it on new T data or a held-out series; do not reuse this negative result as evidence that “MEK/water are useless” in general.

## Claim Impact Summary

- Claim 1: `unsupported`
- Claim 2: `unsupported`
- Claim 3: `supported` (descriptive)
- Claim 4: `supported` (code-inspection / negative constraint; audit strength WARN)
