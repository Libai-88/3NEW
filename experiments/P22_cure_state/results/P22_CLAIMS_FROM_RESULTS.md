# P22 Claims From Results

REVIEW_UNAVAILABLE

**claim_supported: false**

**verdict**: 外部跨模型 reviewer 不可用；本文件只记录预注册 gate 的机器判定与本地确定性审计结果，不由执行者自判 acquit。

## Gate summary

| Claim | Gate | Result | Evidence |
|---|---|---|---|
| C1 — cure-state 主效应 | `cure_state − full8_base` ≥ +0.010；≥14/20；Holm p<0.05；FR≤+1.0 pp；HR≥−2.0 pp | **FAIL** | ΔQWK `+0.009007`；12/20；Holm p `0.20269`；FR `+0.775 pp`；HR `−2.042 pp` |
| C2a — bake 已入模后 cure 仍有增量 | `cure_state_plus_bake − bake_control` ≥ +0.005；≥14/20；Holm p<0.05；FR/HR 护栏 | **FAIL** | ΔQWK `−0.003612`；6/20；Holm p `0.20269`；HR `−0.352 pp` |
| C2b — 跨烘烤条件压力测试 | LOCO pooled `cure_state − full8_base` ≥ +0.005；FR≤+1.0 pp；HR≥−2.0 pp | **FAIL** | ΔQWK `−0.135212`；0/20；FR `+1.408 pp`；HR `−8.451 pp` |
| C2 — 条件可分性 conjunction | C2a 且 C2b | **FAIL** | 两者均失败 |
| C3 — 语义特异性（supporting） | `cure_state − cure_state_shuffle` ≥ +0.005；≥14/20；p<0.05；FR/HR 护栏 | **PASS** | ΔQWK `+0.014604`；14/20；p `0.01530`；FR `−0.211 pp`；HR `−1.127 pp` |
| CURE3 — 简化性检查（非 claim） | `cure_state_tg − cure_state` | **FAIL / 不升级** | ΔQWK `−0.003649`；4/20；p `0.22032` |

## Diagnostic arms

- `bake_control − full8_base`: ΔQWK `+0.012458`，12/20，p `0.0164`，FR `+0.634 pp`，HR `−1.761 pp`。这是全场最高的单臂，但它只是一个烘烤条件二元指示，不是新的固化表示；12/20 也未达到 14/20 的稳定性门槛。
- `cure_state − bake_control`: ΔQWK `−0.003451`，6/20，p `0.12`。在 bake 已入模后，CURE2 没有增量。
- `cure_state_plus_bake`: `0.579028 ± 0.023242`，低于 `bake_control` 的 `0.582640 ± 0.022421`。

## Readout

C1 和 C2 均失败，因此 `claim_supported=false`。C3 通过只说明 CURE2 相对同维度随机块有语义信号，不构成可部署 claim；该信号在分布内甚至弱于单个 `cure_205` 二元烘烤指示，且 LOCO 下崩溃。

外部 reviewer 不可用，verdict 只能为 `REVIEW_UNAVAILABLE`；本地审计 24/24 通过，状态 `PROVISIONAL_LOCAL_AUDIT`。
