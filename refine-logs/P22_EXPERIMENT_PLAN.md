# P22 Experiment Plan — Cure-State Representation vs Bake-Identity Control

**Problem**: P21 已证明“手工角色权重 + 现有 catalyst 特征”在 301 条环氧酚醛 T 弯上不能产生可部署增益。P22 不再调权重，改问一个表示问题：在冻结的 191 维 `full8` 之外，是否存在一个**紧凑、物理可解释、非冗余**的固化状态表示，能解释 P21 没解释到的 T 弯差异；如果有，它是否只是烘烤条件/系列身份的代理？

**Method Thesis**: 用 2 维后固化状态 `cure_state = [cure_drive, cure_margin_eff]`（达到的网络驱动 + 有效热固化裕度）替换 P21 的手工角色权重；先证明它优于 191 维基线，再用 `bake_control`、`cure_state_shuffle` 和 leave-one-condition-out 证明增益不是烘烤身份或维度噪声。

**Date**: 2026-11-28

## Claim Map

| Claim | Why It Matters | Minimum Convincing Evidence | Linked Blocks |
|---|---|---|---|
| C1 固化状态表示的主效应 | 检验 P21 的负结果是否因为漏掉了唯一有独立方差的固化状态变量，而不是角色语义错 | `cure_state − full8_base` QWK ≥ **+0.010**；≥ **14/20** seeds 正；Holm 后 paired p < 0.05；FR 上升 ≤ **1.0 pp**；high recall 下降 ≤ **2.0 pp** | B1 |
| C2 烘烤身份/条件可分性 | 防止把 `cure_drive` / `cure_margin_eff` 的增益误读成“固化机理”，实际只是 200/10 vs 205/17 的烘烤身份 | 两个条件同时满足：(a) 分布内 `cure_state_plus_bake − bake_control` ≥ **+0.005**，≥14/20，Holm p<0.05；(b) leave-one-condition-out 池化 OOF `cure_state − full8_base` ≥ **+0.005**，且 FR/HR 护栏不破 | B2 |
| C3 语义特异性 / placebo | 排除“多两列 + 正则化”解释；同维度随机块不应有同等增益 | `cure_state − cure_state_shuffle` ≥ **+0.005**；≥14/20；paired p<0.05；FR/HR 护栏 | B1 |

**Anti-claims to rule out**

- 增益只来自烘烤条件：`bake_control` 是 P19 `cure_meta` 的同口径对照；C2(a) 要求 cure 在 bake 已入模后仍有增量。
- 增益只来自条件外推/系列身份：C2(b) 用 leave-one-condition-out，训练一个烘烤条件、测试另一个；只有两个条件，因此这是压力测试而非总体推断。
- 增益只来自多两列或 L2：`cure_state_shuffle` 保留同样维度、同样边际分布，只打乱样本对应。
- 增益来自 `tg_rise_est` 这类近似线性可重建变量：主臂只放 CURE2；`tg_rise_est` 只进 B3 简化性检查，不进入主 claim。
- 把 catalyst type one-hot 或 acid dose 重新包装成“新表示”：301 条主体系里 `AC040`/`AZ135` 为 0；`acid_phosphate_frac` 与已入模的 `eq_cat` Spearman `0.99999`，没有独立方差。

## Data Feasibility (pre-registration audit)

**固定建模集**：301 条实测 T，标签 `33/197/71`，cuts `[15,20]`，`formula_id` 301 组；191 维 = 183 base + 8 FTIR。P20 10-seed 基线 `0.573974 ± 0.024638`；P21 20-seed 基线 `0.570181 ± 0.024523`；P20 sanity seed 42 = `0.576128`；FR `3.6620%`，high recall `78.7324%`。

**不可行/冗余的候选项（不做）**

