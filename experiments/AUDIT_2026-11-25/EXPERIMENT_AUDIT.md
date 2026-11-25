# 历史实验系统审计（P0–P14 + legacy J–V）

**日期**：2026-11-25

**状态**：`PROVISIONAL` — 本地确定性证据审计完成；独立跨模型 reviewer 在当前 runtime 不可用，未进行外部 acquit。

**范围**：P0–P14 主线；P10–P14 重点复核；legacy J–V 仅做口径检查。

**结论**：5 PASS / 6 WARN / 0 FAIL。`FAIL=0` 只表示未发现数据伪造、标签泄漏或矩阵错位；`WARN` 表示推断范围和选择偏差需要修正，不能当作“全部通过”。

## 1. 审计方法与边界

本次没有重新训练 P0–P14 的全部模型，而是做**证据级复核**：

1. 对主数据集、特征矩阵、target 表做 SHA256 与形状/列关系核对。
2. 对 P14 的 nested/fixed/drop-one/subset/permutation/bootstrap 结果，逐项对照脚本常量、CSV 原始值和声明值。
3. 对 P0/P09/P13/P14 的样本口径、seed 数、指标定义做交叉核对。
4. 对远程仓库做可复现边界检查，区分“代码归档”和“完整数据归档”。
5. 使用 `result-to-claim` 的 `evidence_check.py` 做数值预检；该工具对 CSV 逗号边界存在假阴性，不能据此判定数据造假。

未完成项：Codex/manual reviewer 不可用；因此本报告是**本地审计**，不是跨模型独立审计。

## 2. 数据与标签证据

| 检查 | 结果 | 证据 |
|---|---|---|
| 主数据 SHA256 | PASS | `753afe8e97a77d1f39d4f852857da5cc204f28c445d3fbfcb3ddf7ff2d67f3f9` |
| T target 样本数/类别 | PASS | 301 条；0/1/2 = 33/197/71 |
| 标签来源 | PASS | 实测 `T弯` → `grade_from_cuts([15,20])`；不是模型输出 |
| X0 与 X7 关系 | PASS | X0 456×183；X7 345×190；X7 恰好多 7 个 FTIR 列，无 target 列 |
| 特征矩阵 target 列 | PASS | 未发现 target 名称列 |

关键含义：P14 的 T 任务使用**实测标签**，矩阵没有把 target 混入特征；这是可以继续做特征实验的前提。

## 3. P14 数值与代码证据

| 检查 | 结果 | 证据/数值 |
|---|---|---|
| P14 nested T | PASS | base183 `0.54513774`；ftir7 `0.57069734`；delta `0.02555960007`；t_p `0.004615969248`；9/10 seeds 正 |
| 190 维 vs core4 | WARN | 190 `0.5796898984` vs core4 `0.5793572088`，差 `0.0003326896`；边际收益极小 |
| 190 维 vs full8 | WARN | 190 `0.5796898984` vs full8 `0.5739744798`，差 `0.0057154186`；drop-one 选了 `ftir_oh_epox` |
| 特征选择是否 nested | WARN | `p14_t7_nested.py:59-60` 只在循环内选 C；X7 特征集在循环外固定 |
| 置换检验 | WARN | `p14_t_permutation.py:32` `N_PERM=20`；p `0.047619` 是 20 次置换的最低可能 p |
| Bootstrap 口径 | WARN | seed-level 区间窄；group-level sample bootstrap 约 `[−0.036, 0.096]`，后者才是更诚实的样本不确定性 |
| 模型族 | PASS（描述性） | 190 logistic `0.579690`；ordinal XGB `0.434567`；multiclass XGB `0.424777` |

**核心解释**：P14 的 `0.570697` 是“**条件于 post-hoc 190 维特征集**”的 nested-C 估计，不是“特征子集 + C 都 nested”的无偏估计。190 维相对 core4 只高 `0.000333`，说明“保留 190 维”很可能包含选择噪声；P15-B 因此把子集选择也放进外层训练折。

## 4. 样本、指标与历史口径

| 检查 | 结果 | 证据/含义 |
|---|---|---|
| P0/P09/P14 样本口径 | WARN | P0 T 301；P09 T 310（含 9 条聚酯金黄）；P14 仅 301 条环氧酚醛；不可直接比较 |
| 根 README 主模型 vs P14 | WARN | 根 README 是 313 维回归/分类，T masked R² `0.749`、全样本 R² `0.159`；P14 是 190 维 ordinal QWK `0.5707`；两套任务/指标 |
| 三目标平均 | WARN | T 10 seeds；MEK/水煮 3 seeds；`0.5609` 混合了不同 seed 数，不是一个统一协议 |
| P13 191 维 | WARN | 3-seed `0.568480`，base `0.533552`，delta `0.034928`；P14 后来修正 base 均值，不能把 P13 数字当最终增益 |
| P11 公式搜索 | WARN（范围） | T/MEK/水煮嵌套 ΔQWK 约 `−0.0038 / −0.0094 / −0.0190`；没有组块过 +0.03 门槛；`invalid_water` 编码错误运行已排除 |
| P10 FTIR8 | PASS（对照） | T 增量约 `+0.0283`，低于预注册 `+0.03`；FTIR8 可由 base183 重建，CV R² `0.9405–0.9997` |

