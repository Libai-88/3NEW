# P21 Remote Archive

**Local commit**: `23b8255` (`P21: test role-criticality priors and importance-aware features (negative result)`)  
**Remote branch**: `experiment/p14-best`  
**Repository**: `https://github.com/Libai-88/3NEW`  
**Date**: 2026-11-28

## Verdict

P21 is a negative result. The pre-registered C1/C2/C3/C4 gates all fail.
`role_prior` passes `role_prior − mass_prior` (+0.022758, 19/20) and
`role_prior − role_prior_shuffle` (+0.009394, 17/20), but fails
`role_prior − full8_gn_base` (+0.002627, 11/20, p=0.29058) and
`role_prior − full8_base` (−0.059878). The direct control
`role_prior_direct − mass_prior_direct` is +0.001243, 10/20, p=0.81164:
without group-size normalisation, role weights have no advantage over mass
weights. C2/C3/C4 also fail. External review is unavailable; local audit is
`PROVISIONAL_LOCAL_AUDIT`, 27/27 checks pass.

## Archived files

- `experiments/P21_role_feature_prior/README.md`
- `experiments/P21_role_feature_prior/data/P21_ROLE_MAP.csv`
- `experiments/P21_role_feature_prior/data/P21_GROUP_WEIGHTS.json`
- `experiments/P21_role_feature_prior/scripts/p21_role_feature_prior.py`
- `experiments/P21_role_feature_prior/scripts/p21_audit.py`
- `experiments/P21_role_feature_prior/results/P21_实验报告.md`
- `experiments/P21_role_feature_prior/results/P21_CLAIMS_FROM_RESULTS.md`
- `experiments/P21_role_feature_prior/results/P21_EXPERIMENT_AUDIT.md`
- `experiments/P21_role_feature_prior/results/P21_EXPERIMENT_AUDIT.json`
- `experiments/P21_role_feature_prior/results/p21_full_summary.csv`
- `experiments/P21_role_feature_prior/results/p21_full_per_seed.csv`
- `experiments/P21_role_feature_prior/results/p21_full_delta.csv`
- `experiments/P21_role_feature_prior/results/p21_full_specificity.csv`
- `experiments/P21_role_feature_prior/results/p21_full_claim_check.json`
- `experiments/P21_role_feature_prior/results/p21_full_config.json`
- `experiments/P21_role_feature_prior/results/p21_full_audit.csv`
- `experiments/P21_role_feature_prior/results/p21_map_audit.json`
- `experiments/P21_role_feature_prior/logs/p21_map.log`
- `experiments/P21_role_feature_prior/logs/p21_sanity.log`
- `experiments/P21_role_feature_prior/logs/p21_full.log`
- `experiments/P21_role_feature_prior/logs/p21_audit.log`
- `refine-logs/P21_EXPERIMENT_PLAN.md`
- `refine-logs/P21_WEIGHT_RUBRIC.md`
- `refine-logs/P21_EXPERIMENT_TRACKER.md`

The 5.9 MB `p21_full_oof_proba.csv` stays local (as P19/P20 did for large
OOF artifacts); the 90,300-row OOF is reproducible with the commands in the
README. The 15-arm full run uses only the 301 observed T labels and 20 seeds.

## Reproduction

```bash
python3 experiments/P21_role_feature_prior/scripts/p21_role_feature_prior.py --mode map
python3 experiments/P21_role_feature_prior/scripts/p21_role_feature_prior.py --mode sanity --tag sanity
python3 experiments/P21_role_feature_prior/scripts/p21_role_feature_prior.py --mode full --tag full
python3 experiments/P21_role_feature_prior/scripts/p21_audit.py
```