| 候选项 | 数据事实 | P22 决定 |
|---|---|---|
| catalyst type one-hot | 301 条中 `10%磷酸` 251 条有、50 条无；`AC040`=0、`AZ135`=0；后两者只在 72 条非 FTIR 的其他体系 T 标签里 | 不做；该列在 301 主体系恒定 |
| `acid_phosphate_frac` 两段式/样条 | 与已入模 `eq_cat` Spearman `0.99999`；Ridge 从 191 base 重建 R² `1.0000` | 不做；只是 `eq_cat` 的单调重标定 |
| `volatile_frac` | 与 `solids_frac` Spearman `−1.0000`；R² `1.0000` | 不做；精确重复 |
| `m_solids` | R² `0.9978`；与配方总固体量线性可重建 | 不做；无独立方差 |
| `eq_epoxy` | R² `0.9998` | 不做；已被 base 线性覆盖 |
| `tg_linear_solids` | R² `0.9998`；与 `w_Tg` Spearman `0.946` | 不做；近似重复 |
| `cure_margin` | R² `0.8530`；与 `cure_margin_eff` Spearman `0.905` | 不做；保留 `cure_margin_eff` |
| `ne_effective` | R² `0.4210`；与 `cure_drive` Spearman `0.992` | 不做；保留 `cure_drive` |
| `t_eff_min` | 只有 2 个取值（10 / 21.59），就是烘烤条件代理；R² `−0.0116` | 不做特征；只做 `bake_control` |
| `pvc_over_binder_vol` | 301 条恒为 0 | 不做 |
| `cure_margin_neg` | 301 条恒为 0 | 不做 |

**保留的 CURE2 / CURE3**

| 特征 | 物理含义 | 从 191 base 重建 R² | 与 T grade Spearman | 角色 |
|---|---|---:|---:|---|
| `cure_drive` | `t_eff_min × ne_potential`，达到的网络驱动 | `0.2887` | `+0.2044` | CURE2 主特征 |
| `cure_margin_eff` | `bake_temp − tg_fox_solids − tg_rise_est`，有效热固化裕度 | `0.7236` | `+0.3599` | CURE2 主特征 |
| `tg_rise_est` | `ne_potential` 的后固化 Tg 抬升估计 | `0.9546` | `+0.2937` | 仅 B3 探索；不进主 claim |

**CURE2 统计**：`cure_drive` min/median/max `0.007127 / 0.073090 / 0.168254`，sd `0.036975`；`cure_margin_eff` `70.5532 / 82.8650 / 104.4935`，sd `4.9447`；均无缺失、非常量。`cure_205` 二元条件 `182 / 119`（1=205°C/17min；0=200°C/10min）。

**结论**：13 个“被 P21 漏掉”的机理列里，真正有独立方差的只有 `cure_drive`、`ne_effective`、`cure_margin_eff`、`cure_margin` 以及边缘的 `tg_rise_est`；其中 `ne_effective` 与 `cure_drive` 近乎共线，`cure_margin` 与 `cure_margin_eff` 近乎共线。P22 因此不是“加 7 个配方特征”，而是“加 2 个后固化状态 + 严格烘烤对照”。

## Paper Storyline

- **Main paper must prove**: C1 的分布内增量 + C2 的条件可分性。只有 C1 不构成可部署 claim；只有 C2 没有 C1 也没有意义。
- **Appendix can support**: C3 placebo；CURE3 简化性检查；LOCO/LOSO 分系列误差；P21 负结果与 P22 的衔接。
- **Experiments intentionally cut**: 手工角色权重、catalyst type one-hot、acid dose 两段式/样条、7 个配方侧“新特征”、原料纯谱 raw peak-level、P20 跨目标辅助监督。
- **If C1/C2 both fail**: P22 是负结果，结论是“当前 301 条 + 两个烘烤条件不足以把固化状态变成可部署 T 弯信号”；下一轮（P23）应转向连续 T 监督/新测量，而不是继续在 191 维上手工构造特征。

## Experiment Blocks

### Block B0 — Data feasibility / redundancy triage

- Claim tested: none directly; freezes which mechanism columns are eligible.
- Why this block exists: P21 的 catalyst 路线在 301 主体系上不可检验；必须先把“可加的列”和“重复列”分开，避免 P22 变成又一次手工委婉搜索。
- Dataset / split / task: 301 条 T；191 base；Ridge 重建用 `GroupKFold(5)` by `formula_id`；目标不参与筛选。
- Compared systems: 13 个 omitted columns，逐一做 R² 重建 + Spearman 描述；`acid_phosphate_frac` vs `eq_cat`；`volatile_frac` vs `solids_frac`；catalyst code counts。
- Metrics: R²、Spearman、nonconstant 计数、缺失/常量计数。
- Setup details: `SimpleImputer(median, add_indicator)` + `StandardScaler` + `Ridge(alpha=1.0)`，全部只在训练折拟合；`P22_FEATURE_TRIAGE.csv` 已生成。
- Success criterion: CURE2 两个特征非常量、无缺失、R² 明显低于 0.95；`bake_control` 可构造；没有目标泄漏。
- Failure interpretation: 若 CURE2 也近似可重建，P22 应直接停止，不再做模型。
- Table / figure target: appendix triage table；main text one paragraph.
- Priority: MUST-RUN（已完成数据审计，模型运行前复核）

