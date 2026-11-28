# P21 Weight Rubric — Role Criticality, Not Mass Fraction

**Frozen before any P21 model run. Do not tune these values on QWK.**

## Core principle

A component's weight reflects its **functional criticality in the cured network and T-bend**, not its mass share.

- Resin: primary continuous network; critical.
- Curing agent / crosslinker: network formation; critical.
- Catalyst / accelerator: cure kinetics gate; critical **even when the mass fraction is small**.
- Filler / pigment: supporting; can affect modulus/CTE but not primary network.
- Solvent / additive: supporting/process; mostly removed or low-dose.
- Formulation balance / ratios / solids: supporting context.
- Molecular descriptors: descriptive, not a direct mechanism measurement.
- FTIR bands: weight by **diagnostic specificity for a role**, not peak intensity.

## Role weights (raw, before normalization)

| group | role tier | raw weight | rationale |
|---|---|---:|---|
| `resin_network` | critical | 1.0 | 连续相/网络骨架，T 弯的主承载 |
| `cure_crosslink` | critical | 1.0 | 交联密度与网络完整性 |
| `catalyst_kinetics` | critical | 1.0 | 用量小但控制固化动力学；不得按质量占比降权 |
| `filler_pigment` | supporting | 0.7 | 可能影响模量/CTE，但不是主网络 |
| `solvent_additive` | supporting | 0.7 | 成膜/流变/助剂，固化后多为次要 |
| `formulation_balance` | supporting | 0.7 | 配比/固含是上下文，不是单一角色 |
| `molecular_descriptor` | descriptive | 0.4 | 结构描述，非直接机理测量 |
| `ftir_band` | diagnostic | 1.0 | 按诊断角色单独加权；见下 |
| `other` | neutral | 1.0 | 无法归类的特征保持中性，不强行归类 |

Normalize the nine group weights to mean 1 across groups before applying.

## Mass prior (control, not the hypothesis)

For material groups, `mass_prior` uses the average mass share of that material role among the 301 T samples:

- `resin_network` → total resin mass share
- `cure_crosslink` → total curing-agent mass share
- `catalyst_kinetics` → total catalyst mass share (`AC040`, `AZ135`, `10%磷酸`)
- `filler_pigment` → total pigment mass share
- `solvent_additive` → total solvent + non-catalyst additive mass share

For non-material groups (`formulation_balance`, `molecular_descriptor`, `ftir_band`, `other`), use the role-prior raw weights so the comparison changes only material-role weights. Normalize the resulting vector to mean 1.

This is deliberately the “dosage = importance” baseline. If `role_prior` cannot beat it, the role-criticality hypothesis is not supported on this dataset.

## FTIR band weights (diagnostic role, not intensity)

| band | diagnostic role | raw weight |
|---|---|---:|
| `ftir_oh_phen` | phenolic resin / network | 0.8 |
| `ftir_oh_epox` | epoxy / cure | 1.0 |
| `ftir_meoh_phen` | methoxy phenolic resin | 0.6 |
| `ftir_aroc_phen` | aromatic resin | 0.8 |
| `ftir_coc_all` | ether / network | 1.0 |
| `ftir_arsub_all` | aromatic substitution / resin | 0.8 |
| `ftir_ch_all` | CH backbone | 0.6 |
| `ftir_co_all` | carbonyl / cure | 1.0 |

Normalize band weights to mean 1. `ftir_band_intensity` is a separate control that weights by training-fold mean band magnitude, not by this table. `ftir_band_shuffle` permutes this table across bands with a seed-fixed permutation.

## Transform rules (P21-D)

- `log_cat`: replace `eq_cat` by `log1p(1000 * eq_cat)`.
- `log_cat_ratio`: additionally replace `r_phenol_epoxy` by `log1p(10*x)` and `r_oh_epoxy` by `log1p(10*x)`. Exploratory only.
- `two_part_cat`: replace `eq_cat` by `cat_has` (x > 0) and `log1p(1000*x)`.
- `interact`: append `eq_cat*xlink_frac`, `eq_cat*r_phenol_epoxy`, `eq_cat*r_oh_epoxy`, `xlink_frac*resin_frac`.
- `interact_shuffle`: same products but partner features are row-permuted with a seed-fixed permutation.

Transform parameters use fixed scales; no test-fold fitting. Rank/quantile/spline transforms are not tested in P21.

## Mapping rules

- `frac_<code>` → material role from `mat_lib` (`树脂/固化剂/颜料/溶剂/助剂`); catalyst codes `AC040`, `AZ135`, `10%磷酸` override `助剂` → `catalyst_kinetics`.
- `rare_present_<code>` → same mapping by material code.
- `rare_total` → `other`.
- `ftir_*` → `ftir_band`.
- `树脂_w_*` → resin; `固化剂_w_*` → cure; `溶剂_w_*` → solvent+additive.
- Explicit names follow the group table below; ambiguous features go to `other` with neutral weight 1.0.

## Guardrails

- Weights are applied **after** `StandardScaler` and after group-size normalization.
- `role_prior`/`mass_prior` use the same role map and group normalization; only the weight values differ.
- `C=2.0` fixed; no weight tuning on QWK.
- No target labels in map, mass computation, transform selection, or placebo construction.

## Addendum A1 — direct-weight exploratory arms (2026-11-28)

The sanity check showed that the group-normalised uniform baseline
(`full8_gn_base`) is `0.517882` versus `full8_base` `0.576128` on seed 42.
Group-size normalisation therefore carries a ~0.058 QWK penalty independent
of role semantics. The pre-registered group-normalised arms and C1 gate stay
unchanged and will be reported as the primary result.

Two exploratory arms are added, with no gate and no tuning:

- `mass_prior_direct`: same normalised mass weights, applied after
  `StandardScaler` **without** `1/sqrt(n_group)` or group-norm rescaling.
- `role_prior_direct`: same normalised role weights, applied the same direct
  way.

They exist only to separate "role weight values" from "group-size
normalisation". `role_prior_direct − mass_prior_direct` and
`role_prior_direct − role_prior_shuffle` are exploratory specificity
comparisons. They do not alter C1/C2/C3/C4.
