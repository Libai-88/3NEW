# P18 远程归档说明

**远程仓库**：`https://github.com/Libai-88/3NEW`  
**目标分支**：`experiment/p14-best`  
**P18 归档日期**：2026-11-26  
**P18 结论**：C1/C2 均 FAIL；当前 301 条 T 标签下无稳定可部署的嵌套决策策略。

## 已进入远程分支的文件

- `README.md`（根索引，含 P18 行）
- `experiments/README.md`（实验索引，含 P18 行）
- `refine-logs/P18_EXPERIMENT_PLAN.md`
- `refine-logs/P18_EXPERIMENT_TRACKER.md`
- `experiments/P18_nested_decision_policy/README.md`
- `experiments/P18_nested_decision_policy/REMOTE_ARCHIVE.md`
- `experiments/P18_nested_decision_policy/scripts/p18_nested_decision.py`
- `experiments/P18_nested_decision_policy/results/P18_实验报告.md`
- `experiments/P18_nested_decision_policy/results/P18_EXPERIMENT_AUDIT.md`
- `experiments/P18_nested_decision_policy/results/P18_EXPERIMENT_AUDIT.json`
- `experiments/P18_nested_decision_policy/results/P18_CLAIMS_FROM_RESULTS.md`
- `results/p18_policy_summary_full.csv`
- `results/p18_policy_delta_full.csv`
- `results/p18_cost_sensitivity_full.csv`
- `results/p18_calibration_full.csv`
- `results/p18_claim_check_full.json`
- `results/p18_config_full.json`

## 仅本地保存的文件

以下大文件没有推送到远程；它们是完整证据链的一部分，但远程只保留可复核的汇总、claim、审计与脚本。

| 文件 | 行数/说明 | 大小 | SHA256 |
|---|---:|---:|---|
| `results/p18_oof_proba_full.csv` | 3010 行，10 seeds × 301，raw + calibrated OOF | 321,176 B | `6c3dd04acfe19bed11ca2009c7e9668d6390a403b095b0812a43ca5e15f7e950` |
| `results/p18_thresholds_full.csv` | 2200 行，44 nested arms × 50 folds，含 `feasible`/`violation` | 437,487 B | `a5eb300e92bcaa7255a28f228ce2943d0eb5e95851954208384b121cf502a364` |
| `results/p18_policy_per_seed_full.csv` | 470 行，47 arms × 10 seeds | 110,183 B | `85bb0c56e9c6ef3f3bdf9432da4f8ecbd777bc1eddab7401f3b543d391f68465` |
| `logs/p18_full.log` | 10 seeds full 运行日志 | 6,970 B | `e990ff1d3230982fe74c47b00ed7c741e343b9c7ffd0272662c9d34e1625c0da` |
| `logs/p18_sanity.log` | 1 seed sanity 运行日志 | 4,294 B | `d67126e9a0b5279105969aaeda153a5fa12400a83d0b8cd9dc68cd2135f8ecb2` |

sanity 版工件（`p18_*_sanity.csv/json`）同样留在本地，未推送。

## 复现命令

```bash
tooling/run.sh python3 experiments/P18_nested_decision_policy/scripts/p18_nested_decision.py \
  --mode sanity --tag sanity

tooling/run.sh python3 experiments/P18_nested_decision_policy/scripts/p18_nested_decision.py \
  --mode full --seeds 42 202 777 1234 2026 31415 2718 1618 5678 9999 --tag full
```

## 边界

- P18 是负结果，不能把 10-seed 均值接近 C1 写成通过；严格 C1 seed gate 是 3/10，C2 seed gate 是 1/10。
- 内层约束多数无可行解：`three_way` 主设置 11/50 折，`selective` 0/50；主结果是 fallback，不是约束最优。
- 无外部跨模型 reviewer；审计状态 `WARN` / `PROVISIONAL_LOCAL_AUDIT`，不是 `pass`。
- 只覆盖 T 弯 301 条环氧酚醛；不外推到 MEK/水煮或新系列。
