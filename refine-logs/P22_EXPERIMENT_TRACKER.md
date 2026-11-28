# P22 Experiment Tracker

| Run ID | Milestone | Purpose | System / Variant | Split | Metrics | Priority | Status | Notes |
|---|---|---|---|---|---|---|---|---|
| R001 | M0 | feature triage | 13 omitted mechanism columns | GroupKFold(5) by formula_id, Ridge reconstruction | R², Spearman, coverage | MUST | DONE | `data/P22_FEATURE_TRIAGE.csv`; CURE2 selected; acid/type/7-formulation rejected |
| R002 | M0 | freeze config | P22 config + CURE2 columns | n/a | dims, hashes | MUST | DONE | `results/p22_config.json`; raw dims 191/193/192/194; P21 seeds; C=2.0 |
| R003 | M0 | sanity | 6 arms | 1 seed ×5 folds | QWK, dims, finite | MUST | DONE | `full8_base` seed42 `0.5761275403`; exact P20 `0.576128`; 30 audit rows |
| R004 | M1 | main full | 6 arms | 20 seeds ×5 folds | QWK, FR, HR, p | MUST | DONE | 600 fits; 120 per-seed rows; 36,120 OOF rows |
| R005 | M2 | LOCO stress | 4 arms | 20 seeds ×2 conditions | pooled QWK, FR, HR | MUST | DONE | A=200/10 (119), B=205/17 (182); `cure_state` 0.327897; no cross-condition p |
| R006 | M2 | LOSO support | 4 arms | 20 seeds ×21 series | pooled QWK, FR, HR | NICE | SKIPPED | Pre-registered stop/go: C1 failed, so LOSO not run |
| R007 | M3 | simplicity | `cure_state_tg` vs `cure_state` | 20 seeds ×5 folds | QWK, FR, HR | NICE | DONE | CURE3 `0.575539` vs CURE2 `0.579188`; not upgraded |
| R008 | M3 | audit | deterministic local checks | n/a | audit checklist | MUST | DONE | 24/24 pass; `PROVISIONAL_LOCAL_AUDIT`; dimensions/OOF/prep/placebo checks |
| R009 | M3 | claim | C1/C2/C3 | n/a | gate JSON | MUST | DONE | C1/C2 fail; C3 supporting pass; `claim_supported=false`; `REVIEW_UNAVAILABLE` |
| R010 | M3 | report | P22 report + README | n/a | numbers | MUST | DONE | `results/P22_实验报告.md`, `README.md`, claim, audit |
| R011 | M4 | archive | GitHub remote | n/a | key files | MUST | DONE | GitHub connector; commits `951b8dc`, `1b24923`, `8e52bfc`, `b013db8`; key-result archive |

## Status notes

- R001: 301 T rows, grades `33/197/71`, 191 base. `cure_drive` R² `0.2887`, `cure_margin_eff` R² `0.7236`; `tg_rise_est` R² `0.9546` (exploratory only). `AC040`/`AZ135` absent; `acid_phosphate_frac` vs `eq_cat` Spearman `0.99999`; `volatile_frac` vs `solids_frac` `−1.0000`.
- R003: `full8_base` seed 42 QWK `0.5761275403`, exact P20 `0.576128` within 1e-6; all arms finite; raw/effective dims checked.
- R004: Main 20-seed results: `full8_base` `0.570181 ± 0.024523`; `cure_state` `0.579188 ± 0.021923`; `cure_state_shuffle` `0.564584 ± 0.021782`; `bake_control` `0.582640 ± 0.022421`; `cure_state_plus_bake` `0.579028 ± 0.023242`; `cure_state_tg` `0.575539 ± 0.023153`.
- R005: `full8_base` LOCO `0.463109`; `cure_state` `0.327897`; `bake_control` `0.460770`; `cure_state_plus_bake` `0.327897`. LOCO is descriptive only: 2 fixed condition folds and seed-deterministic predictions (sd=0), so no cross-condition p-value.
- R008: 24/24 deterministic checks pass; `full8_base` exact sanity, 301×20×5 OOF coverage, imputer/scaler train-only, shuffle no-y, `cure_205` 182/119, no test tuning.
- R009: C1 fail (`+0.009007 < +0.010`, 12/20, Holm p `0.20269`, HR `−2.042 pp`); C2a fail (`−0.003612`, 6/20); C2b fail (`−0.135212`, 0/20); C3 supporting pass (`+0.014604`, 14/20, p `0.01530`). `claim_supported=false`; `verdict: REVIEW_UNAVAILABLE`.
- R010: P22 is a negative result. No new arm is adopted; baseline remains `full8_base` (191 raw) + ordinal logistic C=2. Next step is P23 continuous-T supervision or new measurements, not more handcrafted features.
