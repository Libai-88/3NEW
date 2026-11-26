# P17 实验计划：T 弯决策指标转型（选择性预测与风险闸门）

**日期**：2026-11-26  
**状态**：计划完成，准备执行  
**约束**：短期无新数据；不改原始数据、不改切点、不新增特征、不重训新模型族。只把已冻结模型的 OOF 概率转成**决策指标**。  
**Skills used**：`experiment-plan`（claim→evidence→run order）、`experiment-audit`（anti-claim / 证据边界）、`run-experiment`（sanity→full）。

## 1. 问题

当前 T 弯主指标是 QWK（0.57 左右），但它回答的是“排序/分级一致性”，不是“这批配方能不能放行、要不要复测”。用户已确认：短期内没有新数据，但评价指标转成决策指标可行。P17 因此不改特征/模型，只回答：

1. 同样的 OOF 概率，换成**风险闸门**（高风险直接判高等级，低风险放行，中间复测）后，能不能在不大量增加复测的前提下降低“坏货被放行”的概率？
2. 同样的 OOF 概率，换成**选择性预测**（低置信样本转人工复测）后，覆盖率和风险如何权衡？

## 2. Claim Map

| Claim | Why It Matters | Minimum Convincing Evidence | Linked Blocks |
|---|---|---|---|
| C1：风险闸门优于 argmax 的决策代价 | QWK 不直接对应放行/复测成本 | `three_way` 相对 argmax 的 operational decision cost 下降 ≥ **0.10**（相对单位/样本），false-release rate 相对下降 ≥ **30%**，test rate ≤ **0.35**；10 seeds paired p<0.05，≥7/10 seeds 改善 | B1 |
| C2：选择性预测可在可接受覆盖率下降低 false release | 低置信样本应转复测，而不是硬猜 | `selective τ=0.60` 相对 argmax：coverage ≥ **0.70**，false-release rate 相对下降 ≥ **30%**，high-grade recall 下降 ≤ **0.05**；QWK 下降 ≤ **0.05** | B2 |
| Anti-claim：改善只来自“多判高等级/多复测” | 防止用保守预测刷风险指标 | `pred_high_rate` 不超过真实高等级率 + **0.15**；test rate 不超过 **0.35**；且 `high_precision` 下降 ≤ **0.05** | B1, B2 |

**最多 2 个主 claim**；anti-claim 只用于排除“靠多判 high / 多 abstain 刷指标”。

## 3. 数据与系统

- 数据：`合并版数据集.xlsx`；T 弯 301 条环氧酚醛；三类 33 / 197 / 71；切点 `[15,20]`。
- 分组：`formula_id`；外层 `StratifiedGroupKFold(5)`，10 seeds。
- 冻结系统：
  1. `full8`：P16 的 183 + 8 FTIR 块，`w=1`；C 在训练折内 nested；这是 P16 的预注册主系统。
  2. `p14_190`：P14 的 190 维固定集，C=2；**post-hoc 固定集参考**，只作描述性对照。
- OOF 概率全部由外层测试折产生；决策阈值预注册、固定，不在测试折上调参。
- 不新增数据、不伪造膜厚/烘烤曲线/差谱。

## 4. 决策策略（全部固定阈值，预注册）

| 策略 | 规则 | 说明 |
|---|---|---|
| `argmax` | `argmax p` | 现行基线 |
| `cost` | `argmin (p @ C_grade)` | 现有非对称等级代价，`C_grade` 由 `p09.cost_matrix(3)` 固定 |
| `high_guard` | 若 `p(high) ≥ 0.35` 判 high；否则在 low/mid 内 argmax | 风险闸门，不 abstain |
| `three_way` | `p(high) ≥ 0.35` 判 high；`p(high) ≤ 0.10` 在 low/mid 内 argmax；中间 abstain | 主策略：放行 / 直接判高 / 复测 |
| `selective` | `max(p) < 0.60` abstain；否则 argmax | 低置信转复测 |
| `cost_abstain` | `min(p @ C_grade) > 1.0` abstain；否则 argmin | 决策代价超过一次复测成本就复测 |

**Operational cost**（相对单位/样本，预注册）：

- 正确放行：0
- 正确判高：0
- 复测：1
- 误判高（false reject）：3
- 坏货放行（false release）：10

该成本是**相对权重**，不是客户确认的金额；报告中必须标注“示例成本口径”。同时保留 `p09.cost_matrix` 的等级代价作为第二口径。

## 5. 指标

主指标：

- `operational_cost`（越低越好）
- `false_release_rate`（真实 high 中被判 low/mid 且未复测的比例）
- `test_rate`（复测比例）
- `high_grade_recall`（真实 high 中被直接判 high 的比例；abstain 不算命中）
- `high_precision`、`pred_high_rate`
- `coverage`（selective 接受预测的比例）

次指标：

- QWK（accepted 子集；abstain 策略只对接受样本算）
- MAE、severe overprediction、等级代价 `mean_cost_over2`
- 风险-覆盖率曲线（selective τ 0.40–0.80；high_guard T 0.20–0.60）

## 6. 运行顺序

| Milestone | Goal | Runs | Gate |
|---|---|---|---|
| M0 sanity | 1 seed，检查 OOF 形状、概率和、策略输出 | 1 seed × 2 systems | 无 NaN；概率和为 1；policy 分布合理 |
| M1 full | 10 seeds，生成 OOF 概率 | `full8` 10 seeds + `p14_190` 10 seeds | 每 seed 301 条 OOF；QWK 与 P16/P14 报告同量级 |
| M2 analysis | 策略指标、paired test、风险-覆盖曲线 | 不重训 | C1/C2 判定 |

## 7. 预期成本

- `full8`：10 seeds × 5 outer × 4 C × 3 inner × 2 thresholds ≈ 1,200 次 Logistic 拟合。
- `p14_190`：10 seeds × 5 outer × 2 thresholds = 100 次拟合。
- 2 vCPU / 3.9 GiB 下预计 6–12 分钟；无 GPU。

## 8. 失败解释

- 若 `three_way` 的 false release 下降但 test rate >0.35：说明安全收益靠大量复测换来，不能作为“免费提升”。
- 若 `selective` 的 coverage <0.70：说明当前模型置信度不足以支撑选择性放行。
- 若两个系统结论相反：只报告系统特定结论，不外推。
- 若 QWK 下降 >0.05 且决策代价不降：决策转型不成立，保留 QWK 作为主指标。
- `p14_190` 是 post-hoc 固定集，不得用它单独证明策略优于 `full8`。

## 9. 交付物

- `results/p17_oof_proba.csv`
- `results/p17_policy_per_seed.csv`
- `results/p17_policy_summary.csv`
- `results/p17_policy_delta.csv`
- `results/p17_risk_coverage.csv`
- `results/P17_实验报告.md`
- `logs/p17_full.log`
- `refine-logs/P17_EXPERIMENT_TRACKER.md`
