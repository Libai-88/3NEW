# P15 实验计划：FTIR 特征稳健性（残差化试点 + 嵌套子集选择）

**日期**：2026-11-25

**状态**：P15-B full 已完成；P15-A 仅 1 seed sanity，探索性，不纳入确证。

**主问题**：P14 的 190 维 FTIR 增益，在把“FTIR 子集选择”也放进外层训练折之后，是否仍然存在？如果存在，是否可以用更少、更稳定的 FTIR 特征保留大部分增益？

## 1. 背景与动机

P14 的 T 结果：

- base183 nested：`0.54513774`
- FTIR7（190 维）nested：`0.57069734`
- delta：`+0.02555960007`；t_p `0.004615969248`；9/10 seeds 正

但审计发现一个关键边界：`p14_t7_nested.py` 只 nested 了 C，190 维特征集在循环外固定；`ftir_oh_epox` 是看完全部 10-seed 结果后由 drop-one 选出的。  
所以 `0.5707` 是“**条件于 190 维**”的估计，不是“**特征子集 + C 都 nested**”的无偏估计。P14 自己已记录：190 维 vs core4 只差 `0.000333`，提示“保留 190”可能没有实质收益。

P15 分两个臂：

- **P15-A（探索性）**：FTIR 对 base183 的折内残差化。检验“P14 的增益是否主要来自 base 无法线性解释的残差”。只做 1 seed sanity，不作为确证结论；若要做确证，另立 10-seed 实验。
- **P15-B（主实验）**：把 FTIR 子集选择与 C 选择都放进外层训练折，估计“选择流程”本身的泛化 QWK。候选只使用 P14 已报告的 6 个子集，不做新的穷举搜索。

## 2. 数据与特征

- 主数据：`合并版数据集.xlsx`（SHA256 `753afe8e...f67f3f9`）
- T 样本：301 条环氧酚醛；类别 0/1/2 = 33/197/71；标签 `T弯` → `grade_from_cuts([15,20])`
- 基础矩阵：`experiments/P10_ftir_v3/data/feature_matrix_v2_fix_reduced.csv`，456×183
- FTIR8 矩阵：`experiments/P13_feature_opt/data/feature_matrix_p13_t_ftir8.csv`，191 维 = 183 + 8
- 分组：`formula_id`（301 个 T group 全唯一）
- 缺失：FTIR 7 维有少量缺失；统一 median impute + 缺失指示列；残差化与 raw 使用同一预处理路径

## 3. P15-B 设计（主实验）

### 3.1 候选子集（P14 已报告，不新增搜索）

| 名称 | FTIR 列 | 维度 |
|---|---|---:|
| `base183` | 无 | 183 |
| `full8` | 8 个原始 FTIR | 191 |
| `drop_oh_epox` | 去掉 `ftir_oh_epox` | 190 |
| `drop_oh_epox_aroc` | 去掉 `ftir_oh_epox`、`ftir_aroc_phen` | 189 |
| `core4` | `meoh_phen, ch_all, coc_all, oh_phen` | 187 |
| `core5` | core4 + `arsub_all` | 188 |

### 3.2 选择协议

对每个 seed、每个外层折：

1. 外层训练折内做 `StratifiedGroupKFold(3)` 内层 CV；
2. 对每个候选子集 × `C ∈ {0.5, 1.0, 1.5, 2.0}` 计算内层 QWK；
3. 选内层 QWK 最高的 `(subset, C)`；
4. 用该组合在外层训练折重训，预测外层测试折；
5. 汇总 5 个外层折的 OOF，计算 QWK/MAE/高档 recall/overprediction/cost。

**关键**：外层测试折不参与子集选择、C 选择、缺失值拟合或标准化拟合。

### 3.3 Seeds 与模型

- seeds：`42, 202, 777, 1234, 2026, 31415, 2718, 1618, 5678, 9999`（10 个）
- 模型：ordinal cumulative logistic；`class_weight=balanced`；L2；`max_iter=3000`
- 预处理：median impute + 缺失指示；`StandardScaler`
- 指标：QWK 主指标；MAE、高档 recall、overprediction、cost 为护栏

### 3.4 预注册判定规则

以 10-seed 均值为主：

