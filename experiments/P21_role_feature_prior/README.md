# P21 — Role-Criticality Prior and Importance-Aware Feature Construction

This directory is the archived, reproducible P21 experiment.

## Question

Does a role-criticality prior (resin / curing agent / catalyst high, support and
molecular descriptors lower) beat a mass-dose prior on the 301 observed T-bend
samples? Separately, do log / two-part / interaction constructions for the
small-dose catalyst features help, and do FTIR band weights by diagnostic role
beat an intensity control?

## Design

- Target: 301 observed T-bend labels, three grades `[33, 197, 71]`, cuts `[15, 20]`.
- Features: `full8` 191 columns = 183 base + 8 FTIR band fractions.
- Split: 5-fold `StratifiedGroupKFold` by `formula_id`, 20 seeds.
- Model: ordinal cumulative logistic, L2, balanced, `C=2.0`, max_iter=3000.
- Primary gates: C1 role vs mass (with shuffle and non-inferiority controls);
  C2 catalyst two-part; C3 interaction; C4 FTIR band role.
- 15 arms = 13 pre-registered + 2 exploratory direct-weight controls added
  after the sanity diagnostic (`role_prior_direct`, `mass_prior_direct`).
- No auxiliary labels, no synthetic T labels, no external data; transforms and
  weights never use `y`.

The pre-registration is in `../../refine-logs/P21_EXPERIMENT_PLAN.md` and
`../../refine-logs/P21_WEIGHT_RUBRIC.md`. The sanity-informed addendum is
recorded in both files before the full run.

## Results (20 seeds)

| Arm | QWK mean ± SD |
|---|---:|
| `ftir_band_intensity` | 0.575044 ± 0.028155 |
| `ftir_band_role` | 0.573563 ± 0.026146 |
| `full8_base` | 0.570181 ± 0.024523 |
| `full8_gn_base` | 0.507677 ± 0.021571 |
| `role_prior` | 0.510304 ± 0.021839 |
| `mass_prior` | 0.487546 ± 0.018125 |
| `role_prior_direct` | 0.571143 ± 0.024126 |
| `mass_prior_direct` | 0.569901 ± 0.021610 |
| `two_part_cat` | 0.570271 ± 0.025284 |
| `interact` | 0.571032 ± 0.027612 |

**Overall verdict: negative. C1/C2/C3/C4 all fail.**

- C1 sub-checks `role_prior − mass_prior` (+0.022758, 19/20) and
  `role_prior − role_prior_shuffle` (+0.009394, 17/20) pass, but
  `role_prior − full8_gn_base` is only +0.002627 (11/20, p=0.291) and
  `role_prior − full8_base` is −0.059878.
- The direct control `role_prior_direct − mass_prior_direct` is +0.001243
  (10/20, p=0.812): without group-size normalisation the role weights have no
  advantage over mass weights. The apparent C1 sub-win is a groupnorm /
  small-group amplification effect.
- C2 `two_part_cat` vs base +0.000090; vs `log_cat` −0.000486.
- C3 `interact` vs shuffle +0.004055 (p=0.368); vs base +0.000851.
- C4 `ftir_band_role` vs intensity −0.001481; vs shuffle +0.004852
  (raw p=0.0456, Holm p=0.0912, below the +0.005 gate). The intensity control
  is the highest FTIR arm.
- P21 does not disprove the chemistry of catalyst criticality; it disproves the
  current hand-weighted representation as a deployable T-bend gain.

## Baseline provenance

`full8_base` on the 10 P20 seeds is identical to
`P20_aux_target_transfer/results/p20_per_seed_full.csv` (max abs diff 0.0;
mean 0.573974). The 20-seed P21 mean is 0.570181 because it adds ten new seeds.

## Reproduce

From the repository root:

```bash
python3 experiments/P21_role_feature_prior/scripts/p21_role_feature_prior.py --mode map
python3 experiments/P21_role_feature_prior/scripts/p21_role_feature_prior.py --mode sanity --tag sanity
python3 experiments/P21_role_feature_prior/scripts/p21_role_feature_prior.py --mode full --tag full
python3 experiments/P21_role_feature_prior/scripts/p21_audit.py
```

Expected full runtime on the current 2-vCPU CPU-only box: about 5 minutes.
The full run writes 15 arms ×20 seeds ×5 folds and 90,300 OOF rows.

## Audit

`results/P21_EXPERIMENT_AUDIT.json` and `.md`: 27/27 local deterministic checks
pass. This is `PROVISIONAL_LOCAL_AUDIT`; external cross-model review is
`REVIEW_UNAVAILABLE`, so the claim file keeps
`verdict: REVIEW_UNAVAILABLE` and does not self-acquit.

## Files

- `data/P21_ROLE_MAP.csv` — 191-feature role map.
- `data/P21_GROUP_WEIGHTS.json` — role prior, mass prior, mass shares, FTIR weights.
- `scripts/p21_role_feature_prior.py` — experiment runner.
- `scripts/p21_audit.py` — local audit.
- `results/P21_实验报告.md` — Chinese report.
- `results/P21_CLAIMS_FROM_RESULTS.md` — claim ledger.
- `results/P21_EXPERIMENT_AUDIT.md` / `.json` — audit.
- `results/p21_full_summary.csv` — arm summary.
- `results/p21_full_per_seed.csv` — per-seed metrics.
- `results/p21_full_delta.csv` — paired comparisons.
- `results/p21_full_specificity.csv` — pre-registered comparisons.
- `results/p21_full_claim_check.json` — machine-readable gate output.
- `results/p21_full_audit.csv` — 1,500 fold-level audit rows.
- `logs/` — map/sanity/full/audit logs.
