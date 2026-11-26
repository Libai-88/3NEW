# P18 实验审计：嵌套校准决策策略

**日期**：2026-11-26  
**审计对象**：`experiments/P18_nested_decision_policy/`  
**审计方式**：本地确定性检查 + 代码路径核对  
**外部 reviewer**：`REVIEW_UNAVAILABLE`（当前环境无可用的跨模型 reviewer）  
**总体判定**：`WARN`  
**Integrity status**：`warn` — 未发现伪造 GT、分数归一化或幽灵结果；但存在“内层约束多数无可行解、阈值实际为 fallback”的方法学限制，且无外部 reviewer，不能升级为 `pass`。

## A. Ground Truth Provenance：PASS

- `y` 来自 `合并版数据集.xlsx` 的 T 弯实测标签，经 P17 的 `load_data()` 复用 `p09.build_targets` 与 `grade_from_cuts` 生成；不是模型输出，也不是预测反写。
- 代码证据：`scripts/p18_nested_decision.py:321-343`。
- 标签分布 `33 / 197 / 71`，`n=301`，与计划一致。
- 评估类型：`real_gt`。

## B. Score Normalization：PASS

- 所有指标使用原始 QWK、MAE、false release、false reject、test rate、operational cost；没有把指标除以模型自身最大值/均值。
- `operational_cost` 是预注册相对成本，不是归一化分数；报告已标注“示例权重”。
- 代码证据：`scripts/p18_nested_decision.py:163-221`。

## C. Result File Existence：PASS

所有报告引用的结果文件存在，关键数字与文件一致：

| 引用 | 文件 | 值 | 状态 |
|---|---|---|---|
| C1 FR / test / cost | `results/p18_claim_check_full.json` | `0.046479 / 0.221595 / -0.092691` | verified |
| C1 seed gate | 同上 | `3` | verified |
| C2 FR 相对 / high recall | 同上 | `0.225166 / 0.735211` | verified |
| C2 seed gate | 同上 | `1` | verified |
| 主表 P18 three_way | `results/p18_policy_summary_full.csv` | 与 claim JSON 一致 | verified |
| 校准 NLL/ECE | `results/p18_calibration_full.csv` | `1.464→0.961` / `0.145→0.089` | verified |
| 阈值可行折 | `results/p18_thresholds_full.csv` | 11/50、0/50 | verified |

审计同时做了数据一致性检查：

| 检查 | 结果 |
|---|---|
| OOF 总行数 | 3010 = 10 seeds × 301 |
| 每 seed 行数 | 301；sample_id 唯一 301 |
| 标签分布 | `[33, 197, 71]` |
| 概率和最大偏差 | `1.0e-10` |
| 逐 seed 表 | 470 = 47 arms × 10 seeds |
| 汇总表 | 47 arms |
| 阈值日志 | 2200 = 44 nested arms × 50 folds |
| 校准表 | 50 = 10 seeds × 5 folds |
| C1 argmax QWK | `0.5740 ± 0.0246` |
| C1 P18 QWK | `0.6070 ± 0.0241` |

## D. Dead Code Detection：PASS

- `temp_scale`、`nll`、`ece`、`fit_temperature`、`apply_policy`、`selection_metrics`、`final_metrics`、`select_thresholds`、`run_seed`、`summarize`、`paired_deltas`、`claim_check` 均在 `main()` 路径被调用。
- `n_candidates` / `n_feasible` / `base_inner_*` 写入 `p18_thresholds_full.csv`，不是只定义不调用。
- 已删除未使用的 `arm_label` 和未使用的 `qwk_d` 变量。

## E. Scope Assessment：WARN

- 实际范围：301 条 T 弯环氧酚醛标签、10 seeds × 5 outer × 5 inner 折；只覆盖 T 弯，不覆盖 MEK/水煮。
- 没有使用 “comprehensive / extensive / robust” 等超范围措辞；报告明确写了边界。
- WARN 原因：
  1. 内层 OOF 仅约 240 条，低档约 26 条；阈值选择方差大；
  2. `three_way` 主设置只有 11/50 折有可行阈值，`selective` 0/50；主结果是 fallback，不是约束最优；
  3. 无外部 reviewer；不能声称跨模型 acquit；
  4. 301 条不是独立外部验证，10 seeds 是重复交叉验证。

## F. Evaluation Type：real_gt

- 数据集实测标签；无 synthetic proxy、无模型生成 reference、无 simulation-only。
- 结论不能外推到 MEK/水煮、新系列或生产批次。

## 阈值来源检查

- 外层分组：`p9.make_splits(y, groups, seed, n_splits=5)`；断言 `groups[tr]` 与 `groups[te]` 无交集（`scripts/p18_nested_decision.py:336-337`）。
- 内层分组：在 `tr` 内用 `p9.make_splits(ytr, gtr, seed + 1000 + 37*fi, n_splits=4)`；断言无交集（`:348-349`）。
- 外层概率：只用 `tr` 训练、`te` 预测（`:339-340`）。
- 温度 T：只用 `inner_raw` 与 `ytr` 拟合（`:356-358`）；外层只应用。
- 阈值：`select_thresholds(ytr, source, ...)` 只传内层 OOF 与内层标签（`:378`）；外层 `y[te]` 只在决策完成后计算指标（`:413-424`）。
- 结论：外层测试未参与阈值选择或校准拟合。

## Claim 审计

| Claim | 结果支持什么 | 结果不支持什么 | 判定 |
|---|---|---|---|
| C1 嵌套 `three_way` 稳定可部署 | 10-seed 均值 FR 4.65%、test 22.16%、high recall −0.42 pp、cost −0.0927、pred high 34.58% | seed gate 3/10；4 seeds FR >5%；4 seeds precision 掉 >5 pp；39/50 折无可行阈值 | **not supported（严格门槛）** |
| C2 嵌套 `selective` FR 相对 −30% 且 high recall/QWK 不降 | coverage 87.01%、QWK +0.035 | FR 相对仅 −22.52%；high recall −5.21 pp；seed gate 1/10；0/50 折可行 | **not supported（严格门槛）** |
| Anti-claim：改善来自更多判高/复测 | P18 three_way pred high 34.58%、precision 降 4.49 pp；test 22.16% | 但 FR 4.65%、4 seeds >5%，且 fallback 不是约束最优 | **partial；不能包装为成功** |

**结论**：P18 支持“嵌套阈值 + 温度校准在均值层面接近 C1 的风险分布”，但不支持“存在稳定可部署策略”。报告必须保留 `pass=false`，不能把均值达标写成 C1 通过。

## 限制

1. 无外部跨模型 reviewer；本审计是 `PROVISIONAL_LOCAL_AUDIT`。
2. 成本权重 `10/3/1` 是示例相对权重；Block 2 已做敏感性，但 cap 25% 下成本权重不改变决策。
3. 内层 OOF 小，阈值选择多数折无可行解；主结果是 fallback，不是约束最优。
4. 只覆盖 T 弯；MEK/水煮未做。
5. OOF 概率不是生产环境概率；未做生产漂移监测。

## 证据文件

- `scripts/p18_nested_decision.py`
- `results/p18_oof_proba_full.csv`
- `results/p18_policy_per_seed_full.csv`
- `results/p18_policy_summary_full.csv`
- `results/p18_policy_delta_full.csv`
- `results/p18_cost_sensitivity_full.csv`
- `results/p18_thresholds_full.csv`
- `results/p18_calibration_full.csv`
- `results/p18_claim_check_full.json`
- `results/p18_config_full.json`
- `logs/p18_sanity.log`
- `logs/p18_full.log`
