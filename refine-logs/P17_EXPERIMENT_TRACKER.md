# Experiment Tracker — P17 decision metrics

**Last update**：2026-11-26  
**Branch**：`experiment/p14-best`  
**Status**：M0 sanity、M1 full、M2 analysis 全部完成；C1/C2 均 `pass=false`；报告/审计已写入。

| Run ID | Milestone | Purpose | System / Variant | Split | Metrics | Priority | Status | Notes |
|---|---|---|---|---|---|---|---|---|
| R001 | M0 | sanity full8 | full8 | 1 seed, 5 outer | OOF shapes, policy counts | MUST | DONE | 11.4 s；301 条 OOF；概率和=1 |
| R002 | M0 | sanity p14_190 | p14_190 | 1 seed, 5 outer | OOF shapes, policy counts | MUST | DONE | 11.4 s；301 条 OOF；概率和=1 |
| R003 | M1 | OOF for decisions | full8 | 10 seeds, 5 outer | OOF probabilities | MUST | DONE | 301/seed；QWK argmax 0.5668 与 P16 一致 |
| R004 | M1 | OOF for decisions | p14_190 | 10 seeds, 5 outer | OOF probabilities | MUST | DONE | 301/seed；QWK argmax 0.5797 与 P14 一致 |
| R005 | M2 | policy summary | all | 10 seeds | operational cost, false release, test rate, coverage | MUST | DONE | `p17_policy_summary_full.csv` |
| R006 | M2 | risk-coverage curve | selective/high_guard | 10 seeds | coverage-risk | NICE | DONE | `p17_risk_coverage_full.csv` |

## Run summary

- sanity：`p17_sanity.log`，11.4 s；`p17_oof_proba_sanity.csv` 等。
- full：`p17_full.log`，98.3 s（2 vCPU / 3.9 GiB，无 GPU）；10 seeds × 2 systems，6020 行 OOF。
- claim check：`p17_claim_check_full.json`；`full8` 与 `p14_190` 的 C1/C2 均 `pass=false`。

## Key outcomes

- `full8` `three_way`：false release `21.41% → 3.66%`（相对 −82.9%），test `21.40%`，cost `−0.0372`（p `0.0319`，7/10）→ C1 FAIL（cost 幅度不足）。
- `full8` `selective τ=.60`：coverage `81.16%`，false release `−30.26%`，QWK `+0.0629`，但全体 high recall `−7.89 pp` → C2 FAIL。
- 补充口径：`selective` 接受样本 high recall `+3.94 pp`，high test rate `14.37%`；不改变 C2 预注册失败。
- `p14_190` 同方向：C1 FAIL（cost `−0.0425`），C2 FAIL（false release 相对 −26.85%，high recall −8.17 pp）。

## Blockers

- No new data; all conclusions are within the current 301 T labels.
- External cross-model reviewer unavailable; integrity status `PROVISIONAL_LOCAL_AUDIT`.
- Cost weights are illustrative relative weights, not customer-confirmed amounts.

## Artifacts

- `experiments/P17_decision_metrics/results/P17_实验报告.md`
- `experiments/P17_decision_metrics/results/P17_EXPERIMENT_AUDIT.md`
- `experiments/P17_decision_metrics/results/p17_policy_summary_full.csv`
- `experiments/P17_decision_metrics/results/p17_policy_delta_full.csv`
- `experiments/P17_decision_metrics/results/p17_risk_coverage_full.csv`
- `experiments/P17_decision_metrics/results/p17_claim_check_full.json`
