# P19 Literature Notes — Data Layer

**Date**: 2026-11-26
**Purpose**: Search for (a) a compatible formulation-level epoxy-phenolic T-bend dataset, and (b) a defensible T-bend measurement-noise reference. Literature is used only for context and uncertainty bands. **No literature T value is inserted into the 301-row ground truth.**

## Search queries run

1. `T-bend flexibility epoxy phenolic coating dataset formulation T-bend test ASTM D4145`
2. `"T-bend" dataset machine learning coating formulation prediction`
3. `epoxy phenolic coating formulation database open dataset coating properties`
4. `ASTM D4145 T-bend test repeatability precision coating flexibility`
5. `tabular data augmentation small sample regression mixup SMOTE materials informatics coating`
6. Academic search: `epoxy phenolic coating T-bend flexibility dataset formulation machine learning`
7. Academic search: `data augmentation small tabular regression materials science limited data`
8. Academic search: `T-bend test repeatability coating flexibility ASTM D4145`

## Finding 1 — no compatible public T-bend formulation dataset

The searches returned standards, method papers, patents, and generic coating-property descriptions, but **no machine-readable, formulation-level epoxy-phenolic T-bend dataset** with the same features, substrate, bake condition, and `[15, 20]` cut definition. Therefore:

- External T rows merged: **0**.
- External pretrained model or pseudo-label transfer: **0**.
- The only external numbers used are the ASTM precision statistics below, and they are used as a **reference band**, not as labels.

## Finding 2 — T-bend is a noisy measurement at the cut scale

ASTM D4145 is the standard test method for coating flexibility of prepainted sheet. Its precision statement reports:

| Substrate | T-bend to no fracture, SD (mm) | Within-lab repeatability (mm) | Between-lab reproducibility (mm) |
|---|---:|---:|---:|
| Aluminum | 0.55 | 0.4 | 2.5 |
| Galvanized steel | 1.33 | 1.8 | 10.1 |

The same standard notes that bend direction, specimen temperature, coating thickness, application and cure conditions should be reported, and it distinguishes “no fracture” from “no pickoff”. This dataset records one T value without substrate or pickoff/fracture distinction. The substrate is not recorded in the modelling table, so P19 uses **1.8 mm as a conservative in-lab reference band** and **1.33 mm as the galvanized SD reference**; neither is this dataset’s measured noise.

At this scale, the cut exposure is large:

- 55/301 (18.3%) within ±0.5 mm of 15 or 20;
- 103/301 (34.2%) within ±1.0 mm;
- 132/301 (43.9%) within ±1.33 mm;
- 190/301 (63.1%) within ±1.8 mm.

This is a data-layer property, not a model bug. It also explains why threshold tuning alone is unlikely to produce a stable decision policy.

## Finding 3 — augmentation literature does not guarantee tabular gains

Representative results:

- SMOTE and related interpolation methods are widely used for class imbalance; the synthetic point is a feature-space interpolation, not a physically realized sample. This supports the P19 rule that synthetic rows are training-only.
- Tabular augmentation papers caution that simple Mixup-style interpolation can conflict with irregular tabular functions and can degrade rather than improve performance. This is consistent with P19’s pre-registered negative result for jitter/SMOTE.
- Small-sample imbalanced-data papers show augmentation can help classification balance, but they do not supply a formulation-level T-bend dataset or a validation protocol that would justify treating synthetic T as ground truth.

## Finding 4 — no repeated T measurements in the current table

The workbook has 301 epoxy-phenolic T performance rows for 301 unique samples: **0 repeated samples**. ICC/κ of repeated T cannot be estimated from this data. The ASTM reference band is therefore the only available noise anchor, and it is external and substrate-dependent.

## Decision

- Do **not** merge literature values into the training table.
- Do **not** call synthetic samples “new data” or “manual supplementation of measurements”.
- Use the audit and ASTM band to frame the label ceiling, and treat augmentation/weighting as training regularizers only.
- If future data become available, prioritize 20–30 stratified repeated T measurements over more synthetic rows; only repeats can estimate the label-noise floor.

## URLs

- ASTM D4145 standard page: <https://store.astm.org/d4145-10r18.html>
- ASTM D4145 precision table (PDF copy): <https://dornicaco.ir/ASTM/71.pdf>
- ASTM interlaboratory study record: <https://www.astm.org/rr-d01-1034.html>
- SMOTE example in materials tabular data: <https://arxiv.org/html/2512.05367>
- Tabular augmentation caveat: <https://arxiv.org/html/2301.02819v5>
- Small-sample imbalanced tabular pipeline: <https://onlinelibrary.wiley.com/doi/10.1155/2022/9024165>
