# P17 — T 弯决策指标转型（风险闸门与选择性预测）

**状态**：10 seeds full 完成；C1/C2 均按预注册门槛 `pass=false`。  
**报告**：[`results/P17_实验报告.md`](results/P17_实验报告.md)  
**计划**：[`../../refine-logs/P17_EXPERIMENT_PLAN.md`](../../refine-logs/P17_EXPERIMENT_PLAN.md)  
**Tracker**：[`../../refine-logs/P17_EXPERIMENT_TRACKER.md`](../../refine-logs/P17_EXPERIMENT_TRACKER.md)

## 目标

在短期没有新数据的前提下，不改特征、不改模型族，只把 P16 `full8` 和 P14 `p14_190` 的 OOF 概率转成决策指标，检验：

1. 风险闸门（`three_way`）能否在不大量增加复测的前提下降低 false release；
2. 选择性预测（`selective τ=0.60`）能否在可接受覆盖率下降风险；
3. 现有等级代价矩阵（`cost`）是否与 false release 风险对齐。

## 输入与冻结系统

- 数据：`合并版数据集.xlsx`，T 弯 301 条环氧酚醛，切点 `[15,20]`，三类 `33 / 197 / 71`。
- 分组：`formula_id`；外层 `StratifiedGroupKFold(5)`；10 seeds。
- `full8`：P16 的 183 + 8 FTIR，`w=1`，C 在训练折内 nested；主系统。
- `p14_190`：P14 固定 190 维，C=2；post-hoc 描述性参考。

## 策略（固定阈值，预注册）

`argmax`、`cost`、`high_guard`、`three_way`、`selective`、`cost_abstain`。  
`three_way`：`p(high)≥0.35` 判 high；`p(high)≤0.10` 放行 low/mid；中间 abstain。  
`selective`：`max(p)<0.60` abstain，否则 argmax。

## 关键结果（full8，10 seeds）

| 策略 | false release | test rate | 全体 high recall | 接受样本 high recall | QWK | operational cost |
|---|---:|---:|---:|---:|---:|---:|
| `argmax` | 21.41% | 0.0% | 78.59% | 78.59% | 0.5668 | 0.9196 |
| `three_way` | **3.66%** | 21.40% | 84.79% | **95.87%** | 0.5908 | 0.8824 |
| `selective τ=.60` | 14.93% | 18.84% | 70.70% | 82.53% | **0.6297** | **0.8336** |

- C1 FAIL：false release 相对下降 `82.9%`，但 cost 只降 `0.0372`，未过 ≥0.10；pred high `39.40%` 略超 anti-claim 上限 `38.59%`。
- C2 FAIL：coverage `81.16%`、false release `−30.26%`、QWK `+0.0629` 均达标；全体 high recall `−7.89 pp` 超限。接受样本 high recall `+3.94 pp`、high test rate `14.37%` 仅为补充口径。
- `cost` 策略 false release 升到 `37.32%`、cost `1.0738`，与风险目标不一致，不推荐。

## 复现

```bash
tooling/run.sh python3 experiments/P17_decision_metrics/scripts/p17_decision_metrics.py \
  --mode sanity --seeds 42 --systems full8 p14_190 --tag sanity

tooling/run.sh python3 experiments/P17_decision_metrics/scripts/p17_decision_metrics.py \
  --mode full --seeds 42 202 777 1234 2026 31415 2718 1618 5678 9999 \
  --systems full8 p14_190 --tag full
```

## 输出

`results/p17_oof_proba_full.csv`、`p17_policy_per_seed_full.csv`、`p17_policy_summary_full.csv`、`p17_policy_delta_full.csv`、`p17_risk_coverage_full.csv`、`p17_claim_check_full.json`、`p17_config_full.json`。  
日志：`logs/p17_sanity.log`、`logs/p17_full.log`。

## 边界

- 示例成本权重 `false release 10 / false reject 3 / test 1` 是相对口径，不是客户确认金额。
- 阈值未在测试折上调参；C1/C2 是预注册判定，不是 post-hoc 最优。
- 只覆盖 T 弯；MEK/水煮未做。
- 无外部 reviewer；审计状态 `PROVISIONAL_LOCAL_AUDIT`。
