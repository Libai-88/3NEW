# P15/P16 远程归档说明

**分支**：`experiment/p14-best`

**本地基线提交**：`1b2fcb0`（P16 报告 + 远程归档说明）

**远程基线**：P14 归档提交 `406dc14`；P15/P16 在其后追加

**更新日期**：2026-11-25

## 这个分支现在有什么

- `experiments/P14_evidence_chain/`：P14 证据链与 190 维固定集归档。
- `experiments/P15_feature_robustness/`：P15-A 残差化探索（1 seed）+ P15-B 嵌套子集/C 选择（10 seeds）。
- `experiments/P16_ftir_block_weight/`：P16 FTIR 块权重 + row-shuffled placebo（10 seeds）。
- `experiments/AUDIT_2026-11-25/`：P0–P14 证据审计报告（5 PASS / 6 WARN / 0 FAIL，PROVISIONAL_LOCAL_AUDIT）。
- `refine-logs/`：P15/P16 计划与 tracker。
- `README.md`、`experiments/README.md`：实验索引与结论摘要。

## 关键结论

- P15-B：嵌套子集+C 选择 QWK `0.571704 ± 0.023059`；P14 190 fixed 高 `0.007986`（p `0.090259`，3/10 seeds 正）；190 只被 14% 外层折选中，不能称稳定最优。
- P16 C1 **PASS**：`full8 − placebo8` `+0.035665`，t p `0.0036`，Holm p `0.0072`，9/10 seeds 正；FTIR8 有真实样品特异信号。
- P16 C2 **FAIL**：`ftir8_w − full8` `−0.009151`，p `0.1035`，4/10 seeds 正；整块标量权重不能替代子集选择。
- P16 `core4_w` QWK `0.571499 ± 0.013461`，仅探索性；`core4` 是 P14 历史子集，`w=4.0` 在 34% 折贴边。

## 不在远程的内容

以下大文件保留本地，远程不重复上传：

| 文件 | 大小 | SHA256 |
|---|---:|---|
| `合并版数据集.xlsx` | — | `753afe8e97a77d1f39d4f852857da5cc204f28c445d3fbfcb3ddf7ff2d67f3f9` |
| `experiments/P10_ftir_v3/data/feature_matrix_v2_fix_reduced.csv` | 692K | `2ff16efb81a94234114dcb6e043335a0810f75d7e8fa6c48c719a30f654ec654` |
| `experiments/P13_feature_opt/data/feature_matrix_p13_t_ftir7.csv` | 552K | `5855a8e678f7345511c2606efb1d0519cd1b9675f31cdd8e6ba07001dec539cd` |
| `experiments/P13_feature_opt/data/feature_matrix_p13_t_ftir8.csv` | 556K | 见 `experiments/P16_ftir_block_weight/results/p16_full_config.json` |
| `experiments/P14_evidence_chain/data/p14_t_target.csv` | 8K | 见 P14 README |

复现时优先使用本地完整仓库；远程归档负责审阅、diff 和结果核对。

## 可复现入口

- P15：`experiments/P15_feature_robustness/scripts/run_p15.sh`
- P16：`experiments/P16_ftir_block_weight/scripts/run_p16.sh`
- 审计：`experiments/AUDIT_2026-11-25/scripts/audit_claims.py`

## 审批边界

- 本归档只包含 P14–P16 的文本与代码；不含原始 Excel、大矩阵和谱图二进制。
- P16 C1/C2 判定按 `refine-logs/P16_EXPERIMENT_PLAN.md` 预注册门槛执行，未做事后改门槛。
- 外部 reviewer 不可用；审计状态为 `PROVISIONAL_LOCAL_AUDIT`，不能声称为跨模型 acquit。
