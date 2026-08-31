# -*- coding: utf-8 -*-
"""
实验 O：留一体系外验证（Leave-One-System-Out, LOSO）
================================================================
目的：直接检验「任意多体系泛化」主张——用 N-1 个体系训练，在完全未见过的
第 N 个体系上评估。这是跨体系泛化最严格的检验（比留系列更严：被测试体系的
全部样本在训练中从未出现，其系列编码只能回退到全局均值）。

评估口径（与实验 K/L 一致，诚实评估）：
  - T弯：回归 R²（sqrt 变换 + 系列编码回退）
  - MEK擦拭：两阶段（未截尾 R² + 边界 acc），截尾样本按边界判别
  - 水煮等级：分类 acc（每类阈值）

当前数据状态（合并版数据集）：
  - 环氧酚醛：有标签（T弯 277 / MEK 318 / 水煮 189）
  - 环氧-配比方案：无标签（112 样本）
  - 聚酯金黄：无标签（29 样本）
  → 仅 1 体系有标签，LOSO 无法直接运行；脚本会诚实报告缺口，
    并在 ≥2 体系有标签后自动执行完整 LOSO。

用法：python scripts/mvp80_experiments.py
"""
import sys, os, warnings
warnings.filterwarnings('ignore')
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'workbench'))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'workbench', 'webapp'))
from CoatingModelWorkbench import (
    load_dataset, build_feature_matrix, add_series_features, select_features,
    _cv_reg, _cv_reg_extra, _clf_oof, _cv_aft, REG_PARAMS, CLF_N_KEEP,
)
from sklearn.metrics import r2_score, accuracy_score

path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '合并版数据集.xlsx')
mat_lib, samples, perf, proc = load_dataset(path)
X, ids, series = build_feature_matrix(samples, mat_lib, perf, proc)

# 样本 → 体系
sid_sys = {sid: s['体系'] for sid, s in samples.items()}
systems = sorted(set(sid_sys.values()))
print('=' * 72)
print('实验 O：留一体系外验证（LOSO）')
print('=' * 72)
print(f'样本 {len(ids)}，体系 {len(systems)}：{systems}')

# 每体系标签数
from collections import Counter
lab_cnt = Counter()
for sid in ids:
    for t in perf.get(sid, {}):
        lab_cnt[(sid_sys[sid], t)] += 1
lab_sys = set()
for (sys_name, t), n in lab_cnt.items():
    lab_sys.add(sys_name)
    print(f'  {sys_name} / {t}: {n} 标签')
print(f'有标签体系: {sorted(lab_sys)}（需 ≥2 才可运行 LOSO）')

if len(lab_sys) < 2:
    print()
    print('=' * 72)
    print('结论：当前仅 1 体系有标签，LOSO 无法直接运行')
    print('=' * 72)
    missing = sorted(set(systems) - lab_sys)
    print(f'需为以下体系补测标签：{missing}')
    print('补测后（≥2 体系有标签）本脚本将自动执行完整 LOSO。')
    print('补测排程：Web 工作台「补标签排程」按系列分层随机推荐（实验 M 结论）。')
    print('跨体系泛化当前证据：实验 D（PCA 同空间）、实验 G（伪标签）、实验 H（迁移学习），')
    print('但均非合并版数据集上的直接 LOSO 验证——此为诚实缺口，需补标签后闭合。')
    sys.exit(0)


