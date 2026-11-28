# P21 Remote Archive

**Local commits**: `23b8255` (experiment), `53a9971` (archive manifest)  
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

## Remote commits

- `13d494773e5cbd7d65167be7b620e20ab403863b` — README, report, claim, audit and this manifest
- `01be105239fd05493297d89c72df3146b9ecc302` — group weights, summary, delta, specificity, claim JSON, config, map audit
- `42131820e8a823f89c4f7f5c2334bfec2df1d338` — role map, pre-registration, weight rubric, tracker

## Archived key files

- `experiments/P21_role_feature_prior/README.md`
- `experiments/P21_role_feature_prior/P21_REMOTE_ARCHIVE.md`
- `experiments/P21_role_feature_prior/data/P21_ROLE_MAP.csv`
- `experiments/P21_role_feature_prior/data/P21_GROUP_WEIGHTS.json`
- `experiments/P21_role_feature_prior/results/P21_实验报告.md`
- `experiments/P21_role_feature_prior/results/P21_CLAIMS_FROM_RESULTS.md`
- `experiments/P21_role_feature_prior/results/P21_EXPERIMENT_AUDIT.md`
- `experiments/P21_role_feature_prior/results/P21_EXPERIMENT_AUDIT.json`
- `experiments/P21_role_feature_prior/results/p21_full_summary.csv`
- `experiments/P21_role_feature_prior/results/p21_full_delta.csv`
- `experiments/P21_role_feature_prior/results/p21_full_specificity.csv`
- `experiments/P21_role_feature_prior/results/p21_full_claim_check.json`
- `experiments/P21_role_feature_prior/results/p21_full_config.json`
- `experiments/P21_role_feature_prior/results/p21_map_audit.json`
- `refine-logs/P21_EXPERIMENT_PLAN.md`
- `refine-logs/P21_WEIGHT_RUBRIC.md`
- `refine-logs/P21_EXPERIMENT_TRACKER.md`

## Local-only artifacts

As with P19/P20, the large/reproducible artifacts stay in the local repository
rather than in the remote archive:

- `scripts/p21_role_feature_prior.py` — 15-arm runner.
- `scripts/p21_audit.py` — 27-check local audit.
- `results/p21_full_per_seed.csv` — 300 per-seed rows.
- `results/p21_full_audit.csv` — 1,500 fold-level audit rows.
- `results/p21_full_oof_proba.csv` — 90,300 OOF rows (5.9 MB).
- `logs/` — map/sanity/full/audit logs.

The remote archive is intentionally key-result only. The local commits above
contain the full runnable tree; the remote commits contain the data, reports
and gate outputs needed to read the result without the 5.9 MB OOF.

## Reproduction (local tree)

```bash
python3 experiments/P21_role_feature_prior/scripts/p21_role_feature_prior.py --mode map
python3 experiments/P21_role_feature_prior/scripts/p21_role_feature_prior.py --mode sanity --tag sanity
python3 experiments/P21_role_feature_prior/scripts/p21_role_feature_prior.py --mode full --tag full
python3 experiments/P21_role_feature_prior/scripts/p21_audit.py
```