### Block B1 — Cure-state main effect and placebo

- Claim tested: C1 (primary), C3 (supporting).
- Why this block exists: 检验“漏掉的固化状态”是否比 191 维 base 多出可学习信号；同维度 shuffle 排除参数/正则化解释。
- Dataset / split / task: 301 条 T；`StratifiedGroupKFold(5)` by `formula_id`；20 seeds（P21 seeds）；固定 `C=2.0`；ordinal cumulative logistic；`class_weight=balanced`；L2；`max_iter=3000`。
- Compared systems:
  - `full8_base`：191 维，所有权重 1；P20/P21 同口径。
  - `cure_state`：191 + `cure_drive` + `cure_margin_eff` = 193 维。
  - `cure_state_shuffle`：同 193 维；每个 seed 对 CURE2 两列做一次**全样本行置换**（不触碰 y），再进入同一 CV；保留边际分布和维度。
  - `bake_control`：191 + `cure_205` 二元 = 192 维；P19 `cure_meta` 同口径。
  - `cure_state_plus_bake`：191 + CURE2 + `cure_205` = 194 维；检验 bake 已入模后 cure 是否仍有增量。
  - `cure_state_tg`：191 + CURE2 + `tg_rise_est` = 194 维；仅 B3 简化性，不参与 C1/C3。
- Metrics: QWK primary；three-way false release、high recall、high precision、pred high rate、grade MAE；paired delta FR/HR。
- Setup details: imputer/scaler 只在 outer training fold 拟合；CURE2 在 base 之后追加并单独标准化；`bake_control` 保持 0/1 原始编码；不使用 groupnorm、不使用角色权重、不调 C。每个 seed 使用同一组 outer folds；`cure_state_shuffle` 的置换 seed 由 run seed 固定，且在切分前完成，不使用 y。
- Success criterion: C1：`cure_state − full8_base` ≥ +0.010，≥14/20，Holm p<0.05，FR≤+1.0 pp，HR≥−2.0 pp。C3：`cure_state − cure_state_shuffle` ≥ +0.005，≥14/20，p<0.05，FR/HR 护栏。
- Failure interpretation: C1 失败 → 固化状态块不够，关闭这条路线；C1 过但 C3 失败 → 增益更像维度/正则化，不是语义。
- Table / figure target: main table `base / cure_state / shuffle / bake / cure+bake`；appendix coefficient signs。
- Priority: MUST-RUN

### Block B2 — Bake identity and condition separation

- Claim tested: C2 (primary).
- Why this block exists: `cure_drive` 和 `cure_margin_eff` 都依赖烘烤温度/时间；P19 已证明两个固化条件完全由系列决定，不能把条件效应和系列身份分开。必须做条件外推压力测试。
- Dataset / split / task:
  - **B2a in-distribution**: 同 B1 的 5-fold/20 seeds；比较 `cure_state_plus_bake − bake_control`。
  - **B2b leave-one-condition-out (LOCO)**: 两个固定条件：A=`200°C/10min`（119 条），B=`205°C/17min`（182 条）。每个 seed 做两次：train A→test B，train B→test A；把 301 条 held-out 预测拼成一份 pooled OOF，算全局 QWK/FR/HR；20 seeds。只有两个条件，因此不做跨条件显著性推断，只做预注册的效应量压力测试。
  - **B2c leave-one-series-out (LOSO, support)**: 21 个系列逐一留出，pooled OOF；只报告 `cure_state − full8_base`，作为系列外推的辅助诊断，不进入 C2 gate。
