# P16 Experiment Tracker

**Plan**：`refine-logs/P16_EXPERIMENT_PLAN.md`

**Status**：full 10-seed completed; C1 PASS, C2 FAIL.

**Date**：2026-11-25

| Run ID | Milestone | Purpose | System / Variant | Split | Metrics | Priority | Status | Notes |
|---|---|---|---|---|---|---|---|---|
| R001 | M0 | sanity | base183 / full8 / placebo8 / ftir8_w / core4_w | 1 seed, 5 outer | QWK, shapes, NaN, weight mask | MUST | DONE | base 0.5400; full8 0.5665; placebo 0.5391; ftir8_w 0.5683; core4_w 0.5745 |
| R002 | M1 | baseline | base183 / full8 / placebo8 | 10 seeds, 5 outer | QWK, MAE, high, over, cost | MUST | DONE | base 0.5451; full8 0.5668; placebo 0.5311 |
| R003 | M2 | main | ftir8_w | 10 seeds, 5 outer, 6 w × 4 C | QWK + guardrails; chosen w/C | MUST | DONE | 0.5576 ±0.0163; C2 FAIL; mean w 2.31; w=4 22% folds |
| R004 | M3 | parsimony | core4_w | 10 seeds, 5 outer, 6 w × 4 C | QWK + non-inferiority | MUST | DONE | 0.5715 ±0.0135; exploratory; w=4 34% folds |
| R005 | M4 | analysis | paired tests, Holm, 95% CI, selection frequency | — | C1/C2 verdict | MUST | DONE | C1 PASS (Holm 0.0072); C2 FAIL (p 0.1035) |
| R006 | B4 | diagnostic | w/C frequency and w-curve | 10 seeds | stability | NICE | DONE | `p16_full_weight_frequency.csv`; shares per set |
| R007 | B5 | reference | P14 190 fixed/nested table | — | reference only | APPENDIX | DONE | `p16_full_p14_reference.csv`; no retrain |

## Pre-registered gates

- **C1**：`full8 − placebo8` QWK ≥ +0.010；Holm 后 p<0.05；≥7/10 seeds 正；high drop ≤0.02、cost rise ≤0.02。
- **C2**：`ftir8_w − full8` QWK ≥ +0.005；Holm 后 p<0.05；≥7/10 seeds 正；`core4_w − ftir8_w` ≥ −0.005（非劣性）。
- **Stop rules**：C1 失败 → 停止把 FTIR 当化学信息；C2 不得救场。C2 失败但 C1 成立 → 保留 full8 固定块，不再做权重搜索。`w` 贴边 0.5 或 4.0 → 报“未定”，不 post-hoc 扩网格。`core4` 明显低于 ftir8_w → 不推简约子集。

## Notes

- No new data; use P10 `feature_matrix_v2_fix_reduced.csv` + P13 `feature_matrix_p13_t_ftir8.csv`.
- Target: 301 T samples; 5 outer grouped folds by `formula_id`; 3 inner.
- Model: ordinal logistic; P14 model family already showed logistic > XGB; no new model sweep.
- Placebo: seed-fixed global row shuffle of FTIR8; same dimensions and covariance; target never used to choose permutation.
- Compute: ~18k logistic fits; 35–55 min on 2 vCPU.
