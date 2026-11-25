# P14 数据与结果说明

## 输入

- `../P10_ftir_v3/data/feature_matrix_v2_fix_reduced.csv` — 345×183 主基准。
- `../P10_ftir_v3/data/ftir_sample_features_v3.csv` — 456×16 原料 FTIR 样本特征。
- `../P13_feature_opt/data/feature_matrix_p13_t_ftir7.csv` — 345×191 文件（`sample_id` + 190 特征，P14 最终 T 矩阵）。
- `../P13_feature_opt/data/feature_matrix_p13_t_ftir8.csv` — 345×191 文件（含 `ftir_oh_epox`，drop-one/历史对照）。

## `data/`

- `p14_data_audit.json` — 主数据 SHA256、301 条 T 样本、类别 33/197/71、190 维形状、7 个 FTIR 缺失计数、301 个唯一 `formula_id`。
- `p14_t_target.csv` — `sample_id`、`group`、`y`，只含 T 有效样本。
- `p14_t_selected_features.csv` — 190 个最终特征名。

## `results/`

- `p14_final_summary.csv` — 最终三目标指标表。
- `p14_final_model.json` — T 的 190 维、C=2、ordinal logistic 配置。
- `p14_t_fixed_*` — 10-seed 固定 C 网格。
- `p14_t_nested_*` — 191 维 nested C（历史对照）。
- `p14_t7_nested_*` — 190 维 nested C（最终）。
- `p14_t_models_*` — 190 维模型族比较。
- `p14_t_drop_one_*` — FTIR drop-one。
- `p14_t_ftir_subsets_*` — FTIR 子集比较。
- `p14_t_permutation_*` — FTIR 块置换。
- `p14_t_bootstrap_*` — 按 `formula_id` 组 bootstrap。

`p14_t_bootstrap_reps.csv` 是 10 seeds × 2000 次重采样的中间表，保留用于复核区间；不用于直接报告单点指标。
