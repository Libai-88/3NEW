# P19 远程归档说明

**远程仓库**：`https://github.com/Libai-88/3NEW`  
**目标分支**：`experiment/p14-best`  
**P19 归档日期**：2026-11-26  
**P19 结论**：C1/C2 均 fail；C3/C4 通过；合成增强不能替代新 T 测量。

## 已进入远程分支的文件

- `experiments/P19_data_layer/README.md`
- `experiments/P19_data_layer/REMOTE_ARCHIVE.md`
- `experiments/P19_data_layer/results/P19_实验报告.md`
- `experiments/P19_data_layer/results/P19_EXPERIMENT_AUDIT.md`
- `experiments/P19_data_layer/results/P19_EXPERIMENT_AUDIT.json`
- `experiments/P19_data_layer/results/P19_CLAIMS_FROM_RESULTS.md`
- `experiments/P19_data_layer/results/P19_LITERATURE_NOTES.md`
- `experiments/P19_data_layer/results/p19_claim_check_full.json`
- `experiments/P19_data_layer/results/p19_config_full.json`
- `experiments/P19_data_layer/results/p19_data_audit_full.json`
- `experiments/P19_data_layer/results/p19_summary_full.csv`
- `experiments/P19_data_layer/results/p19_delta_full.csv`

## 仅本地保存的文件

以下大文件 / 代码 / 逐 seed 表没有推送到远程；远程保留可复核的汇总、claim、审计、文献记录与报告，完整证据链留在本地提交 `f126086` / `b3e41b6`。

| 文件 | 大小 | SHA256 |
|---|---:|---|
| `scripts/p19_data_layer.py` | 27 KB | 本地提交 |
| `refine-logs/P19_EXPERIMENT_PLAN.md` | 13,743 B | 本地提交 |
| `refine-logs/P19_EXPERIMENT_TRACKER.md` | 2,422 B | 本地提交 |
| `results/p19_augmentation_audit_full.csv` | 18,277 B | `c61896b25c63541e70275bec7391764bf665c088a239ccbb72cfa7589022ca57` |
| `results/p19_augmentation_audit_sanity.csv` | 1,892 B | `efb39c3546dd62bc208b633e4fd8db6b72281e8388e48b37abb3f9860d4ee145` |
| `results/p19_claim_check_sanity.json` | 2,967 B | `ffeff67b2b4761f94006c5c797ccc4f46b22103c2b6bb6cc9d7f3a1e58f0ff7e` |
| `results/p19_config_sanity.json` | 696 B | `3d4611ccb46a35bdd8249498e36cd3755c00e28fda9b7e12b2b9bfcf20893487` |
| `results/p19_data_audit_full.csv` | 278 B | `3e27880da1100e2921bb233b25163930a568ab1eb9a7b7178d45ffe485744bd7` |
| `results/p19_delta_sanity.csv` | 639 B | `f9ad6ec17d9f7657ae97d2e431724a23b4078b8b97e34a9427aa7e91198a7f66` |
| `results/p19_label_noise_simulation_full.csv` | 214 B | `6dfc1ece39286c3d38b4a0f5cb339cef1a09100be3f620214e9d928d50e6228b` |
| `results/p19_oof_proba_full.csv` | 1,570,731 B | `25793aece35b259f4e4a293939369818c059b1ffc08fb13c2b90c1efe743b7a7` |
| `results/p19_oof_proba_sanity.csv` | 152,978 B | `0b82441438911403bc1ca6fc449a714350538e63c0d3a988f803bb9b5eab76f7` |
| `results/p19_per_seed_full.csv` | 14,884 B | `9f3b2689c7ea4a224057f1417b19b96234fecc22dfb2b7c4dc5deff39a208cfa` |
| `results/p19_per_seed_sanity.csv` | 1,686 B | `157b1bdadffac9eb3202f5c48f5b73800a607ca44b74ac328f619343134c35f6` |
| `results/p19_summary_sanity.csv` | 1,514 B | `96912896d291095861db3e0aa6b22aa9a743f4d47ac7afdea40dae43b00335b7` |
| `logs/p19_full.log` | 3,554 B | `6b249403a4889d26601cde7f50ca8a42274bd5fc0c119f8cf36e4c9110480b3a` |
| `logs/p19_sanity.log` | 2,799 B | `a5a1153d08bf57944ef1e800f1c04c079389f7cf570acbca3f799853664a3fae` |

sanity 版工件（`p19_*_sanity.csv/json`）与完整 OOF/逐 seed 表同样留在本地，未推送。

## 复现命令

```bash
tooling/run.sh python3 experiments/P19_data_layer/scripts/p19_data_layer.py \
  --mode sanity --tag sanity

tooling/run.sh python3 experiments/P19_data_layer/scripts/p19_data_layer.py \
  --mode full --seeds 42 202 777 1234 2026 31415 2718 1618 5678 9999 --tag full
```

## 边界

- P19 是负结果；不能把 `cure_meta` 或 `boundary_w50` 的方向性信号写成通过。
- 合成样本只在训练折内生成，测试折合成行数为 0；评估只使用 301 条实测 T。
- 外部跨模型 reviewer 不可用；claim 状态 `REVIEW_UNAVAILABLE`，本地审计 `WARN` / `PROVISIONAL_LOCAL_AUDIT`。
- 只覆盖 T 弯 301 条环氧酚醛；不外推到 MEK/水煮或新系列。