- Compared systems: `full8_base`, `cure_state`, `bake_control`, `cure_state_plus_bake`（LOCO/LOSO 只跑这 4 个；`shuffle`/`cure_state_tg` 不跑压力测试）。
- Metrics: pooled QWK primary；FR、high recall；按条件/系列的 error slices。
- Setup details: 同一 imputer/scaler 协议；LOCO 训练折含全部 3 个等级（A: 20/66/33；B: 13/131/38），测试折也含 3 个等级；LOSO 每个训练折检查 3 个等级齐全，否则该 seed/fold 标记无效。`bake_control` 在 LOCO 训练折内是常量（A=0 或 B=1），所以 **LOCO 不比较 bake_control**；只比较 `cure_state − full8_base`。
- Success criterion: C2(a) `cure_state_plus_bake − bake_control` ≥ +0.005，≥14/20，Holm p<0.05，FR/HR 护栏；C2(b) LOCO pooled `cure_state − full8_base` ≥ +0.005，FR≤+1.0 pp，HR≥−2.0 pp。两者同时满足才算 C2 pass。
- Failure interpretation: C2(a) 失败 → 分布内增益可由 bake 身份解释；C2(b) 失败 → cure-state 只在同条件内有效，不能跨条件；两种失败都把 C1 降级为“诊断性”，不写成可部署 claim。
- Table / figure target: main table condition slices；appendix LOCO/LOSO。
- Priority: MUST-RUN（C2b）；LOSO NICE-TO-HAVE

### Block B3 — Simplicity check: CURE2 vs CURE3

- Claim tested: none formal; defends simplicity.
- Why this block exists: `tg_rise_est` 的 R² 0.9546，接近 base 线性可重建；需要证明“多一个物理变量”是否值得。
- Dataset / split / task: 同 B1 的 5-fold/20 seeds；`cure_state` vs `cure_state_tg`。
- Compared systems: `cure_state` (193), `cure_state_tg` (194).
- Metrics: QWK, FR, HR；paired delta。
- Setup details: 同 B1；`tg_rise_est` 只在训练折标准化；不调 C。
- Success criterion: 若 `cure_state_tg − cure_state` < +0.003 或 <12/20 seeds 正，保留 CURE2，不把 CURE3 升级为主臂；若 ≥+0.003 且 C2 仍过，只能作为 exploratory candidate，需下一轮预注册复测。
- Failure interpretation: CURE3 不更好 → 支持 2 维紧凑表示，符合 simplicity。
- Table / figure target: appendix one row。
- Priority: NICE-TO-HAVE

### Block B4 — Failure analysis and qualitative diagnosis

- Claim tested: none; explains what remains.
- Why this block exists: P21 的结论需要和 P22 接上：如果 cure-state 只在同条件有效，下一步应做数据采集还是连续标签。
- Dataset / split / task: 用 B1/B2 的 OOF；按 grade、series、bake condition、predicted high 分层。
- Compared systems: `full8_base`, `cure_state`, `bake_control`, `cure_state_plus_bake`。
- Metrics: calibration、confusion matrix、per-series QWK/MAE（样本足够的系列）、coefficient signs、error vs T distance to cut。
- Setup details: 只做描述性分析；不基于测试集调特征/阈值。
- Success criterion: 给出可复现的 failure taxonomy；不产生新 claim。
- Failure interpretation: 若误差集中在边界/高等级，P23 应优先连续 T 监督或新测量，而不是再加手工特征。
- Table / figure target: appendix / report。
- Priority: MUST-RUN (report)

## Run Order and Milestones

| Milestone | Goal | Runs | Decision Gate | Cost | Risk |
|---|---|---|---|---|---|
| M0 | freeze triage + config; sanity | `p22_feature_triage.py`; `--mode sanity` 1 seed | `full8_base` seed42 = `0.576128`；dims 191/193/192/194；无 NaN；CURE2 无缺失；`cure_205` 182/119 | ~2 min CPU | 数据路径/列顺序错误 |
| M1 | main 5-fold 20 seeds | 6 arms ×20 seeds ×5 folds = 600 fits | C1/C3 按预注册 gate | ~3 min CPU | 小样本、效应量不足 |
| M2 | condition/series stress | LOCO 4 arms ×20×2 = 160；LOSO 4×20×21 = 1,680 | C2(a)/C2(b)；C1 fail 则只跑 LOCO 3 臂诊断 | ~8 min CPU | 只有 2 个条件，不能做条件总体推断 |
| M3 | simplicity / audit / claim / report | CURE3 100 fits；审计；报告 | CURE3 不升级；本地审计全过；外部 reviewer 不可用则 `REVIEW_UNAVAILABLE` | ~5 min | 多重比较/事后解释 |
| M4 | remote archive | 关键文件 | 按 P19/P20/P21 先例归档 | ~5 min | connector 写入需确认 |

## Compute and Data Budget

