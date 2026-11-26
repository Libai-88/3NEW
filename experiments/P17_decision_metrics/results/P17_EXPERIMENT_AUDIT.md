# P17 实验审计：决策指标转型

**日期**：2026-11-26  
**审计对象**：`experiments/P17_decision_metrics/`  
**审计方式**：本地确定性检查 + 代码路径核对  
**外部 reviewer**：`REVIEW_UNAVAILABLE`（当前环境无可用的跨模型 reviewer）  
**总体判定**：`WARN`  
**Integrity status**：`warn` — 没有发现伪造 GT、分数归一化或幽灵结果；但缺少外部 reviewer，成本权重是示例口径，不能升级为 `pass`。

## A. Ground Truth Provenance：PASS

- `y` 来自 `合并版数据集.xlsx` 的 T 弯实测标签，经 `p09.build_targets` 和 `grade_from_cuts` 生成；不是模型输出，也不是预测反写。
- 代码证据：`scripts/p17_decision_metrics.py:78-92`。
- 标签分布 `33 / 197 / 71`，`n=301`，与计划一致。
- 评估类型：`real_gt`。

## B. Score Normalization：PASS

- 所有指标使用原始 QWK、MAE、false release、operational cost；没有把指标除以模型自身最大值/均值。
- 代码证据：`scripts/p17_decision_metrics.py:163-224`。
- `operational_cost` 是预注册相对成本，不是归一化分数；报告已标注“示例权重”。

## C. Result File Existence：PASS

所有报告引用的结果文件存在，关键数字与文件一致：

| 引用 | 文件 | 值 | 状态 |
|---|---|---|---|
| `full8` C1 cost delta | `results/p17_claim_check_full.json:3-17` | `−0.037209` | verified |
| `full8` C1 false-release relative | 同上 | `−82.89%` | verified |
| `full8` C2 high recall | `results/p17_claim_check_full.json:18-33` | `0.707042` | verified |
| `full8` C2 QWK | 同上 | `0.629674` | verified |
| `full8` C2 false release | 同上 | `0.149296` | verified |
| `p14_190` C1/C2 | `results/p17_claim_check_full.json:35-63` | 同文件 | verified |

审计脚本同时做了交叉核对：`p17_policy_summary_full.csv` 的 `selective` 行与 claim JSON 的 C2 数值一致；`argmax` QWK 与 P16/P14 报告一致（`0.566778` / `0.579690`）。

## D. Dead Code Detection：PASS

- `policy_predict`、`decision_metrics`、`policy_table`、`risk_curves`、`claim_check` 均在 `main()` 路径被调用（`scripts/p17_decision_metrics.py:404-470`）。
- `high_grade_recall_accepted` 与 `high_test_rate` 已写入 `p17_policy_per_seed_full.csv` 和 summary；不是只定义不调用。
- `p17_config_full.json` 写出实际阈值和成本权重。

## E. Scope Assessment：WARN

- 实际范围：301 条 T 弯环氧酚醛标签、10 seeds × 5 outer × 2 systems；只覆盖 T 弯，不覆盖 MEK/水煮。
- 没有使用 “comprehensive / extensive / robust” 这类超范围措辞；报告明确写了边界。
- WARN 原因：301 条、低档仅 33 条，false reject 的方差大；10 seeds 是重复交叉验证，不是独立外部验证。

## F. Evaluation Type：real_gt

- 数据集实测标签；无 synthetic proxy、无模型生成 reference、无 simulation-only。
- 结论不能外推到 MEK/水煮或新系列。

## 数据一致性检查

| 检查 | 结果 |
|---|---|
| OOF 总行数 | 6020 = 2 systems × 10 seeds × 301 |
| system/seed 单元 | 20 个，每单元恰好 301 行 |
| 标签分布 | `[33, 197, 71]` |
| 概率和最大偏差 | `1.0e-10` |
| `full8` argmax QWK | `0.566778 ± 0.026883`，与 P16 一致 |
| `p14_190` argmax QWK | `0.579690 ± 0.022514`，与 P14 一致 |
| tracker 状态 | R001–R006 全部 DONE |
| 外部 reviewer | 不可用；`REVIEW_UNAVAILABLE` |

## Claim 审计

| Claim | 结果支持什么 | 结果不支持什么 | 判定 |
|---|---|---|---|
| C1 风险闸门降低决策代价 | false release 大幅下降（−82.9%），test 21.4%，high recall +6.2 pp；cost 方向为负（−0.0372） | cost 幅度未过 ≥0.10；pred high `39.40%` 略超 anti-claim 上限；false reject/high precision 变差 | **not supported（严格门槛）** |
| C2 选择性预测降风险 | coverage 81.2%，false release −30.3%，QWK +0.063；接受样本 high recall +3.9 pp | 全体 high recall −7.9 pp，超过 ≤0.05；`p14_190` false release 降幅仅 26.8% | **not supported（严格门槛）** |
| Anti-claim 改善只来自多判高/多复测 | `selective` pred high 26.45%、precision +5.7 pp，anti-claim PASS | `three_way` pred high 39.40%、precision −6.6 pp，anti-claim FAIL | **mixed；`three_way` 不满足** |

**结论**：P17 支持“决策指标转型可行、风险可以被显式交易”，不支持“存在免费提升”或“C1/C2 已通过”。报告必须保留 `pass=false`，不能把 `three_way` 的 false release 降幅单独包装成成功。

## 限制

1. 无外部跨模型 reviewer；本审计是 `PROVISIONAL_LOCAL_AUDIT`。
2. 成本权重（false release 10 / false reject 3 / test 1）是示例相对权重，不是客户确认金额；换权重会改变最优策略。
3. 阈值固定、未在测试折上调参；C1/C2 是预注册判定，不是 post-hoc 最优。
4. 只覆盖 T 弯；MEK/水煮未做。
5. OOF 概率不是生产环境概率；未做校准和漂移监测。

## 证据文件

- `scripts/p17_decision_metrics.py`
- `results/p17_oof_proba_full.csv`
- `results/p17_policy_per_seed_full.csv`
- `results/p17_policy_summary_full.csv`
- `results/p17_policy_delta_full.csv`
- `results/p17_risk_coverage_full.csv`
- `results/p17_claim_check_full.json`
- `results/p17_config_full.json`
- `results/P17_EXPERIMENT_AUDIT.json`
- `logs/p17_sanity.log`
- `logs/p17_full.log`
