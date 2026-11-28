# P21 Experiment Plan — Role-Criticality Prior vs Mass-Dose Prior

**Problem**: 301 条环氧酚醛 T 弯样本；当前 `full8` 191 维（183 base + 8 FTIR bands），P20 已关闭 stacked 辅助目标路线。P21 检验一个更直接的特征先验：按组分在固化网络/T 弯中的**功能关键性**分配权重，而不是按质量占比；并检验对关键小量特征做单调/两段式/交互构造是否能提供可迁移信息。
**Method Thesis**: 角色关键性先验（resin / cure / catalyst 高；filler / solvent / formulation 中；molecular 低）应比质量分数先验更能解释 T 弯；对 catalyst 的 log/两段式/交互构造应在训练折内验证，而不是事后调参。
**Date**: 2026-11-28

## Claim Map

| Claim | Why It Matters | Minimum Convincing Evidence | Linked Blocks |
|---|---|---|---|
| C1 角色关键性先验 | 检验“小用量但关键”的催化剂角色能否转化为权重增益，而不是剂量先验 | `role_prior − mass_prior` QWK ≥ +0.010；≥14/20 seeds 正；Holm p<0.05；FR 上升 ≤1.0 pp；high recall 下降 ≤1.0 pp；且 `role_prior − role_prior_shuffle` ≥ +0.005（≥14/20） | B1 |
| C2 重要性感知的 catalyst 特征构造 | 检验 log/两段式是否比原始 catalyst 特征更好，而不是所有特征统一 log | `two_part_cat − full8_base` QWK ≥ +0.005；≥14/20；Holm p<0.05；FR/HR 护栏；`two_part_cat − log_cat` ≥ +0.005 | B2 |
| C3 catalyst 交互 | 检验 catalyst × cure/resin 的协同是否真实，而不是增加参数 | `interact − interact_shuffle` ≥ +0.005；≥14/20；p<0.05；`interact − full8_base` ≥ +0.005；FR/HR 护栏 | B2 |
| C4 FTIR band 诊断权重 | 检验重要峰是“诊断角色”而不是“峰强” | `ftir_band_role − ftir_band_intensity` ≥ +0.005；≥14/20；p<0.05；且 `ftir_band_role − ftir_band_shuffle` ≥ +0.005 | B3 |

**Anti-claims to rule out**

- 增益只来自 group-normalization、L2 或增加参数，而不是角色语义：用 `role_prior_shuffle` / `interact_shuffle` / `ftir_band_shuffle` 对照。
- 角色先验只在 group-normalized baseline 上有效，但低于原始 `full8`：要求 `role_prior` 相对 `full8_base` 不低超过 0.005。
- 把“小用量”误读成“低重要性”：`mass_prior` 是剂量对照；`role_prior` 必须赢它，不能只赢 `full8_base`。
- FTIR 当前只有 8 个 band fraction，不是 raw peak；P21 只能检验 band-level，不能宣称 raw peak-level。

## Paper Storyline

- **Main paper must prove**: 角色关键性先验与剂量先验在固定 301 条 T 上的差异；以及 catalyst 的零膨胀/非线性处理是否有可迁移增益。
- **Appendix can support**: FTIR band 诊断权重的特异性；`log_cat_ratio` 的探索性结果。
- **Experiments intentionally cut**: 不做 raw wavenumber peak-level（P22）；不做 191 维逐特征手工权重；不做 P20 辅助目标叠加；不做外部新数据。

## Experiment Blocks

### Block B1 — P21-A Role-criticality vs mass-dose prior

- Claim tested: C1.
- Why this block exists: 直接检验用户提出的“功能角色重要，不是用量占比”。
- Dataset / split / task: 301 条 T 弯；`StratifiedGroupKFold(5)` by `formula_id`；20 seeds；固定 `C=2.0`，cumulative logistic，balanced。
- Compared systems:
  - `full8_base`：原始 191 维，所有权重 1（P20 基线）。
  - `full8_gn_base`：同样的 191 维，按 role group 做 group-normalized uniform（每个角色组总方差相等），作为权重实验的同预处理基线。
  - `mass_prior`：同一组映射；材料角色权重 = 平均质量份额；非材料组用 `role_prior` 原始权重；归一化均值 1；group-normalized。
  - `role_prior`：关键角色（resin / cure / catalyst）= 1.0；支撑角色（filler / solvent+additive / formulation）= 0.7；描述角色（molecular）= 0.4；FTIR=1.0；other=1.0；归一化均值 1；group-normalized。
  - `role_prior_shuffle`：同一组权重的 seed-fixed 置换，放到错误角色组；保留权重多重集和范数。
