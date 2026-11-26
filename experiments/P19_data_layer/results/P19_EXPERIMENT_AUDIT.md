# P19 Experiment Audit Report

**Date**: 2026-11-26
**Experiment**: `P19_data_layer` — data audit + training-only augmentation
**Auditor**: local deterministic audit; external cross-model reviewer **unavailable**
**Status**: `WARN` / `PROVISIONAL_LOCAL_AUDIT` — this is not a cross-model acquittal.

## Overall Verdict: WARN

## Integrity Status: warn

## Checks

### A. Ground Truth Provenance: PASS

- `scripts/p19_data_layer.py` loads the 301 observed T labels through `p17_load_data()`; `y` is produced by `p09.grade_from_cuts` from the workbook’s measured T values.
- `raw_t` is read from `建模输入`/`性能结果` and asserted to align with the 301 sample IDs.
- `make_train_arm()` is called only with the outer training indices. The outer test fold is never passed to the augmentation function.
- `n_synthetic_test` is asserted to be **0** in every fold and recorded in `results/p19_augmentation_audit_full.csv`; the aggregate is 0.
- No pseudo-label, literature T value, or manual T value is used as a target.
- Evaluation type: `real_gt`.

### B. Score Normalization: PASS

- Primary metric is raw quadratic weighted kappa computed by `sklearn.metrics.cohen_kappa_score` against observed labels.
- False-release, high-recall, test-rate, and MAE are raw operational metrics; no prediction-max normalization.
- No metric denominator is derived from model output statistics.

### C. Result File Existence: PASS

Cited result files exist and contain the reported numbers:

- `results/p19_summary_full.csv`
- `results/p19_delta_full.csv`
- `results/p19_per_seed_full.csv`
- `results/p19_oof_proba_full.csv`
- `results/p19_augmentation_audit_full.csv`
- `results/p19_data_audit_full.json`
- `results/p19_claim_check_full.json`
- `results/p19_label_noise_simulation_full.csv`

### D. Dead Code Detection: PASS

- All metric functions used by the report are called in `metrics_for()` / `paired_summary()` / `build_claim_check()`.
- The `sanity` argument in `run_seed()` is not used; it has no metric or claim effect. This is a harmless cleanup item, not a dead metric path.
- All eight model arms are exercised; `cure_meta` is explicitly labelled exploratory.

### E. Scope Assessment: WARN

- 301 observed T samples, one endpoint, 10 seeds, 5 outer folds.
- No external validation; no repeated T measurements; no substrate record.
- The report does not use “comprehensive” or “robust” as a claim. The scope is explicitly limited to the current epoxy-phenolic T table.
- The cure-condition arm is confounded with series and cannot support a causal claim.

### F. Evaluation Type: real_gt

- Real observed T labels are the only evaluation reference.
- Synthetic rows are training-only regularizers and are excluded from every test fold.

## Claim Impact

- **C1 — training-only augmentation**: unsupported. Best mean ΔQWK is `+0.00703` (`jitter25`), below the pre-registered `+0.020`; only 6/10 seeds positive; FR `+2.39 pp` and high recall `−2.25 pp`.
- **C2 — boundary-aware weighting**: unsupported. Best `boundary_w50` ΔQWK `+0.00978`, below `+0.020`; 8/10 seeds positive, FR `+0.42 pp`, high recall unchanged; paired p `0.063`. This is directional only, not a claim.
- **C3 — data audit**: supported as descriptive evidence.
- **C4 — no external rows merged**: supported by construction and file checks.

## Action Items

1. Do not deploy synthetic augmentation or boundary weighting as a data-layer fix.
2. Keep `boundary_w50` only as a pre-registered follow-up hypothesis, not as a result.
3. Prioritize repeated T measurements (20–30 stratified samples) over more synthetic rows.
4. Record that ASTM D4145 precision is a reference band, not measured noise for this substrate.

## Claim Impact Summary

- Claim 1: `unsupported`
- Claim 2: `unsupported`
- Claim 3: `supported` (descriptive)
- Claim 4: `supported` (negative constraint)
