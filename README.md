# 3NEW · 三新项目研发

涂料性能与配方-工艺关系预测模型的**全链路优化与泛化验证**研究成果。

## 阶段导航

| 阶段 | 目录 | 内容 |
| --- | --- | --- |
| 第一阶段 · 优化与泛化验证 | `report/` `code/` `models/` `data/` | 特征工程、数据增强、模型集成、诚实复盘（本 README 主体） |
| 第二阶段 · 跨体系数据集（终极版模板 + 合并版数据集） | [`generalization/`](generalization/README.md) | 跨体系通用描述符、终极版数据集模板、合并版数据集、配套 Windows 工作台、最终验证（T弯 R²≈0.79 / MEK 未截尾 R²≈0.50 / 水煮 acc≈0.80） |

> 第二阶段交付：终极版模板 + 自动化工作台 + 合并版数据集。**注意**：合并版数据集早期仅「环氧酚醛」1 个体系含实测标签；后续已从原始配方/性能表补全「聚酯金黄」26 条实测标签，并修复了组成解析、特征转换等残留 bug，水煮指标经分层建模重新达标。三个体系均可表达进同一特征空间，但「环氧-配比方案」仍无实测标签，跨体系泛化仍为开放缺口，详见 [`generalization/README.md`](generalization/README.md) 与「数据局限」一节。

## 目标

面向涂料研发场景，尝试建立"配方 → 性能"的预测模型，设定并逐项诚实验证以下指标：

- 回归（T弯、MEK 耐擦拭）：R² 目标 ≥ 0.85
- 分类（水煮等级）：准确率目标 ≥ 0.95

## 核心方法

| 维度 | 做法 |
| --- | --- |
| 数据侧 | 特征交互/组合工程、文献驱动数据增强（增广至 3,200 条）、目标稳健化（winsorize / log1p / 删失保留）、清洁同工艺池 |
| 训练侧 | GroupKFold（按配方族）、OOF-stacking、门控专家混合、多任务链式/嵌入、协同训练、伪主动学习、留一法（LOO）诊断 |
| 算法侧 | 5 类基模型（ET/RF/GBR/SVR/Ridge）+ 集成，跨批迁移诊断与外部真实数据集泛化验证 |
| 验证纪律 | 全程清洁同工艺池（200℃/10min），按配方族 GroupKFold 诚实验证，不混异工艺数据 |

## 关键结论（诚实复盘）

- 特征组合（含原创重建红外结构指纹）是唯一跨架构、跨 seed 稳健的正向杠杆。
- 模型侧最佳增益来自 MEK OOF-stacking（R² +0.09）；分类上无集成能稳定提升。
- 训练域内诚实上界：MEK R²≈0.44、T弯 R²≈0.46、水煮 acc≈0.43（GroupKFold/LOO 均指向同量级）。
- 跨批次外推决定性证据：7.26→新100 中 5 个模型 R² 全为强负，特征空间最近邻诊断显示 **100% 新配方落在训练区 1.5σ 之外（纯外推）**。
- **结论**：性能上限由数据信噪比决定；R²≥0.85 / acc≥0.95 在当前数据上数学上不可达，需先补齐新配方的见区数据。详见报告。

## 目录结构

```
3NEW
├── README.md                         # 本文件：项目总览、方法、结论、复现
├── report/                           # 研究报告（直接用浏览器打开）
│   ├── coating-model-optimization.html   # 主报告（含交互图表）
│   └── assets/
│       ├── charts.js                 # ECharts 图表渲染脚本
│       └── data.js                   # 真实 PCA 数据注入
├── code/                             # 可复现脚本（详见 code/README.md）
│   ├── predict_v3.py                 # 预测接口（可直接运行）
│   ├── build3.py / blend_ir.py / build_ir.py   # 特征构建·重建红外
│   ├── final_combined.py / transfer_c.py       # 三协议评估·跨批迁移
│   ├── train_champion_v3.py / save_champ_v5~v7.py   # 各版本冠军模型
│   ├── advanced_tech.py / advanced_clf.py      # 高级回归/分类技术对比
│   ├── augment_clean.py / save_augset.py / deliver_aug.py / final_matrix.py  # 数据增强管线
│   ├── generalization2.py             # 外部 PolySol 泛化验证
│   ├── loo.py / cross_batch_diag.py / within_family.py / noise_floor.py / w_coupling.py  # 诊断
│   └── pseudo_al.py / cotrain.py / mt_embed.py  # 主动学习/协同训练/多任务嵌入
├── models/                           # 冠军模型 v3~v7
│   ├── champion_models_v3.pkl  # §7.2 终训（33维交互特征）
│   ├── champion_models_v4/v5/v6/v7.pkl  # §5.8/§5.9 增强/combo特征各版本
└── data/                             # 编译特征矩阵 + 增广数据集
    ├── master3.npz                   # build3.py 产物：O(371)+N(100) 对齐特征与目标
    ├── augmented_dataset_cleanprocess.csv   # 真实+增强混合（3,200 条，源/配方族列）
    └── augmented_only_cleanprocess.csv      # 仅增强样本
```

## 快速开始

1. 直接打开 `report/coating-model-optimization.html`（浏览器即可渲染，无构建依赖；ECharts 走 CDN）。
2. 跑通预测：`python3 code/predict_v3.py`（加载 `models/champion_models_v3.pkl`，输出更新批第 1 条的性能预测）。
3. 数据集：`data/*.csv` 列为 `f0..f28`（29 维配方/工艺特征）+ 目标 `yT`（T弯）、`yM`（MEK）、`yW`（水煮等级）+ `source`（真实/增强）、`family`（配方族，用于 GroupKFold）。
4. 完整代码与逐脚本说明见 `code/README.md`。

## 复现要点

- 严格按 `family` 做 GroupKFold，测试族绝不进入训练。
- 不使用 8.5/8.6 等异工艺数据（清洁池 = 7.26 + 新100，均 200℃/10min）。
- 跨批验证训练/测试集合在特征域上分离（见报告 §5.5 决定性诊断）。