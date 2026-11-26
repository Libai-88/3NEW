# P20 远程归档说明

**远程仓库**：`https://github.com/Libai-88/3NEW`  
**目标分支**：`experiment/p14-best`  
**P20 归档日期**：2026-11-26  
**P20 结论**：C1/C2 fail；C3/C4 通过（C4 为代码检查 + 负约束）；stacked 辅助概率没有提升 T 弯。

## 已进入远程分支的文件

- `experiments/P20_aux_target_transfer/README.md`
- `experiments/P20_aux_target_transfer/REMOTE_ARCHIVE.md`
- `experiments/P20_aux_target_transfer/results/P20_实验报告.md`
- `experiments/P20_aux_target_transfer/results/P20_EXPERIMENT_AUDIT.md`
- `experiments/P20_aux_target_transfer/results/P20_EXPERIMENT_AUDIT.json`
- `experiments/P20_aux_target_transfer/results/P20_CLAIMS_FROM_RESULTS.md`
- `experiments/P20_aux_target_transfer/results/p20_summary_full.csv`
- `experiments/P20_aux_target_transfer/results/p20_delta_full.csv`
- `experiments/P20_aux_target_transfer/results/p20_specificity_full.csv`
- `experiments/P20_aux_target_transfer/results/p20_claim_check_full.json`
- `experiments/P20_aux_target_transfer/results/p20_config_full.json`

## 仅本地保存的文件

以下文件没有推送到远程；远程保留可复核的报告、审计、claim 和紧凑结果表，完整证据链与代码留在本地提交。原因：GitHub connector 的单次写入需要逐个文件传内容，1.19 MB OOF、逐 seed 表和 23.6 KB 脚本不适合作为 connector 文本 payload；本地 commit 保留完整可复现链。

| 文件 | 大小 | SHA256 |
|---|---:|---|
| `scripts/p20_aux_transfer.py` | 23,632 B | 本地提交 |
| `results/p20_per_seed_full.csv` | 10,583 B | `aa8274405c5416c564309bf9924f17b6d10e233e4dc49987abecce1b32b13c6e` |
| `results/p20_oof_proba_full.csv` | 1,189,176 B | `b4106bc70622066b2ddaa4ee22ae8345f26a9528a6071c2dbfb3809d31454d60` |
| `results/p20_aux_audit_full.csv` | 18,834 B | `0cb9772df92a90b9fc8030bcd9db8e0444a836bf72ec3fd2332934691a09022d` |
| `logs/p20_full.log` | 2,803 B | `ba4c052c4e15b401c56c0fb710ed479b6f40806e91e9c726d995ee854999ab3b` |
| `logs/p20_sanity.log` | 2,383 B | `05de24de5727543067d0986b7fe62e0e39bb6f05474ccfadea01a47fd22d5cce` |
| `results/p20_oof_proba_sanity.csv` | local | `6a805016f7897caac4166ccffdc83e68cd3ad1716da652870f8d81ab1979790e` |
| `results/p20_per_seed_sanity.csv` | local | `84ce1b273fe0767ab4445eefa512fef40433e641f49b54caf08e43fc42dff231` |
| `results/p20_aux_audit_sanity.csv` | local | `dce9380df487990472d139e34d2c57bb101eb6718afea44eac6cb16a1f6ddf84` |

sanity 版工件（`p20_*_sanity.csv/json`）与完整 OOF/逐 seed 表同样留在本地，未推送。

## 复现命令

```bash
cd /home/user/3new-refactor
python3 experiments/P20_aux_target_transfer/scripts/p20_aux_transfer.py --mode sanity --tag sanity
python3 experiments/P20_aux_target_transfer/scripts/p20_aux_transfer.py \
  --mode full --seeds 42 202 777 1234 2026 31415 2718 1618 5678 9999 --tag full
```

## 边界

- P20 是负结果；不能把 `aux_both` 比 `aux_both_shuffle` 高 `+0.009348` 写成 C2 成功。
- 测试折不使用辅助 GT；`n_aux_test_labels_used` 是声明的 0，代码检查确认未读取 `te` 辅助标签，但不是动态污点证明。
- 只覆盖 T 弯 301 条环氧酚醛；不外推到 MEK/水煮主任务或新系列。
- 外部跨模型 reviewer 不可用；claim 状态 `REVIEW_UNAVAILABLE`，本地审计 `WARN` / `PROVISIONAL_LOCAL_AUDIT`。
