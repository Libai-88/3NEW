# P19 Claims from Results

**Status**: `REVIEW_UNAVAILABLE` — 外部跨模型 reviewer 不可用；以下是本地确定性 claim ledger，不是跨模型 acquit。  
**审计**: `P19_EXPERIMENT_AUDIT.md` / `.json`（`WARN`，`PROVISIONAL_LOCAL_AUDIT`）。

## Claim ledger

| ID | 预注册 claim | claim_supported | 支持证据 | 缺口 |
|---|---|---|---|---|
| C1 | 训练折内 jitter / SMOTE 至少一个臂使真实 OOF QWK 提升 ≥0.020，≥7/10 seeds 正向，FR 上升 ≤1.0 pp，high recall 下降 ≤2.0 pp | **no** | 最佳增强臂 `jitter25`：ΔQWK `+0.00703`，6/10 seeds，FR `+2.39 pp`，high recall `−2.25 pp` | 效应量不足；FR/recall 双违约；`jitter10` ΔQWK `+0.00143`，4/10 seeds；`smote_low` 几乎为 0 |
| C2 | 训练折内边界加权至少一个臂使真实 OOF QWK 提升 ≥0.020，≥7/10 seeds 正向，FR 上升 ≤1.0 pp，high recall 下降 ≤2.0 pp | **no** | `boundary_w50`：ΔQWK `+0.00978`，8/10 seeds，FR `+0.42 pp`，high recall `0.00 pp`，paired p `0.063` | 效应量 `+0.00978 < +0.020`；未过预注册门槛；只能算 directional |
| C3 | 数据层审计可复现：301 条 T、44 条缺 T、0 条重复 T、190/301 在 ±1.8 mm 边界带内 | **yes** | `p19_data_audit_full.json`：301 / 44 / 0 / 190；另 45 个 FTIR 缺失单元、67 个 full8 常量列；2 个固化条件完全与系列混杂 | 无重复 T，无法估计 ICC/κ；ASTM 参考带不是本数据实测噪声 |
| C4 | 不把文献 T 值或外部数据行合并进 301 行主表 | **yes** | `P19_LITERATURE_NOTES.md`：未找到同口径公开数据集；外部 T 行 0；文献只用于精度参考 | 文献检索不是系统综述；只覆盖可检索的公开来源 |

## What the results actually show

- **增强没有创造信息。** 5 个增强/混合臂的 QWK 变化在 `−0.005` 到 `+0.007` 之间；最好的 `jitter25` 只有 6/10 seeds 正向，且 false release 上升 `2.39 pp`、high recall 下降 `2.25 pp`。这不是“数据层变好”，只是训练正则的轻微摆动。
- **边界加权方向正确但不够强。** `boundary_w50` 的 QWK `+0.00978`、8/10 seeds 正向、FR 只升 `0.42 pp`、high recall 不变；但 paired p `0.063`，效应量不到预注册的 `+0.020`。它是一个可复测的假设，不是 P19 的成功 claim。
- **降低边界权重到 0.25 反而更差。** `boundary_w25` ΔQWK `−0.00303`、5/10 seeds、FR `+1.83 pp`、high recall `−2.25 pp`；说明边界样本不能简单丢弃/压权。
- **低类 SMOTE 基本无效。** `smote_low` ΔQWK `+0.00017`，FR 不变，high recall `+0.99 pp`；合成低类样本没有改变排序能力。
- **固化条件臂有表面增益但不可部署。** `cure_meta` ΔQWK `+0.01147`、8/10 seeds，但 high recall `−2.39 pp`；且 200 °C/10 min 与 205 °C/17 min 完全由系列决定，无法把“条件效应”与“系列身份”分开。
- **标签噪声是主要瓶颈。** ASTM D4145 的 galvanized steel SD `1.33 mm`、within-lab repeatability `1.8 mm`；301 条中有 `190` 条（`63.1%`）落在距切点 ±1.8 mm 内。当前表没有重复 T，无法估计 ICC/κ。标签噪声模拟（σ=1.8 mm）下，重切标签与原始标签的 QWK 只有 `0.661`、一致率 `74.7%`——这是标签一致性上限的诊断，不是模型成绩。

## Suggested claim revision

不要写“P19 通过数据增强提升了数据层质量”。可写：

> 在 301 条 T 标签、冻结 P16 `full8`、10 seeds 和训练折内增强的预注册协议下，jitter/SMOTE 与边界加权均未达到真实 OOF QWK `+0.020` 的门槛；最佳方向性结果是 `boundary_w50`（`+0.00978`，8/10 seeds，FR `+0.42 pp`，high recall 不变，p `0.063`），但不能作为部署 claim。数据层的主要限制是标签边界不确定、无重复测量、固化条件与系列混杂；合成样本不能替代新的 T 测量。

## Next experiments needed

1. **真正的数据层补强**：20–30 条分层重复 T 测试（覆盖 15/20 切点附近、R/C/D 系列、两种固化条件），估计 ICC/κ 和标签噪声地板。
2. **44 条未测环氧酚醛 T** 优先补测；其中 41 条已有 MEK、22 条已有水煮，可用于后续多任务/辅助表征，但不能当作 T 标签。
3. **P19-B（需新预注册）**：若要继续 `boundary_w50`，用更多 seeds 或新数据复测；不能把本次 `+0.00978` 直接升级成成功。
4. **P20 未做**：跨目标辅助表征（MEK/水煮）仍是高风险备选，且当前 301 条 T 的信息瓶颈未解；不建议在 P19 负结果后直接开跑。
