verdict: REVIEW_UNAVAILABLE
claim_supported: false
date: 2026-11-28
experiment: P21 role-criticality prior and importance-aware feature construction
n_seeds: 20
n_arms: 15
split: 5-fold StratifiedGroupKFold by formula_id
c_fixed: 2.0
target: 301 observed T-bend labels, cuts [15, 20]
baseline_full8_qwk: 0.570181 ± 0.024523 (20 seeds; shared 10 P20 seeds reproduce 0.573974 exactly)
audit: PROVISIONAL_LOCAL_AUDIT, 27/27 local checks pass, external reviewer unavailable

# P21 Claims From Results

## Overall

P21 does **not** support a deployable role-criticality feature prior, a
catalyst log/two-part construction, a catalyst interaction construction, or
a diagnostic FTIR-band weighting scheme on the current 301 T-bend data.

The primary C1 gate fails. Two of its sub-comparisons do pass
(`role_prior` beats `mass_prior` and `role_prior_shuffle`), but the role arm is
far below `full8_base` and is not better than the group-normalised uniform
baseline. The direct-weight exploratory control shows that, once
group-size normalisation is removed, the role prior has no advantage over the
mass prior. The apparent C1 sub-win is therefore a group-normalisation /
small-group amplification effect, not evidence that role semantics improve
prediction.

## C1 — role-criticality prior vs mass-dose prior: FAIL

| Sub-check | Result | Evidence |
|---|---|---|
| `role_prior − mass_prior` | PASS | +0.022758, 19/20 seeds positive, paired p=4.91e-5, Holm p=1.47e-4; FR +0.21 pp, high recall +2.96 pp |
| `role_prior − role_prior_shuffle` | PASS | +0.009394, 17/20, paired p=0.01646, Holm p=0.03292 |
| `role_prior − full8_gn_base` | FAIL | +0.002627, 11/20, p=0.29058; below the +0.005 gate |
| `role_prior − full8_base` non-inferiority | FAIL | −0.059878, 0/20 positive, p=2.77e-10 |
| Direct control: `role_prior_direct − mass_prior_direct` | FAIL | +0.001243, 10/20, p=0.81164; no role-specific advantage |

Mean QWK:
- `full8_base` 0.570181 ± 0.024523
- `full8_gn_base` 0.507677 ± 0.021571
- `mass_prior` 0.487546 ± 0.018125
- `role_prior` 0.510304 ± 0.021839
- `role_prior_shuffle` 0.500909 ± 0.025149
- `mass_prior_direct` 0.569901 ± 0.021610
- `role_prior_direct` 0.571143 ± 0.024126

Interpretation: `role_prior` wins the two pre-registered within-groupnorm
comparisons, but the group-normalised baseline is itself 0.0625 QWK below
`full8_base`. `role_prior` is only 0.0026 above `full8_gn_base`, and the
direct-weight control is statistically indistinguishable from the mass prior.
C1 is not supported as a deployable prior.

## C2 — importance-aware catalyst construction: FAIL

| Comparison | Delta QWK | Seeds positive | p | FR / high-recall guardrail |
|---|---:|---:|---:|---|
| `two_part_cat − full8_base` | +0.000090 | 8/20 | 0.96540 | FR +0.49 pp; HR +0.07 pp |
| `two_part_cat − log_cat` | −0.000486 | 9/20 | 0.81340 | FR +0.49 pp; HR 0.00 pp |

`two_part_cat` 0.570271 ± 0.025284; `log_cat` 0.570757 ± 0.025091;
`log_cat_ratio` 0.571713 ± 0.024681 (exploratory). The two-part construction
does not beat either the original features or plain log. C2 fails.

## C3 — catalyst interaction construction: FAIL

| Comparison | Delta QWK | Seeds positive | p |
|---|---:|---:|---:|
| `interact − interact_shuffle` | +0.004055 | 11/20 | 0.36765 |
| `interact − full8_base` | +0.000851 | 11/20 | 0.71265 |

`interact` 0.571032 ± 0.027612; `interact_shuffle` 0.566978 ± 0.020927.
The interaction arm does not clear the +0.005 threshold or its shuffled
control. C3 fails.

## C4 — FTIR band diagnostic weighting: FAIL

| Comparison | Delta QWK | Seeds positive | p | Holm p |
|---|---:|---:|---:|---:|
| `ftir_band_role − ftir_band_intensity` | −0.001481 | 9/20 | 0.63150 | 0.63150 |
| `ftir_band_role − ftir_band_shuffle` | +0.004852 | 14/20 | 0.04561 | 0.09121 |

`ftir_band_role` 0.573563 ± 0.026146; `ftir_band_intensity`
0.575044 ± 0.028155; `ftir_band_shuffle` 0.568712 ± 0.025413.
The diagnostic-role weights are not better than training-fold band intensity;
the shuffle comparison is below the +0.005 gate and does not survive Holm.
The intensity control is the highest-scoring FTIR arm. C4 fails.

## What P21 does and does not show

- It does show that, in this dataset, hand-built role weights are not a
  deployable improvement over `full8_base`.
- It does show that group-size normalisation is destructive for this feature
  set: `full8_gn_base` is 0.0625 QWK below `full8_base`.
- It does show that direct role weights, without group-size normalisation,
  are statistically indistinguishable from direct mass weights.
- It does **not** disprove the chemistry claim that catalyst is functionally
  critical. It disproves only the claim that the current five catalyst-related
  columns, weighted or transformed this way, yield a measurable T-bend gain.
- It does **not** validate raw-peak FTIR weighting; only 8 band fractions were
  available.

## Next-step constraints

Any P22 should not simply tune these weights harder. The direct control
already says the weight values are not the bottleneck. A more defensible next
step is to improve the catalyst representation itself (catalyst type,
acid strength, cure-kinetics proxy, dose-response shape) or use a
nested-validated supervised selector, and to compare against
`full8_base` with the same group CV. Until that exists, the manual
role-prior route should remain closed.
