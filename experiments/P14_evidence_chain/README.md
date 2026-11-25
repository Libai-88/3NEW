# P14 证据链实验

## 目标

P14 是对 P13 的 T=191（183+FTIR8，C=1，3 seeds）证据链的补强与修订。用户要求「证据链补充完善，确保特征优化到位，模型选择最适配且参数最优」，因此本实验只做三件事：

1. 把 T 的 seeds 从 3 扩到 10；
2. 用 nested C 选择避免参数选择泄漏；
3. 补模型族比较、drop-one、FTIR 子集、置换检验和 bootstrap。

P13 的 3-seed 数字作为初筛保留；P14 是最终证据，也是当前最优实验。

## 远程归档边界

本分支保存 P14 的全部脚本、7 张证据汇总表、最终三目标表、模型配置、数据审计和 190 个入选特征名。两个特征矩阵（`feature_matrix_v2_fix_reduced.csv`、`feature_matrix_p13_t_ftir7.csv`）和 `ftir_sample_features_v3.csv` 体积较大，未进入 Git；其本地 SHA256 和绝对路径见 `REMOTE_DATA.md` 与 `data/local_artifact_manifest.json`。克隆本分支后，先按 `REMOTE_DATA.md` 把矩阵放回协议中的相对路径，再运行复现命令。

## 协议

- 数据：`../P10_ftir_v3/data/feature_matrix_v2_fix_reduced.csv`（345×183，主体系）与 `../P13_feature_opt/data/feature_matrix_p13_t_ftir7.csv`（345×190）。
- 目标：T 三级 `≤15 / 15–20 / >20`；T 有效样本 301。
- T 的 `formula_id` 有 301 个唯一值，无重复组；`StratifiedGroupKFold` 在当前数据上等价于分层抽样，但保留该协议以兼容后续重复配方。
- 划分：`StratifiedGroupKFold(5)`，按 `formula_id`；seeds `42, 202, 777, 1234, 2026, 31415, 2718, 1618, 5678, 9999`。
- 指标：QWK、MAE、高档 recall、过度预测率、决策代价。
- 模型：ordinal cumulative logistic；C 网格 `0.1–2.0`；nested C 网格 `0.5/1.0/1.5/2.0`，内层 3-fold grouped CV。
- 预处理：median imputer + missing indicator，StandardScaler；全部在训练折内拟合。

## 结果

### 最终方案

| 目标 | 特征集 | 维度 | 模型/决策 | QWK | 高档 recall | 代价 |
|---|---|---:|---|---:|---:|---:|
| T | 183 + FTIR7 | 190 | ordinal logistic C=2 argmax | 0.5707（nested）/0.5797（fixed） | 0.7901 | 0.6781 / 0.6645 |
| MEK | base183 | 183 | ordinal logistic C=1 + cost-anchor | 0.6424 | 0.7697 | 0.9164 |
| 水煮 | base183 | 183 | ExtraTrees multiclass argmax | 0.4695 | 0.6790 | 0.9476 |

三目标平均 QWK 0.5609（nested）/0.5639（fixed），P12 为 0.5485。

### T 的关键数字

- 10-seed 固定 C：base183 C=2 0.5517；FTIR8 191 C=2 0.5740；FTIR7 190 C=2 0.5797。
- Nested C：base183 0.5451；FTIR7 190 0.5707；delta +0.0256，p=0.0046，9/10 seeds 正，95% seed-level CI [0.0101, 0.0410]。
- 模型族：ordinal logistic C=2 0.5797；ordinal XGBoost 0.4346；multiclass XGBoost 0.4248。
- Drop-one：去 `ftir_meoh_phen` −0.0105；去 `ftir_oh_epox` +0.0057；因此最终去掉 `ftir_oh_epox`。
- 置换：观测 0.5729；零分布 0.5308 ±0.0133；20 次置换 p=0.0476。
- Bootstrap：seed-level delta 95% CI [0.0110, 0.0449]；样本级 group bootstrap 区间较宽 [−0.036, 0.096]。

## 脚本

- `scripts/p14_t_evidence.py` — 10-seed 固定 C 网格与 nested C；`--mode fixed|nested`。
- `scripts/p14_t_models.py` — ordinal logit / ord_xgb / multi_xgb 模型族比较。
- `scripts/p14_t_drop_one.py` — 8 个 FTIR 特征的 drop-one。
- `scripts/p14_t_ftir_subsets.py` — FTIR 子集（full8/7/6/core4/core5）。
- `scripts/p14_t_permutation.py` — FTIR 块置换零假设。
- `scripts/p14_t_bootstrap.py` — 按 formula_id 组 bootstrap。

## 复现

以下命令假定仓库根目录为当前目录，且 `../P10_ftir_v3/data/feature_matrix_v2_fix_reduced.csv` 与 `../P13_feature_opt/data/feature_matrix_p13_t_ftir7.csv` 已按 `REMOTE_DATA.md` 补齐；远程分支不含这两个矩阵。

```bash
cd <repo-root>
tooling/run.sh python3 experiments/P14_evidence_chain/scripts/p14_t_evidence.py --mode fixed --seeds 42 202 777 1234 2026 31415 2718 1618 5678 9999
tooling/run.sh python3 experiments/P14_evidence_chain/scripts/p14_t_evidence.py --mode nested --seeds 42 202 777 1234 2026 31415 2718 1618 5678 9999
tooling/run.sh python3 experiments/P14_evidence_chain/scripts/p14_t_models.py
tooling/run.sh python3 experiments/P14_evidence_chain/scripts/p14_t_drop_one.py
tooling/run.sh python3 experiments/P14_evidence_chain/scripts/p14_t_ftir_subsets.py
tooling/run.sh python3 experiments/P14_evidence_chain/scripts/p14_t_permutation.py
tooling/run.sh python3 experiments/P14_evidence_chain/scripts/p14_t_bootstrap.py
```

## 产物

- `data/p14_data_audit.json`
- `data/p14_t_target.csv`（301 行；本地生成，远程分支未提交，可由 `p14_t_evidence.py` 重建）
- `data/p14_t_selected_features.csv`
- `results/p14_final_summary.csv`
- `results/p14_final_model.json`
- `results/p14_t_fixed_summary.csv`
- `results/p14_t7_nested_summary.csv`
- `results/p14_t_models_summary.csv`
- `results/p14_t_drop_one_summary.csv`
- `results/p14_t_ftir_subsets_summary.csv`
- `results/p14_t_permutation_summary.csv`
- `results/p14_t_bootstrap_summary.csv`
- `results/P14_证据链结论.md`
- `results/P14_最终特征方案.md`

## 状态

- 已完成 10-seed 固定 C、nested C、模型族、drop-one、FTIR 子集、置换、bootstrap。
- 最终 T 采用 190 维（183+FTIR7），C=2；MEK/水煮沿用 P12。
- 未改原始数据、标签切点、分组折；未伪造膜厚/烘烤曲线/固化后差谱。
- T 的 FTIR7 子集是同数据 post-hoc 选择，需外部验证后再上线。
