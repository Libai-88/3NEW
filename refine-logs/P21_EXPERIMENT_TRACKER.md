# P21 Experiment Tracker

| Run ID | Milestone | Purpose | System / Variant | Split | Metrics | Priority | Status | Notes |
|---|---|---|---|---|---|---|---|---|
| R001 | M0 | freeze role map | `P21_ROLE_MAP.csv` + group weights | n/a | coverage, counts | MUST | DONE | 191/191; 9 groups; `other`=2; catalyst=5; no y |
| R002 | M0 | sanity baseline | `full8_base` vs P20 | 1 seed ×5 folds | QWK | MUST | DONE | seed 42 `0.576128`, exact P20 sanity |
| R003 | M0 | sanity all arms | 15 arms incl. direct controls | 1 seed ×5 folds | QWK/NaN/dims | MUST | DONE | finite, dims 191/192/195; seed 42 `full8_base` exact |
| R004 | M1 | full | 15 arms (13 pre-registered + 2 exploratory) | 20 seeds ×5 folds | QWK, FR, HR, p | MUST | DONE | `full8_base` 0.570181 ± 0.024523; 300 per-seed rows; 90,300 OOF |
| R005 | M2 | audit | local deterministic | n/a | 27 checks | MUST | DONE | 27/27 pass; `PROVISIONAL_LOCAL_AUDIT`; external `REVIEW_UNAVAILABLE` |
| R006 | M2 | claim | C1–C4 | n/a | gate JSON | MUST | DONE | C1/C2/C3/C4 all fail; claim_supported=false |
| R007 | M2 | report | P21 report | n/a | numbers | MUST | DONE | `results/P21_实验报告.md`, README, claim, audit |
| R008 | M2 | archive | GitHub remote | n/a | files | MUST | DONE | GitHub connector; remote commits `13d4947`, `01be105` |

## Status notes

- R002/R003: `full8_base` seed 42 exactly `0.576128` as P20. `full8_gn_base`
  is `0.517882`, showing groupnorm cost before full; direct controls added and
  documented before full.
- R004: P21 `full8_base` on the 10 P20 seeds exactly matches P20 per-seed
  (max abs diff 0.0; shared mean 0.573974). P21 20-seed mean is 0.570181.
- R006: C1 sub-comparisons role vs mass and role vs shuffle pass, but
  non-inferiority vs `full8_base` and role vs `full8_gn_base` fail; direct
  role vs direct mass is +0.001243, p=0.812. C1 fails overall.
- R006: C2/C3/C4 fail; C4 role vs shuffle raw p=0.0456 but Holm p=0.0912 and
  delta +0.004852 below the +0.005 gate; intensity control is highest FTIR arm.