- Total estimated GPU-hours: **0**（CPU-only，2 vCPU）。
- Main: 600 cumulative-logistic fits；LOCO 160；LOSO 1,680；CURE3 100；合计 2,540 fits。按 P21 实测 ~0.20 s/fit，约 **8–10 min**，加数据加载/报告预计 **15 min** 内。
- Data preparation: 无新标签；只读 `合并版数据集.xlsx`、191 base CSV、FTIR sample CSV；不生成合成样本。
- Human evaluation: 需要领域专家复核 CURE2 的物理含义和 `bake_control` 口径；不需要标注。
- Biggest bottleneck: 不是算力，而是只有两个烘烤条件且条件与系列完全混杂；C2 只能是压力测试，不能估计条件总体效应。

## Risks and Mitigations

- **烘烤条件 provenance 不确定**: P0.5 已把工艺特征列为默认安全基线之外；P22 不把 `cure_state` 直接写成可部署，C2 不过即降级。
- **条件与系列完全混杂**: 不做“条件效应”因果 claim；LOCO 只做 pooled 压力测试，LOSO 只做辅助。
- **只有两个条件**: 不做跨条件 p 值/置信区间；C2(b) 用预注册效应量 + FR/HR 护栏，不声称总体显著。
- **CURE2 仍含 bake 信息**: C2(a) 要求 `cure_state_plus_bake − bake_control` 有增量；C2(b) 要求跨条件仍正。
- **`cure_drive` / `ne_effective` 共线**: 主臂只放 `cure_drive`，不放 `ne_effective`；避免无意义双重计数。
- **`tg_rise_est` 近似可重建**: 只进 B3，不进主 claim；CURE3 不因“多一个变量”自动升级。
- **多重比较**: C1 与 C2(a) 预注册为 primary，Holm 校正；C3 supporting，单独报告；B3/B4 不产生 claim。
- **小样本功效**: 20 seeds、5 folds、固定 C；效应门槛 +0.010/+0.005；不做事后调 C/阈值/权重。
- **shuffle 破坏系列结构**: placebo 只打乱 CURE2 两列，不动 base/FTIR；目的是语义特异性，不是模拟真实缺失。
- **外部 reviewer 不可用**: claim 只写 `REVIEW_UNAVAILABLE`；本地审计 `PROVISIONAL_LOCAL_AUDIT`，不自判 acquit。

## Final Checklist

- [x] Main paper table covered by B1/B2
- [x] Novelty isolated: cure-state vs base, bake control, shuffle
- [x] Simplicity defended: CURE2 vs CURE3
- [x] Frontier component not claimed
- [x] Nice-to-have (CURE3, LOSO) separated from must-run
- [x] Results appended after full run
- [x] Claim/audit/report written after results
- [ ] Remote archive after user confirmation

## Results appended (2026-11-28, full 20 seeds)

- `full8_base`: `0.570181 ± 0.024523`; sanity seed 42 `0.5761275403`, exact P20 `0.576128`.
- `cure_state`: `0.579188 ± 0.021923`; `cure_state − full8_base` `+0.009007`, 12/20, Holm p `0.20269`, FR `+0.775 pp`, HR `−2.042 pp`; C1 FAIL.
- `cure_state_shuffle`: `0.564584 ± 0.021782`; `cure_state − shuffle` `+0.014604`, 14/20, p `0.01530`; C3 supporting PASS.
- `bake_control`: `0.582640 ± 0.022421`; `+0.012458` vs base, 12/20, p `0.0164`, HR `−1.761 pp`; strongest single arm but not a new representation.
- `cure_state_plus_bake`: `0.579028 ± 0.023242`; `−0.003612` vs `bake_control`, 6/20; C2a FAIL.
- `cure_state_tg`: `0.575539 ± 0.023153`; `−0.003649` vs CURE2, 4/20; CURE3 not upgraded.
- LOCO: `full8_base` `0.463109`; `cure_state` `0.327897` (`−0.135212`, 0/20); `bake_control` `0.460770`; `cure_state_plus_bake` `0.327897`; C2b FAIL. LOCO has only 2 fixed condition folds and is seed-deterministic; descriptive only, no cross-condition p.
- LOSO skipped per pre-registered stop/go because C1 failed.
- Local audit: 24/24 pass; `PROVISIONAL_LOCAL_AUDIT`; external `REVIEW_UNAVAILABLE`; `claim_supported=false`.
- Decision: close the cure-state route; no new deployable arm. Baseline remains `full8_base` 191 raw + ordinal logistic C=2. Next: P23 continuous-T supervision or new measurements, not more handcrafted features.
