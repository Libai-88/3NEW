# 代码与复现说明

本目录收录报告《涂料性能预测模型：全链路优化与泛化验证》（`../report/coating-model-optimization.html`）的**核心可复现脚本**与由它们产出的模型与数据。原始调试脚本未收录，以保持仓库整洁。

## 目录结构

```text
3NEW
├── code/                      # 可复现脚本（本目录）
│   ├── README.md
│   ├── predict_v3.py          # 预测接口（可直接运行，需 ../models/champion_models_v3.pkl）
│   ├── build3.py              # §特征构建：由原始上传数据编译 master3.npz
│   ├── blend_ir.py            # 重建红外光谱特征（SNV+二阶导+PCA，含 IR190）
│   ├── build_ir.py            # 红外归档解包 => blend_feats.npz
│   ├── final_combined.py      # §5.2 合并数据三种协议评估
│   ├── transfer_c.py          # §5.5 跨批/跨工艺迁移(Leave-Regime-Out)诊断
│   ├── same_process_champ.py  # §5.7 同工艺域内 Champion 训练
│   ├── train_champion_v3.py   # §7.2 终训 champion_models_v3.pkl
│   ├── save_champ_v5/v6/v7.py # §5.8/5.9 各版本冠军模型落盘
│   ├── advanced_tech.py       # §5.4 高级回归技术对比（stacking/门控/伪标签等）
│   ├── advanced_clf.py        # §5.4 高级分类技术对比
│   ├── augment_clean.py       # §5.8 文献驱动化学合理数据增强
│   ├── save_augset.py         # §5.8 导出增广数据集 CSV
│   ├── deliver_aug.py         # §5.8.3 增强真实增益诚实验证 + v4
│   ├── final_matrix.py        # §5.8.3 增强矩阵对比
│   ├── generalization2.py     # §6 外部 PolySol 数据泛化验证
│   ├── loo.py                 # §5.4.1 留一法(record-LOO / family-LOO)诊断
│   ├── cross_batch_diag.py    # §5.5 跨批次决定性分布位移诊断
│   ├── within_family.py       # §5.9.6 族内可学性判别
│   ├── noise_floor.py         # §5.9.6 标签噪声基底诊断
│   ├── w_coupling.py          # §5.9.7 水煮等级耦合诊断
│   ├── pseudo_al.py           # §5.6 伪主动学习
│   ├── cotrain.py             # §5.6 协同训练
│   └── mt_embed.py            # §5.9.4 多任务嵌入
├── models/                    # 各版本冠军模型（预测/复现用）
│   ├── champion_models_v3.pkl # §7.2 终训版本（33维交互特征）
│   ├── champion_models_v4.pkl # §5.8 清洁池+增强 v4
│   ├── champion_models_v5.pkl # §5.8 最强架构 v5
│   ├── champion_models_v6.pkl # §5.9 extra组合特征 + XGB/LGB
│   └── champion_models_v7.pkl # §5.9 当前最强者（extra 429维 + 最强架构）
├── data/                      # 编译特征矩阵 + 增广数据集
│   ├── master3.npz            # build3.py 产物：O(371)+N(100) 对齐特征与目标
│   ├── augmented_dataset_cleanprocess.csv   # 真实+增强混合
│   └── augmented_only_cleanprocess.csv      # 仅增强
└── report/                    # 研究报告（主报告 + 图表资源）
```

## 快速开始：预测

```bash
python3 code/predict_v3.py
```

输出对应新批第 1 条（200℃/10min）的 T弯/MEK/水煮等级及各级概率。接口签名见文件头注释，可 `from predict import predict_performance` 改配比调用。

依赖：`numpy`、`scikit-learn`、`pandas`、`openpyxl`（构建脚本）、`RDKit`（仅 §6 外部验证脚本 `generalization2.py`）。

## 复现要点（与报告一致）

- 严格按 `family` 做 GroupKFold，测试族绝不进入训练。
- 清洁同工艺池 = 7.26 批(200℃/10min) + 新 100 组，不使用 8.6(205℃/17min) 异工艺批次。
- 跨批外推的关键证据见 §5.5：特征空间最近邻诊断显示新 100 全落在训练区 1.5σ 之外。
- 增强仅在训练折内由真实行生成，测试族不参与任何增强。

## 数据处理链路

1. 原始上传数据（7.26/8.6 配料汇总、新 100 组 CSV、8.12 红外归档）放在 `data/uploads/`（因含原始研发数据，本仓库默认不提交，可自行放入以完整复现 `build3.py`/`blend_ir.py`）。
2. 运行 `build3.py` 生成 `data/master3.npz`（已随仓库提供）。
3. 其余脚本直接读取 `../data/master3.npz`，相对路径无需修改即可在 `code/` 目录内运行。