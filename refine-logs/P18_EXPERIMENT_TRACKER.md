# P18 Experiment Tracker

| Run ID | Milestone | Purpose | System / Variant | Split | Metrics | Priority | Status | Notes |
|---|---|---|---|---|---|---|---|---|
| R001 | M0 | sanity | full8, 1 seed | outer 5 / inner 4 | shape, coverage, proba sum, no group overlap | MUST | DONE | 301 条全覆盖；assert 通过 |
| R002 | M0 | threshold provenance | nested_three_way_temp | outer 5 / inner 4 | thresholds only from inner OOF | MUST | DONE | `select_thresholds(ytr, source)`；外层测试不参与 |
| R003 | M1 | main | argmax / P17 fixed / nested raw / nested temp | outer 5 / inner 4, 10 seeds | FR, test, high recall, QWK, cost | MUST | DONE | 47 臂；C1/C2 均 FAIL |
| R004 | M1 | sensitivity | three_way / selective temp | 10 seeds | cost × capacity Pareto | MUST | DONE | 42 个 temp 臂；cap 25% 下 cfr 不改变决策 |
| R005 | M1 | calibration | temp scaling | 10 seeds | NLL, ECE, T | NICE | DONE | T 2.964；46/50 在上界 3.0 |
| R006 | M2 | audit | all results | — | evidence existence / threshold provenance | MUST | DONE | WARN / PROVISIONAL_LOCAL_AUDIT |
| R007 | M3 | report | full | — | C1/C2 verdict | MUST | DONE | C1 pass=false, C2 pass=false |
