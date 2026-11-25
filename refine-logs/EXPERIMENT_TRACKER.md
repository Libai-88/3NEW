# Experiment Tracker — P15 feature robustness

**Last update**：2026-11-25

**Branch**：`experiment/p14-best`

**Status**：P15-B full 完成；审计已出 provisional 报告；P15/P16 已归档到远程分支。

| Item | Status | Evidence/Notes |
|---|---|---|
| P0–P14 audit | completed provisional | `experiments/AUDIT_2026-11-25/EXPERIMENT_AUDIT.md`; 5 PASS / 6 WARN / 0 FAIL |
| Audit machine JSON | completed | `experiments/AUDIT_2026-11-25/EXPERIMENT_AUDIT.json` |
| Claim ledger | completed | `experiments/AUDIT_2026-11-25/CLAIMS_FROM_RESULTS.md` |
| P15 plan | completed | `refine-logs/EXPERIMENT_PLAN.md` |
| P15-A residual pilot sanity | completed (1 seed) | `results/p15_sanity_*`; QWK base 0.5400 / raw 0.5810 / resid 0.5401; not confirmatory |
| P15-B nested selection sanity | completed (1 seed) | `results/p15b_sanity_*`; QWK 0.5705; selection dispersed |
| P15-B nested selection full | completed | `logs/p15b_full.log`; 10 seeds; mean QWK 0.571704 ±0.023059; P14 190 fixed delta −0.007986, p 0.090259, 3/10 seeds positive |
| P15 report | completed | `results/P15_实验报告.md` |
| Git commit/push | completed | local P15/P16 commits; remote branch updated by connector |
| Remote data manifest | existing (P14) | `experiments/P14_evidence_chain/REMOTE_DATA.md` |

## Blockers

- Independent cross-model reviewer unavailable; audit verdict remains `PROVISIONAL_LOCAL_AUDIT` and `REVIEW_UNAVAILABLE`.

## Next actions

1. Read `results/P15_实验报告.md` and check the pre-registered decision table.
2. Keep large matrices local and rely on `REMOTE_DATA.md`.
3. If continuing, pre-register P17 core4_w only; do not post-hoc search full8.