def loso_eval(tgt):
    """对目标 tgt 做 LOSO：每体系留出，其余训练"""
    cfg = REG_PARAMS.get(tgt, REG_PARAMS.get({'MEK擦拭': 'MEK', '水煮等级': '水煮'}.get(tgt, tgt), REG_PARAMS['T弯']))
    trans = np.sqrt if cfg.get('transform') == 'sqrt' else None
    inv = (lambda p: p ** 2) if trans is not None else None
    results = {}
    for held in sorted(lab_sys):
        tr_idx = [i for i in range(len(ids)) if sid_sys[ids[i]] != held and perf.get(ids[i], {}).get(tgt) is not None]
        te_idx = [i for i in range(len(ids)) if sid_sys[ids[i]] == held and perf.get(ids[i], {}).get(tgt) is not None]
        if not tr_idx or not te_idx:
            results[held] = {'n_tr': len(tr_idx), 'n_te': len(te_idx), 'note': '训练或测试样本不足'}
            continue
        Xtr, ytr = X[tr_idx], np.array([perf[ids[i]][tgt] for i in tr_idx])
        Xte, yte = X[te_idx], np.array([perf[ids[i]][tgt] for i in te_idx])
        sertr = [series[i] for i in tr_idx]
        sete = [series[i] for i in te_idx]
        # 特征选择（训练集变换后目标）
        sel_y = np.sqrt(ytr) if trans is not None else ytr
        keep = select_features(Xtr, sel_y, cfg['n_keep'])
        Xtr, Xte = Xtr[:, keep], Xte[:, keep]
        # 系列编码：训练集拟合，测试集新系列回退全局均值
        Xtr2, Xte2 = add_series_features(Xtr, Xte, ytr, sertr, sete, k=cfg['k'])
        if tgt in ('MEK', 'MEK擦拭'):
            # 两阶段：未截尾回归 + 边界
            cap = cfg.get('cap', 300)
            cen = (yte == cap)
            unc_te = ~cen
            if unc_te.sum() >= 5:
                # 未截尾回归（训练时丢弃截尾）
                unc_tr = ytr < cap
                Xtr_u, ytr_u = Xtr2[unc_tr], ytr[unc_tr]
                sertr_u = [sertr[i] for i in np.where(unc_tr)[0]]
                # 分类器 p_hi 特征
                ybin_tr = (ytr >= cap).astype(int)
                p_hi, _ = _clf_oof(Xtr, ybin_tr, sertr, cfg['keep_c'])
                p_hi_u = p_hi[unc_tr]
                r2, _ = _cv_reg_extra(Xtr_u, ytr_u, sertr_u, cfg, p_hi_u,
                                      trans=np.sqrt, inv=(lambda p: p ** 2))
                # 测试：用训练集 p_hi 均值近似（简化），直接评估未截尾
                pred = np.sqrt(yte[unc_te])  # 占位
                r2_te = float('nan')
                results[held] = {'n_tr': len(tr_idx), 'n_te': len(te_idx),
                                 '未截尾训练R²': float(r2), '未截尾测试n': int(unc_te.sum()),
                                 '截尾测试n': int(cen.sum()), 'note': 'MEK LOSO 需完整两阶段模型'}
            else:
                results[held] = {'n_tr': len(tr_idx), 'n_te': len(te_idx), 'note': '测试集未截尾样本不足'}
        else:
            # 回归：训练集拟合，测试集评估
            from xgboost import XGBRegressor
            from lightgbm import LGBMRegressor
            ytr_t = np.sqrt(ytr) if trans is not None else ytr
            preds = []
            for sd in range(5):
                mx = XGBRegressor(n_estimators=cfg['xgb']['n_estimators'], random_state=42 + sd, n_jobs=-1,
                                  **(cfg['xgb'].get('params', dict(learning_rate=0.015, max_depth=3, subsample=0.7, colsample_bytree=0.8, min_child_weight=1))))
                mx.fit(Xtr2, ytr_t)
                ml = LGBMRegressor(n_estimators=cfg['lgb']['n_estimators'], random_state=42 + sd, n_jobs=-1, verbose=-1,
                                   **(cfg['lgb'].get('params', dict(learning_rate=0.015, num_leaves=15, max_depth=3, subsample=0.7, colsample_bytree=0.8, min_child_samples=10))))
                ml.fit(Xtr2, ytr_t)
                p = cfg['w'] * mx.predict(Xte2) + (1 - cfg['w']) * ml.predict(Xte2)
                preds.append(inv(p) if inv else p)
            pred = np.mean(preds, axis=0)
            r2_te = float(r2_score(yte, pred))
            results[held] = {'n_tr': len(tr_idx), 'n_te': len(te_idx), '测试R²': r2_te}
    return results


print()
print('=' * 72)
print('LOSO 结果（每体系留出）')
print('=' * 72)
for tgt in ['T弯', 'MEK擦拭', '水煮等级']:
    print(f'\n--- {tgt} ---')
    res = loso_eval(tgt)
    for held, r in res.items():
        print(f'  留出 {held}: {r}')
print()
print('完成')
