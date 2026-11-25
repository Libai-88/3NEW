# P16 — FTIR Block Weighting and Placebo Control

**Status**: full 10-seed run completed; P16 verdict C1 PASS, C2 FAIL.

## Questions

1. Is the FTIR8 gain real sample-specific information, or only extra
   parameters/L2 regularization?
2. Can one continuous block weight `w` replace P15's unstable hard subset
   selection?

## Protocol

- Data: 301 epoxy-phenolic T samples; 3-grade `T弯` with cuts `[15,20]`.
- Base: P10 v2-fix 183 features.
- FTIR: P13 FTIR8 (8 raw indices); core4 is the prior P14 subset.
- Outer: `StratifiedGroupKFold(5)` by `formula_id`; inner: 3-fold grouped.
- C: `0.5, 1.0, 1.5, 2.0`; weight: `0.5, 1.0, 1.5, 2.0, 3.0, 4.0`.
- Model: ordinal cumulative logistic, balanced, L2, max_iter 3000.
- Seeds: 42, 202, 777, 1234, 2026, 31415, 2718, 1618, 5678, 9999.

## Systems

| System | Features | Weight |
|---|---|---|
| `base183` | 183 base | none |
| `full8` | 183 + 8 FTIR | w=1 |
| `placebo8` | 183 + 8 row-shuffled FTIR | w=1 |
| `ftir8_w` | 183 + 8 FTIR | w selected inner |
| `core4_w` | 183 + 4 prior core4 FTIR | w selected inner |

The placebo is a seed-fixed global row permutation of FTIR8: same dimensions,
marginals and covariance, but no sample-target alignment. Base is unchanged.
`y` is never used to construct the placebo.

Weight is applied **after** StandardScaler: impute → scale → multiply the trailing
FTIR block (values + missing indicators) by `w`. Applying it before scaling would
cancel it.

## Pre-registered gates

- **C1**: `full8 − placebo8` QWK ≥ +0.010; Holm-adjusted p<0.05; ≥7/10 seeds
  positive; high recall drop ≤0.02; cost rise ≤0.02.
- **C2**: `ftir8_w − full8` QWK ≥ +0.005; Holm-adjusted p<0.05; ≥7/10 seeds
  positive; `core4_w − ftir8_w` ≥ −0.005 (non-inferiority).

## Reproduce

```bash
cd /home/user/3new-refactor
# sanity (1 seed)
bash experiments/P16_ftir_block_weight/scripts/run_p16.sh sanity
# full 10 seeds
bash experiments/P16_ftir_block_weight/scripts/run_p16.sh full
```

Inputs: local P10/P13 matrices. No new data; no GPU.

## Result snapshot

- `full8` 0.566778 ± 0.026883; `placebo8` 0.531069 ± 0.023207; C1 delta +0.035665, Holm p 0.0072, 9/10 seeds positive: **C1 PASS**.
- `ftir8_w` 0.557627 ± 0.016347; C2 delta −0.009151, p 0.1035, 4/10 seeds positive: **C2 FAIL**.
- `core4_w` 0.571499 ± 0.013461; exploratory only (prior P14 subset, w=4 boundary 34%).

## Outputs

- `results/p16_full_per_seed.csv`
- `results/p16_full_summary.csv`
- `results/p16_full_chosen.csv`
- `results/p16_full_weight_frequency.csv`
- `results/p16_full_delta.csv`
- `results/p16_full_config.json`
- `results/p16_full_p14_reference.csv`
- `logs/p16_sanity.log`, `logs/p16_full.log`
