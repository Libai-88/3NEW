# Claims from P0–P14 results

本表只记录**能由现有 CSV/JSON 直接支持的 claim**，并标注证据边界。P15/P16 结果另见各自报告，不混入本表。

| Claim | Evidence | Verdict | Boundary |
|---|---|---|---|
| P14 base183 nested T QWK `0.54513774` | `p14_t7_nested.csv` / `P14` report | supported | 10 seeds, fixed base183 |
| P14 190 nested T QWK `0.57069734` | same | supported | 条件于 post-hoc 190 集；不是完整 nested 特征选择 |
| P14 190−base delta `+0.0255596`，p `0.00461597`，9/10 seeds 正 | same | supported | 20-perm p 是下限；seed-level 不是 sample-level |
| P14 fixed C=2 190 QWK `0.5796898984` | `p14_t_drop_one_per_seed.csv` | supported | 描述性；C 固定，不是 nested |
| 190 vs core4 diff `+0.0003326896` | P14 subset table | supported | core4 是历史子集，非新搜索 |
| P14 190 vs full8 diff `+0.0057154186` | drop-one table | supported | drop-one 是 post-hoc |
| P10 FTIR8 T delta `+0.0283` < pre-reg `+0.03` | P10 report | supported | FTIR8 可由 base183 重建；不是独立信息 |
| P11 无公式组块过 `+0.03` | P11 report | supported | 需排除 `invalid_water` 运行 |
| P13 FTIR8 3-seed delta `+0.034928` | P13 report | preliminary | 3 seeds；P14 修正 base 后不能直接当最终增益 |
| 三目标平均 `0.5609` | P14 report | limited | T 10 seeds + MEK/水煮 3 seeds，协议不齐 |
| 根 README T masked R² `0.749` | root README / P0 | different metric | 313 维回归 + 公共掩码；不是 P14 QWK |