- Metrics: QWK primary；three-way false release、high recall、high precision、pred high rate、MAE grade。
- Setup details: 20 seeds；outer 5 folds；权重在 StandardScaler 后乘；每个角色组按 `w_g / sqrt(n_g)` 缩放；整体 Frobenius norm 匹配 `full8_gn_base`；`C=2.0` 固定。
- Success criterion: C1 gate above；另 `role_prior` 相对 `full8_base` QWK ≥ −0.005（非劣）。
- Failure interpretation: 若 `role_prior` 赢 `full8_gn_base` 但不赢 `mass_prior`，说明只是组权重/正则化，不是角色关键性；若两者都不赢，关闭“手工角色权重”路线。
- Table / figure target: main table with role vs mass vs shuffle；appendix group weights.

### Block B2 — P21-D Importance-aware catalyst feature construction

- Claim tested: C2 (primary), C3 (supporting).
- Why this block exists: 检验“关键小量特征要体现差异”：log/两段式/交互是否比原始特征更好。
- Dataset / split / task: 同一 301 条 T、同一 5 折/20 seeds、`C=2.0`；不使用 role group weights，统一权重 1，避免与 B1 混淆。
- Compared systems:
  - `full8_base`：原始 191 维。
  - `log_cat`：`eq_cat` 替换为 `log1p(1000*eq_cat)`；其余不变。
  - `log_cat_ratio`：`eq_cat`、`r_phenol_epoxy`、`r_oh_epoxy` 分别替换为 `log1p(1000*x)`、`log1p(10*x)`、`log1p(10*x)`；探索性。
  - `two_part_cat`：`eq_cat` 替换为 `cat_has`（>0）+ `log1p(1000*eq_cat)`；检验零膨胀 catalyst。
  - `interact`：追加 4 个理论驱动乘积：`eq_cat×xlink_frac`、`eq_cat×r_phenol_epoxy`、`eq_cat×r_oh_epoxy`、`xlink_frac×resin_frac`。
  - `interact_shuffle`：同样 4 个乘积，但伙伴特征按 seed-fixed 行置换；保留乘积维度和尺度。
- Metrics: QWK primary；FR/high recall/high precision。
- Setup details: 变换只使用 X；不看 y；log 尺度固定；rank/分位数不在本轮使用；新增列在训练折内标准化；outer test 不参与任何变换参数拟合。
- Success criterion: C2 gate for `two_part_cat` vs `full8_base` and vs `log_cat`；C3 gate for `interact` vs `interact_shuffle` and vs `full8_base`.
- Failure interpretation: `log_cat` 单独赢但 `two_part_cat` 不赢，说明零膨胀指示不是关键；`interact` 不赢 shuffle，说明是参数/正则化不是协同；两者都不赢则关闭手工 catalyst 构造。
- Table / figure target: ablation table with identity/log/two-part/interact/shuffle.

### Block B3 — P21-C FTIR band diagnostic weights

- Claim tested: C4 (supporting).
- Why this block exists: 检验“重要峰”应按诊断角色而不是峰强加权；P16 只测过整块一个标量，band-level 是不同粒度。
- Dataset / split / task: 同一 301 条 T、5 折/20 seeds、`C=2.0`；base 191 维；只改 trailing FTIR8 的 band weights。
- Compared systems:
  - `full8_base`：FTIR8 均匀权重。
  - `ftir_band_role`：固定 band 权重：环氧/OH/C=O/C-O-C 高；芳香/骨架中；CH/甲氧基低。
  - `ftir_band_intensity`：training-fold mean band magnitude 归一化权重；作为“强峰=重要”对照。
  - `ftir_band_shuffle`：`ftir_band_role` 权重的 seed-fixed 置换。
- Metrics: QWK primary；FR/high recall。
- Setup details: 权重在 StandardScaler 后乘；整体 Frobenius norm 匹配 `full8_base`；band 权重均值 1；不调整 C。
- Success criterion: C4 gate.
- Failure interpretation: 若 `ftir_band_role` 不赢 intensity，说明强峰/正则化解释更强；若只赢 shuffle 不赢 intensity，不能宣称诊断角色。
- Table / figure target: appendix FTIR band table；main text one sentence.

## Run Order and Milestones

| Milestone | Goal | Runs | Decision Gate | Cost | Risk |
|---|---|---|---|---|---|
| M0 | 角色映射与权重冻结；sanity 1 seed | `--mode map`; `--mode sanity` | 基线 QWK 与 P20 sanity 对齐 ±0.005；无 NaN；241? 不适用，191/变体维度正确 | ~2 min CPU | 映射覆盖/权重泄漏 |
| M1 | P21 full 20 seeds | 15 arms ×20 seeds ×5 folds (13 pre-registered + 2 exploratory) | C1 先看；C1 fail 则 B2/B3 只做支持性报告 | ~30 min CPU | 小样本、低效应 |
| M2 | 结果审计、claim、报告 | 无重训 | C1/C2/C3/C4 按预注册 gate | ~5 min | 外部 reviewer 不可用 |

## Compute and Data Budget