- **通过（P14 190 稳定）**：nested 选择 QWK ≥ `0.565`，且任一 FTIR 子集（非 base183）在 ≥70% 外层折被选中；同时 `drop_oh_epox` 或 `core4` 的选择份额 ≥50%。
- **简约通过**：`core4` 或 `core5` 在 ≥70% 外层折被选中，且 QWK ≥ `0.565`；此时优先报告更少特征。
- **部分通过**：QWK `0.550–0.565`，或选择分布高度分散（最高份额 <30%）；报告为“选择不稳定，P14 190 不能作为唯一最优”。
- **失败**：QWK < `0.550`，或 `base183` 在 ≥50% 外层折被选中；说明 FTIR 增益在诚实选择下不稳健。
- **护栏**：相对 P14 190 fixed，若高档 recall 下降 >0.02 或 cost 上升 >0.02，即使 QWK 达标也标记“性能换简约需谨慎”。

参考（非配对基线）：P14 190 fixed C=2 的 10-seed `0.5796898984`；P15-B 的 nested 选择会低于这个值，因为 C 和子集都承担了选择方差。

### 3.5 预期成本

6 子集 × 4 C × 3 inner × 2 thresholds × 5 outer × 10 seeds ≈ 7200 次 logistic 拟合；当前 2 vCPU / 3.9 GiB，单 seed sanity 约 48 秒，full 约 8–10 分钟。

## 4. P15-A 设计（探索性试点，不纳入确证）

目的：把 base183 能线性解释的 FTIR 部分在**外层训练折内**回归掉，只把残差送入模型。

- 拟合：`Ridge(alpha=1.0)`，base183 → FTIR7，仅外层训练折拟合；内层 C 选择时在内层训练折重新拟合。
- 三个集合：`base183`、`raw_ftir7`、`resid_ftir7`；统一 median impute + 缺失指示。
- **1 seed sanity** 结果：base `0.5400`、raw `0.5810`、resid `0.5401`；Ridge 训练折 R² 均值 `0.967`，残差标准差比 `0.161`。  
  解释：残差化去掉了过多信号；这不是“FTIR 无信息”的证据，只是“简单线性残差化不适合当前 301 条数据”。不纳入 P15-B 判定。

## 5. 运行顺序与自动化

1. `p15a_residual_pilot.py --mode sanity --tag sanity`（已完成；仅 1 seed，探索性）
2. `p15b_nested_selection.py --mode sanity --tag sanity`（已完成；1 seed，QWK `0.5705`）
3. `p15b_nested_selection.py --mode full --tag full`（已完成；10 seeds）
4. 输出：`per_seed.csv`、`chosen.csv`、`selection_frequency.csv`、`vs_p14.csv`、`delta.csv`、`config.json`
5. 汇总到 `P15_实验报告.md`；更新 `EXPERIMENT_TRACKER.md`

执行入口：`experiments/P15_feature_robustness/scripts/run_p15.sh`。  
所有运行日志写入 `logs/`；不覆盖已有结果，sanity 与 full 分文件。

## 6. 风险与边界

- 301 条样本 + 3 类不平衡：QWK 的 seed 方差不可忽略；报告均值、sd、逐 seed 方向。
- 6 个候选子集仍来自 P14 的同一批报告，存在“候选集本身受历史选择影响”的残余风险；P15-B 只能修正“在候选集内选择”的偏差，不能修正“候选集如何产生”的偏差。
- C grid 只有 4 个值；若最优 C 在边界，需在报告中标注。
- P15-A 只有 1 seed，不能用于确证；不得把 pilot 的负结果写成“FTIR 增益不存在”。
- 远程仓库仍缺大矩阵；P15 结果与矩阵 SHA/manifest 必须一起归档，否则无法复现。

## 7. 交付物

- `results/p15b_full_per_seed.csv`
- `results/p15b_full_summary.csv`
- `results/p15b_full_chosen.csv`
- `results/p15b_full_selection_frequency.csv`
- `results/p15b_full_vs_p14.csv`
- `results/p15b_full_delta.csv`
- `results/p15b_full_config.json`
- `results/P15_实验报告.md`
- `refine-logs/EXPERIMENT_TRACKER.md`
