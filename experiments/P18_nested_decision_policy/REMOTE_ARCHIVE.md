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
- `experiments/P18_nested_decision_policy/results/p18_claim_check_full.json`
- `experiments/P18_nested_decision_policy/results/p18_config_full.json`

## 仅本地保存的文件

以下大文件没有推送到远程；它们是完整证据链的一部分，但远程只保留可复核的汇总、claim、审计与脚本。

| 文件 | 行数/说明 | 大小 | SHA256 |
|---|---:|---:|---|
| `results/p18_policy_summary_full.csv` | 47 arms 汇总 | 20,068 B | `b49b7c0d17ebc9c691c494fa7806332705efc8a1f92ec1a028e6f653d31f2006` |
| `results/p18_policy_delta_full.csv` | primary 对 argmax / P17 fixed 的 paired delta | 5,400 B | `f994e7c023202d1fc1bbaac0176e5fc1fcdec9fe76cdfdae587468b24e8a0a5c` |
| `results/p18_cost_sensitivity_full.csv` | 42 个 temp nested 臂的成本-容量敏感性 | 18,184 B | `7204ace0593dd4329a1f2e57731372cce11ae76acc8e9ae0be74ca8f465f1926` |
| `results/p18_calibration_full.csv` | 50 折 T/NLL/ECE | 3,895 B | `c3be670d3c7bb31a4e655ef5d1324ca18c1ba6ca8ac34a371ccd57745cd38736` |
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
