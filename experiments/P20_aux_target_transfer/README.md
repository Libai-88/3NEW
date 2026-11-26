# P20：跨目标辅助表征（MEK / 水煮 → T 弯）

**日期**：2026-11-26  
**状态**：已完成。C1/C2 **FAIL**；C3/C4 描述性/负约束通过；外部 reviewer `REVIEW_UNAVAILABLE`。10-seed 结果：`aux_mek4` ΔQWK `−0.003824`、`aux_water3` `−0.006728`、`aux_both` `−0.014573`，三个真实辅助臂均低于 `full8_base`；`aux_both` vs shuffle specificity `+0.009348`、6/10、p `0.156`，未过 `+0.010` / 7 seeds。详见 `results/P20_实验报告.md`。

## 问题

P19 已证明训练折内合成增强不能替代新的 T 测量。P20 检验另一条路径：MEK 和水煮标签能否作为训练期辅助目标，给 T 弯模型提供可迁移的表征，而不是单纯增加特征维度。

## 方法

- T 目标：301 条环氧酚醛 T 弯，切点 `[15, 20]`，三档标签 `33 / 197 / 71`。
- 辅助目标：
  - MEK 4 级：`≤50 / 50–100 / 100–200 / ≥200`；298/301 有标签。
  - 水煮 3 级：`1–2 / 3 / 4–5`；239/301 有标签。
- 辅助模型：P16 `full8`（183 + 8 FTIR，191 维）+ 累积 logistic；`C=2.0`，`w=1.0`，`class_weight=balanced`。
- 训练期表征：
  - 外层训练折内做 3 折 group inner CV，生成训练行的辅助 OOF 概率；
  - 外层测试行的辅助概率只由训练折模型预测，**不读取测试辅助标签**。
  - 缺失辅助标签的训练行用外层训练折类先验填充；测试行不输入辅助标签。
- T 弯模型：`full8` 经 P16 `BlockWeightPrep`，再拼接并标准化辅助概率；`C=2.0`，`w=1.0`。
- 外层：`StratifiedGroupKFold(5)`，`formula_id` groups，10 seeds。

## Arms

| Arm | 含义 |
|---|---|
| `full8_base` | P19 基线，无辅助标签 |
| `aux_mek4` | MEK 4 级辅助概率 |
| `aux_water3` | 水煮 3 级辅助概率 |
| `aux_both` | MEK + 水煮辅助概率 |
| `aux_mek4_shuffle` | MEK 标签打乱 placebo |
| `aux_both_shuffle` | MEK + 水煮标签打乱 placebo |

## 预注册 gate

- C1：`aux_mek4` vs `full8_base`，均值 ΔQWK ≥ +0.020，≥7/10 seeds，FR 上升 ≤1.0 pp，high recall 下降 ≤2.0 pp。
- C2：`aux_both` vs `full8_base` 达到同款 gate，且 `aux_both` vs `aux_both_shuffle` 均值 ΔQWK ≥ +0.010、≥7/10 seeds、FR/HR 不恶化超过限值。
- C3：辅助覆盖与臂级结果可复核（描述性）。
- C4：50 个 outer folds 的 `n_aux_test_labels_used=0`。

## 运行

```bash
tooling/run.sh python3 experiments/P20_aux_target_transfer/scripts/p20_aux_transfer.py \
  --mode sanity --tag sanity

tooling/run.sh python3 experiments/P20_aux_target_transfer/scripts/p20_aux_transfer.py \
  --mode full --seeds 42 202 777 1234 2026 31415 2718 1618 5678 9999 --tag full
```

## 产物

- `scripts/p20_aux_transfer.py`
- `results/p20_summary_full.csv`
- `results/p20_delta_full.csv`
- `results/p20_specificity_full.csv`
- `results/p20_per_seed_full.csv`
- `results/p20_oof_proba_full.csv`
- `results/p20_aux_audit_full.csv`
- `results/p20_claim_check_full.json`
- `results/p20_config_full.json`
- `results/P20_实验报告.md`
- `results/P20_EXPERIMENT_AUDIT.md` / `.json`
- `results/P20_CLAIMS_FROM_RESULTS.md`

## 边界

- 只使用现有 MEK / 水煮标签，不新增 T 测量，不合并外部数据。
- 测试折不使用辅助 GT；没有 oracle 辅助标签臂。
- 辅助标签与 T 的关系不是因果；P20 只检验预测表征。
