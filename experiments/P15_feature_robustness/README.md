# P15 — FTIR Feature Robustness

**Status**：P15-B full completed (10 seeds); P15-A residual pilot is 1-seed exploratory only.

## Objective

Test whether P14's 190-dim FTIR gain survives when the FTIR subset is selected
**inside** the outer training folds, not fixed post hoc. Secondary exploratory
arm: replace raw FTIR by its training-fold linear residual from base183.

## Protocol

- Data: 301 epoxy-phenolic T samples, `T弯` → 3 grades via cuts `[15, 20]`.
- Base: P10 v2-fix 183 features.
- FTIR: P13 `feature_matrix_p13_t_ftir8.csv` (191 = 183 + 8).
- P15-B candidates (all previously reported P14 subsets, no new search):
  `base183`, `full8`, `drop_oh_epox`, `drop_oh_epox_aroc`, `core4`, `core5`.
- Outer: `StratifiedGroupKFold(5)` by `formula_id`; inner: 3-fold grouped.
- Inner selection: subset × C (`0.5, 1, 1.5, 2`) by inner QWK.
- Model: ordinal cumulative logistic, balanced, L2, max_iter 3000.
- Seeds: 42, 202, 777, 1234, 2026, 31415, 2718, 1618, 5678, 9999.

## Key result

- P15-B nested subset+C: QWK `0.571704 ± 0.023059` (95% CI `[0.555208, 0.588199]`).
- P14 190 fixed C=2: `0.579690 ± 0.022514`; P15-B delta `−0.007986`, paired p `0.090259`, 3/10 seeds positive.
- Selection frequency: `full8` 36%, `core4` 20%, `drop_oh_epox_aroc` 20%, `drop_oh_epox` 14%, `base183` 8%, `core5` 2%.
- P14's 190 subset was selected in only 14% of outer folds; no candidate reached a 50% majority.

**Decision**: QWK threshold passed, stability criterion failed. FTIR block is useful, but the fixed 190-dim subset is not a stable optimum. P14's 190 result remains conditional on the post-hoc fixed set.

## P15-A exploratory pilot (not confirmatory)

1 seed: base `0.5400`, raw FTIR7 `0.5810`, residual FTIR7 `0.5401`; Ridge base→FTIR R² `0.967`, residual std ratio `0.161`. Simple linear residualization removes too much signal; do not use as a claim that "FTIR has no information".

## Reproduce

```bash
cd /home/user/3new-refactor
# sanity (1 seed; not part of the 10-seed estimate)
bash experiments/P15_feature_robustness/scripts/run_p15.sh sanity
# full 10 seeds
bash experiments/P15_feature_robustness/scripts/run_p15.sh full
```

Inputs are the local P10/P13 matrices. The remote branch is a code/report archive;
full matrices are local-only — see `../P14_evidence_chain/REMOTE_DATA.md`.

## Outputs

- `results/p15b_full_per_seed.csv`
- `results/p15b_full_summary.csv`
- `results/p15b_full_chosen.csv`
- `results/p15b_full_candidate_frequency.csv`
- `results/p15b_full_vs_p14.csv`
- `results/p15b_full_delta.csv`
- `results/p15b_full_config.json`
- `results/P15_实验报告.md`
- `logs/p15b_full.log`