- Total estimated GPU-hours: 0（CPU-only，2 vCPU）。
- Full estimate: 15 arms ×20 seeds ×5 folds = 1,500 cumulative-logistic fits；按 P20 约 1.4 s/fit，约 35 min。
- Data preparation: 无新标签；只用现有 301 条实测 T；角色映射来自材料库 + 领域 rubric。
- Human evaluation: 无；需要用户/领域专家事后检查角色映射合理性。
- Biggest bottleneck: 角色映射的主观性、group-normalization baseline 的选择、301 条样本的统计功效。

## Risks and Mitigations

- **角色映射主观**: `P21_ROLE_MAP.csv` + `P21_WEIGHT_RUBRIC.md` 冻结；歧义特征进 `other`；权重不看 y。
- **group-normalization 改变基线**: 同时报告 `full8_base` 与 `full8_gn_base`；C1 要求 role 不低于 `full8_base` 超过 0.005。
- **多组权重/多臂多重比较**: 预注册 C1/C2 两个 primary；C3/C4 标记 supporting；Holm 校正。
- **小样本功效**: 20 seeds；效应门槛 ≥0.010 / ≥0.005；不做事后调权重。
- **FTIR 不是 raw peak**: 明确 band-level 结论；raw peak 留 P22。
- **外部 reviewer 不可用**: claim 文件只写 `verdict: REVIEW_UNAVAILABLE`；本地审计 `WARN` / `PROVISIONAL_LOCAL_AUDIT`，不自判 acquit。

## Final Checklist

- [x] Main table covered by B1/B2
- [x] Novelty isolated: role vs mass; band role vs intensity
- [x] Simplicity defended: only 4 products; no 191 hand weights
- [x] Frontier component not claimed
- [x] Nice-to-have (log_cat_ratio, FTIR band) separated from primary
- [x] Results appended after full run

## Addendum A1 — Sanity-informed control arms (2026-11-28, before full)

Sanity on seed 42 was used as an implementation/assumption check, not as a
performance-selection tool. `full8_base` reproduced P20 exactly
(`QWK=0.576128`). The pre-registered `full8_gn_base` (group-normalised
uniform) scored `0.517882`, i.e. the group-size normalisation itself costs
~0.058 QWK relative to the original base. That makes the pre-registered C1
non-inferiority clause (`role_prior − full8_base ≥ −0.005`) impossible to
satisfy for any arm using the same group-normalised preprocessing, regardless
of the role weights.

Response, recorded before the 20-seed full run:

- Keep the pre-registered C1 arms and gate unchanged; report the result with
  the group-normalisation confound explicitly.
- Add two **exploratory, non-gating** arms: `mass_prior_direct` and
  `role_prior_direct`. They use the same role map and the same normalised
  weights as `mass_prior` / `role_prior`, but apply weights directly after
  `StandardScaler` without `1/sqrt(n_group)` or group-norm rescaling. Their
  purpose is to separate "role weights" from "group-size normalisation".
- `role_prior_direct − mass_prior_direct` and
  `role_prior_direct − role_prior_shuffle` are reported as exploratory
  specificity comparisons; they do not change C1's primary verdict.
- No gate, threshold, seed, split or `C` is changed. All 20 seeds are still
  reported for every arm; the exploratory arms are labelled as such.

Full run is therefore 15 arms ×20 seeds ×5 folds, estimated ~35 min CPU.


## Results appended (2026-11-28, full 20 seeds)

- `full8_base`: 0.570181 ± 0.024523 (20 seeds). On the 10 shared P20 seeds,
  identical to P20 per-seed (max abs diff 0.0; mean 0.573974).
- `full8_gn_base`: 0.507677 ± 0.021571; group-size normalisation costs
  0.0625 QWK against `full8_base`.
- `role_prior`: 0.510304 ± 0.021839; `mass_prior`: 0.487546 ± 0.018125.
  role beats mass (+0.022758, 19/20) and shuffle (+0.009394, 17/20), but is
  only +0.002627 over `full8_gn_base` (11/20, p=0.29058) and −0.059878
  against `full8_base`.
- Direct control: `role_prior_direct` 0.571143 ± 0.024126;
  `mass_prior_direct` 0.569901 ± 0.021610; delta +0.001243, 10/20, p=0.81164.
  Without groupnorm, role weights have no advantage over mass weights.
- C1 FAIL overall. C2 FAIL (`two_part_cat` vs base +0.000090; vs `log_cat`
  −0.000486). C3 FAIL (`interact` vs shuffle +0.004055, p=0.36765; vs base
  +0.000851). C4 FAIL (`ftir_band_role` vs intensity −0.001481; vs shuffle
  +0.004852, Holm p=0.09121, below +0.005 gate).
- Local audit: 27/27 checks pass; `PROVISIONAL_LOCAL_AUDIT`; external
  `REVIEW_UNAVAILABLE`; claim `verdict: REVIEW_UNAVAILABLE`,
  `claim_supported: false`.
- Interpretation: role-criticality chemistry remains plausible, but the
  current 5 catalyst-related features plus hand weights do not produce a
  deployable T-bend gain. The apparent role-vs-mass gain is a groupnorm /
  small-group amplification effect, not a role-semantic effect.