## 5. 远程可复现边界

- 远程分支 `experiment/p14-best` 是**代码/报告/小表归档**，不含：
  - `feature_matrix_p13_t_ftir7.csv`
  - `feature_matrix_v2_fix_reduced.csv`
  - `ftir_sample_features_v3.csv`
  - P14 target 表与多数 P14 summary/log
- 本地有 `REMOTE_DATA.md` 与 `data/local_artifact_manifest.json`，记录了 SHA 和补齐路径。
- 结论：远程 clone 不能直接复现 P14/P15 的完整数值；必须按 manifest 补齐本地矩阵。这不是数据造假，而是归档边界。

## 6. `evidence_check.py` 假阴性说明

`result-to-claim` 的数值 pre-check 在 CSV 上出现 1 条 `verified`、10 条 `value_not_found`。原因是数值前有逗号时，匹配器的边界策略不认 CSV 字段；抽查原始 CSV 后数值存在。  
因此：**不能把 `value_not_found` 当作数值不存在或造假证据**；应回到 CSV/JSON 原始文件核对。

## 7. Claim → 影响表

| Claim | 当前支持程度 | 影响/修正 |
|---|---|---|
| P14 T 190 nested QWK `0.5707` | 条件支持 | 仅在固定 190 维时有意义；不是完整 nested 特征选择的无偏估计 |
| P14 delta `+0.0256`，p `0.0046`，9/10 seeds | 条件支持 | 点估计与 seed 方向支持；但 20 次置换的 p 是下限，且特征集是 post-hoc |
| P14 190 维是最优特征集 | 弱支持 | 190 vs core4 仅 `+0.000333`；core4 更简约，应作为首选候选或做 nested 选择 |
| P14 fixed C=2 `0.5797` | 描述性支持 | C=2 是固定值，不是嵌套选择；不能与 nested 估计混用 |
| P10 FTIR8 增量 `+0.0283` 低于门槛 | 支持 | 与 P10 预注册结论一致；FTIR8 高度线性冗余 |
| P11 公式搜索无组块过门槛 | 支持（需排除 invalid_water） | 不能把 `invalid_water` 运行纳入结论 |
| P13 191 维 delta `+0.0349` | 3-seed 初步支持 | 不是最终 10-seed 结论；P14 已修正 base 均值 |
| 三目标平均 `0.5609` | 有限支持 | T 10 seeds 与 MEK/水煮 3 seeds 混合；需分别报告 |
| 根 README `R²=0.749` | 不同口径 | 不是 P14 QWK 的直接对比对象 |

## 8. 处置建议

1. **P15-B（主实验）**：把 FTIR 子集选择与 C 选择都放进外层训练折，候选限定为 P14 已报告的 6 个子集；用 10 seeds、5 outer、3 inner 做诚实估计。这是对 `C2_P14_selection_pressure` 的直接修正。
2. **P15-A（探索性试点）**：FTIR 残差化只做 1 seed sanity；若要做确证性结论，必须另立 10-seed 预注册实验。当前 pilot 显示残差化会显著削弱信号，不能据此宣称“FTIR 增益不存在”。
3. **置换检验**：若计算允许，P15 或后续应把 permutation 提到 ≥200 次；20 次只能作为最低限度诊断。
4. **Bootstrap**：主报告使用 group-level sample bootstrap 的宽区间，seed-level 区间只作稳定性描述。
5. **三目标**：MEK/水煮若要继续作为主结论，需补到 10 seeds；否则在报告中明确标注 3 seeds。
6. **远程归档**：把 P15 的矩阵 SHA/生成脚本/manifest 一并提交；大矩阵仍按 `REMOTE_DATA.md` 补。

## 9. 最终判定

- **数据完整性**：未发现 FAIL；主数据、target、矩阵关系、P14 主数值均能对上。
- **推断有效性**：6 个 WARN 集中在**选择偏差、置换分辨率、bootstrap 口径、样本/seed 混合、远程缺数据**，不是数据造假。
- **可发表的当前结论**：P14 的 190 维增益是“固定 190 维”下的条件证据；要宣称“190 维是最优且可复现的特征集”，必须等 P15-B 的 nested 子集选择结果。
- **审计状态**：`PROVISIONAL_LOCAL_AUDIT`；`REVIEW_UNAVAILABLE`，不得写成外部 reviewer 已 acquit。
