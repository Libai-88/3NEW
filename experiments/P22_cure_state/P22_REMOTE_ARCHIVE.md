# P22 Remote Archive

**Repository**: `https://github.com/Libai-88/3NEW`  
**Branch**: `experiment/p14-best`  
**Date**: 2026-11-29  
**Scope**: key-result archive. The full runnable tree remains in the local repository.

## Verdict

P22 is a negative result. `cure_state = cure_drive + cure_margin_eff` gives
QWK `+0.009007` over `full8_base` (below the pre-registered `+0.010`; 12/20
seeds; Holm p `0.20269`), and fails the high-recall guardrail (`−2.042 pp`).
`cure_state_plus_bake − bake_control` is `−0.003612` (6/20). Leave-one-
condition-out collapses `cure_state` from `0.463109` to `0.327897`
(`−0.135212`, 0/20), while the binary `bake_control` stays at `0.460770`.
C1/C2 fail. C3 passes as supporting only (`+0.014604`, 14/20, p `0.01530`)
and does not rescue the route.

Local deterministic audit is 24/24, `PROVISIONAL_LOCAL_AUDIT`. External
cross-model review is unavailable, so the claim remains
`REVIEW_UNAVAILABLE` with `claim_supported=false`.

## Remote commits

- `PENDING` — key report, claim, audit, summaries and config.
- `PENDING` — feature triage, pre-registration, tracker and archive manifest update.

## Archived key files

- `experiments/P22_cure_state/README.md`
- `experiments/P22_cure_state/P22_REMOTE_ARCHIVE.md`
- `experiments/P22_cure_state/data/P22_FEATURE_TRIAGE.csv`
- `experiments/P22_cure_state/data/P22_FEATURE_TRIAGE.json`
- `experiments/P22_cure_state/results/P22_实验报告.md`
- `experiments/P22_cure_state/results/P22_CLAIMS_FROM_RESULTS.md`
- `experiments/P22_cure_state/results/P22_EXPERIMENT_AUDIT.md`
- `experiments/P22_cure_state/results/P22_EXPERIMENT_AUDIT.json`
- `experiments/P22_cure_state/results/p22_main_summary.csv`
- `experiments/P22_cure_state/results/p22_loco_summary.csv`
- `experiments/P22_cure_state/results/p22_sanity_summary.csv`
- `experiments/P22_cure_state/results/p22_claim_check.json`
- `experiments/P22_cure_state/results/p22_config.json`
- `refine-logs/P22_EXPERIMENT_PLAN.md`
- `refine-logs/P22_EXPERIMENT_TRACKER.md`

## Local-only artifacts

As with P19/P20/P21, large or reproducible artifacts stay in the local
repository rather than in the remote key-result archive:

- `scripts/p22_feature_triage.py` — data triage.
- `scripts/p22_cure_state.py` — sanity/main/LOCO runner.
- `scripts/p22_audit.py` — 24-check local audit and claim gate.
- `results/p22_main_per_seed.csv` — 120 per-seed rows.
- `results/p22_main_audit.csv` — 600 fold-level audit rows.
- `results/p22_main_oof_proba.csv` — 36,120 OOF rows (2.4 MB).
- `results/p22_loco_per_seed.csv` — 80 per-seed rows.
- `results/p22_loco_audit.csv` — 160 fold-level audit rows.
- `results/p22_loco_oof_proba.csv` — 24,080 OOF rows (1.7 MB).
- `results/p22_sanity_audit.csv`, `results/p22_sanity_oof_proba.csv`.
- `logs/` — triage/sanity/main/loco/audit logs.

## Reproduction

From the repository root:

```bash
python3 experiments/P22_cure_state/scripts/p22_feature_triage.py
python3 experiments/P22_cure_state/scripts/p22_cure_state.py --mode sanity --tag sanity
python3 experiments/P22_cure_state/scripts/p22_cure_state.py --mode main --tag main
python3 experiments/P22_cure_state/scripts/p22_cure_state.py --mode loco --tag loco
python3 experiments/P22_cure_state/scripts/p22_audit.py
```

LOSO is intentionally not run: the pre-registered stop/go rule required C1 to
pass before LOSO; C1 failed.
