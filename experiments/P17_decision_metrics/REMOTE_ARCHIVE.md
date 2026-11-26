# P17 远程归档边界

**日期**：2026-11-26  
**远程分支**：`experiment/p14-best`  
**状态**：P17 的报告、审计、claim、汇总表、配置、脚本、计划/tracker 和索引已进入远程；完整 OOF、逐 seed 表、风险曲线、日志和 sanity 结果留在本地完整归档。远程仓库足以复核结论；需要重算时按下方命令在本地重生成。

## 已进入远程

- `experiments/P17_decision_metrics/README.md`
- `experiments/P17_decision_metrics/results/P17_实验报告.md`
- `experiments/P17_decision_metrics/results/P17_EXPERIMENT_AUDIT.md`
- `experiments/P17_decision_metrics/results/P17_EXPERIMENT_AUDIT.json`
- `experiments/P17_decision_metrics/results/P17_CLAIMS_FROM_RESULTS.md`
- `experiments/P17_decision_metrics/results/p17_policy_summary_full.csv`
- `experiments/P17_decision_metrics/results/p17_claim_check_full.json`
- `experiments/P17_decision_metrics/results/p17_config_full.json`
- `experiments/P17_decision_metrics/scripts/p17_decision_metrics.py`
- `experiments/P17_decision_metrics/REMOTE_ARCHIVE.md`
- `experiments/README.md`
- `refine-logs/P17_EXPERIMENT_PLAN.md`
- `refine-logs/P17_EXPERIMENT_TRACKER.md`

## 本地保留（远程未推）

| 文件 | 大小 | SHA256 |
|---|---:|---|
| `results/p17_oof_proba_full.csv` | 363126 B | `dfd94624c269fc2fee0b60e09cbb67ceb718ee615dac3c0468552e8e14efce80` |
| `results/p17_oof_proba_sanity.csv` | 35317 B | `074112db69ed105eb059e6122e3c8dd5a84c715ffa6c97897da774e2bbcaa463` |
| `results/p17_policy_per_seed_full.csv` | 25676 B | `eb11f021ba22069015016c60bd1a17903aabbdf2ca3ed3b11a99b359e1aa7f29` |
| `results/p17_policy_delta_full.csv` | 11886 B | `e9169c125c1888ec3c065efe3d510078f88baf4715150a333399efefd52076fd` |
| `results/p17_risk_coverage_full.csv` | 47287 B | `a703c568187f66b4503eb1a45413a68720734e3686348a6026e1b429fa6774ee` |
| `logs/p17_full.log` | 12162 B | `9573f0f753a8742ce49f15959b62929747e3004ccbdbc270b87ea8eb19b3aca7` |
| `logs/p17_sanity.log` | 8591 B | `a0a279bc0626f4b1ad8649eb3043cf01f950fc36f26228b7fb22d55c9ae9ea8e` |

> 若需远程完整复算，按下面的命令在本地重生成；OOF 是同一协议的可复现中间产物。P17 报告已经列出逐 seed/曲线关键数字，远程不携带大表不影响结论复核。

## 复现

```bash
tooling/run.sh python3 experiments/P17_decision_metrics/scripts/p17_decision_metrics.py \
  --mode full --seeds 42 202 777 1234 2026 31415 2718 1618 5678 9999 \
  --systems full8 p14_190 --tag full
```

OOF 由外层 `StratifiedGroupKFold(5)` 产生；`full8` 的 C 在训练折内 nested。重新生成前请确认 `合并版数据集.xlsx`、`feature_matrix_p13_t_ftir8.csv` 等输入 SHA 与 P15/P16 归档一致。
