# P21 Experiment Audit

- audit_status: `PROVISIONAL_LOCAL_AUDIT`
- external_review: `REVIEW_UNAVAILABLE`
- checks: **27 / 27 pass**

| check | pass | detail |
|---|---|---|
| `role_map_rows` | PASS | `{"rows": 191}` |
| `role_map_unique` | PASS | `{"unique": 191}` |
| `role_map_groups` | PASS | `{"groups": ["catalyst_kinetics", "cure_crosslink", "filler_pigment", "formulation_balance", "ftir_band", "molecular_descriptor", "other", "resin_network", "solvent_additive"]}` |
| `role_map_other` | PASS | `{"other": ["frac_rare_total", "rtype_其他"]}` |
| `catalyst_group` | PASS | `{"features": ["frac_10%磷酸", "frac_AC040", "frac_AZ135", "eq_cat", "cat_per_epoxy_eq"]}` |
| `role_weight_mean1` | PASS | `{"mean": 0.9999999999999998}` |
| `mass_weight_mean1` | PASS | `{"mean": 1.0}` |
| `mass_share_sum` | PASS | `{"sum": 1.0000000000000004, "shares": {"resin_network": 0.6780585983572582, "cure_crosslink": 0.15619555655109826, "catalyst_kinetics": 0.012077244873885949, "filler_pigment": 0.0, "solvent_additive": 0.15366860021775805}}` |
| `per_seed_rows` | PASS | `{"rows": 300}` |
| `per_seed_unique` | PASS | `{"max_group": 1}` |
| `arms` | PASS | `{"arms": ["ftir_band_intensity", "ftir_band_role", "ftir_band_shuffle", "full8_base", "full8_gn_base", "interact", "interact_shuffle", "log_cat", "log_cat_ratio", "mass_prior", "mass_prior_direct", "role_prior", "role_prior_direct", "role_prior_shuffle", "two_part_cat"]}` |
| `seeds` | PASS | `{"n": 20, "config_seeds": [42, 202, 777, 1234, 2026, 31415, 2718, 1618, 5678, 9999, 123, 456, 789, 1011, 1213, 1415, 1617, 1819, 2021, 2223]}` |
| `oof_rows` | PASS | `{"rows": 90300}` |
| `oof_per_arm_seed` | PASS | `{"sizes": [301]}` |
| `oof_probability_sum` | PASS | `{"max_abs_err": 1.0000011929633956e-10}` |
| `oof_finite` | PASS | `{"nan": {"p0": 0, "p1": 0, "p2": 0}}` |
| `label_distribution` | PASS | `{"counts": {"0": 33, "1": 197, "2": 71}}` |
| `audit_rows` | PASS | `{"rows": 1500}` |
| `audit_flags` | PASS | `{"test_transform_fitted": [false], "target_used_in_weights": [false]}` |
| `audit_norm_finite` | PASS | `{"nan": {"baseline_norm": 0, "train_weighted_norm": 0, "norm_scale": 0}}` |
| `arm_dimensions` | PASS | `{"expected": {"full8_base": 191, "full8_gn_base": 191, "mass_prior": 191, "role_prior": 191, "role_prior_shuffle": 191, "mass_prior_direct": 191, "role_prior_direct": 191, "log_cat": 191, "log_cat_ratio": 191, "two_part_cat": 192, "interact": 195, "interact_shuffle": 195, "ftir_band_role": 191, "ftir_band_intensity": 191, "ftir_band_shuffle": 191}, "actual": {"ftir_band_intensity": 191, "ftir_band_role": 191, "ftir_band_shuffle": 191, "full8_base": 191, "full8_gn_base": 191, "interact": 195, "interact_shuffle": 195, "log_cat": 191, "log_cat_ratio": 191, "mass_prior": 191, "mass_prior_direct": 191, "role_prior": 191, "role_prior_direct": 191, "role_prior_shuffle": 191, "two_part_cat": 192}}` |
| `group_split_no_leakage` | PASS | `{"n_splits_checked": 100}` |
| `p20_baseline_reproduction` | PASS | `{"shared_seeds": 10, "max_abs_diff": 0.0, "p21_shared_mean": 0.5739744798099999, "p20_shared_mean": 0.5739744798099999}` |
| `no_aux_labels` | PASS | `{"no_aux_labels": true}` |
| `fixed_c` | PASS | `{"c_fixed": 2.0}` |
| `claim_verdict` | PASS | `{"verdict": "REVIEW_UNAVAILABLE", "claim_supported": false}` |
| `claim_gate_structure` | PASS | `{"C1": false, "C2": false, "C3": false, "C4": false}` |

## Claim gates

| gate | local result |
|---|---|
| C1 | FAIL |
| C2 | FAIL |
| C3 | FAIL |
| C4 | FAIL |

The external cross-model reviewer is unavailable. This is a local deterministic audit only; no acquittal is claimed.
