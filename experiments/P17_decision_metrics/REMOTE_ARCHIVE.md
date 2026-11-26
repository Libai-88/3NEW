# P17 远程归档边界

**日期**：2026-11-26  
**远程分支**：`experiment/p14-best`  
**状态**：报告、审计、汇总表、逐 seed 表、风险曲线、claim check、配置、脚本、日志和计划/tracker 进入远程；完整 OOF 概率矩阵留在本地，按 SHA256 可复现。

## 已进入远程

- `README.md`
- `results/P17_实验报告.md`
- `results/P17_EXPERIMENT_AUDIT.md`
- `results/P17_EXPERIMENT_AUDIT.json`
- `results/P17_CLAIMS_FROM_RESULTS.md`
- `results/p17_policy_summary_full.csv`
- `results/p17_policy_delta_full.csv`
- `results/p17_policy_per_seed_full.csv`
- `results/p17_risk_coverage_full.csv`
- `results/p17_claim_check_full.json`
- `results/p17_config_full.json`
- `results/p17_policy_summary_sanity.csv`
- `results/p17_policy_per_seed_sanity.csv`
- `results/p17_policy_delta_sanity.csv`
- `results/p17_risk_coverage_sanity.csv`
- `results/p17_claim_check_sanity.json`
- `results/p17_config_sanity.json`
- `scripts/p17_decision_metrics.py`
- `logs/p17_full.log`
- `logs/p17_sanity.log`
- `../../refine-logs/P17_EXPERIMENT_PLAN.md`
- `../../refine-logs/P17_EXPERIMENT_TRACKER.md`

## 本地保留（远程未推）

| 文件 | 大小 | SHA256 |
|---|---:|---|
| `results/p17_oof_proba_full.csv` | 363126 B | `dfd94624c269fc2fee0b60e09cbb67ceb718ee615dac3c0468552e8e14efce80` |
| `results/p17_oof_proba_sanity.csv` | 35317 B | `074112db69ed105eb059e6122e3c8dd5a84c715ffa6c97897da774e2bbcaa463` |

> 若需远程完整复算，按下面的命令在本地重生成；OOF 文件是同一协议的可复现中间产物。

## 复现

```bash
tooling/run.sh python3 experiments/P17_decision_metrics/scripts/p17_decision_metrics.py \
  --mode full --seeds 42 202 777 1234 2026 31415 2718 1618 5678 9999 \
  --systems full8 p14_190 --tag full
```

OOF 由外层 `StratifiedGroupKFold(5)` 产生；`full8` 的 C 在训练折内 nested。重新生成前请确认 `合并版数据集.xlsx`、`feature_matrix_p13_t_ftir8.csv` 等输入 SHA 与 P15/P16 归档一致。
