# P13 数据目录

## 最终使用

- `feature_matrix_p13_t_ftir7.csv` — 345×191 文件（`sample_id` + 190 特征）；T 建模使用 301 行、190 维，是 P14 最终矩阵。
- `feature_dictionary_p13_ftir7.csv` — 7 个最终 FTIR 特征定义（`ftir_oh_epox` 已去掉）。
- `feature_matrix_p13_aug.csv`、`feature_matrix_p13_spectra.csv` — P13 诊断候选，不进入最终模型。

## 历史对照

- `feature_matrix_p13_t_ftir8.csv` — 345×191（`sample_id` + 191 特征，含 `ftir_oh_epox`），P13 的 3-seed 初筛矩阵；已被 P14 的 190 维方案修订，不再作为最终 T 矩阵。
- `feature_dictionary_p13_ftir8.csv` — 8 个历史 FTIR 特征定义。

矩阵只由 P10 的 183 维和 7 个原料 FTIR 特征拼接，不包含标签、不做目标编码；缺失值由下游训练折内 median imputer 处理。

> Remote branch note: the large `feature_matrix_p13_t_ftir7.csv` is not committed here; see `../../P14_evidence_chain/REMOTE_DATA.md` and the SHA256 manifest.
